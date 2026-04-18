//! XMODEM Protocol Module
//!
//! Implements the XMODEM file transfer protocol with CRC-16 and checksum modes:
//! - xmodem_receive: receive file data from a sender (upload)
//! - xmodem_send: send file data to a receiver (download)
//! - Raw I/O helpers with telnet IAC escaping
//! - CRC-16 (CCITT polynomial 0x1021) computation

use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};

use crate::config;
use crate::logger::glog;
use crate::telnet::is_esc_key;

// XMODEM protocol constants
const SOH: u8 = 0x01;
/// XMODEM-1K block header: the next block is 1024 bytes of payload.
const STX: u8 = 0x02;
const EOT: u8 = 0x04;
const ACK: u8 = 0x06;
const NAK: u8 = 0x15;
const CAN: u8 = 0x18;
const SUB: u8 = 0x1A;
const CRC_REQUEST: u8 = b'C';

// Telnet protocol bytes
const IAC: u8 = 0xFF;
const SB: u8 = 250;
const SE: u8 = 240;
const WILL: u8 = 251;
const WONT: u8 = 252;
const DO_CMD: u8 = 253;
const DONT: u8 = 254;

pub(crate) const XMODEM_BLOCK_SIZE: usize = 128;
/// XMODEM-1K block size.  The sender chooses per-block; the receiver
/// branches on the `SOH` / `STX` header byte to know which one arrived.
pub(crate) const XMODEM_1K_BLOCK_SIZE: usize = 1024;

const MAX_FILE_SIZE: usize = 8 * 1024 * 1024;
/// Time allowed for the full 131-byte block body (after SOH) to arrive.
const BLOCK_BODY_TIMEOUT_SECS: u64 = 60;

#[derive(Clone, Copy)]
enum TransferMode {
    Checksum,
    Crc16,
}

// =============================================================================
// XMODEM PROTOCOL - RECEIVE (UPLOAD)
// =============================================================================

pub(crate) async fn xmodem_receive(
    reader: &mut (impl AsyncRead + Unpin),
    writer: &mut (impl AsyncWrite + Unpin),
    is_tcp: bool,
    is_petscii: bool,
    verbose: bool,
) -> Result<Vec<u8>, String> {
    let cfg = config::get_config();
    let negotiation_timeout = cfg.xmodem_negotiation_timeout;
    let block_timeout = cfg.xmodem_block_timeout;
    let max_retries = cfg.xmodem_max_retries;

    let mut file_data = Vec::new();
    let mut expected_block: u8 = 1;
    let negotiation_deadline =
        tokio::time::Instant::now() + tokio::time::Duration::from_secs(negotiation_timeout);

    if verbose { glog!("XMODEM recv: starting negotiation (is_tcp={}, is_petscii={})", is_tcp, is_petscii); }

    // Negotiate mode: try CRC first ('C') for 20 attempts (60 seconds),
    // then fall back to checksum (NAK) for the remaining time.  This gives
    // the user plenty of time to start their XMODEM sender in CRC mode.
    let mut mode = TransferMode::Crc16;
    let mut attempt: u32 = 0;

    // Send CRC requests for 2/3 of the negotiation time, then fall back to checksum.
    let crc_attempts = (negotiation_timeout * 2 / 3 / 3).max(3) as u32;
    let max_negotiation_attempts = crc_attempts + max_retries as u32;
    loop {
        if tokio::time::Instant::now() >= negotiation_deadline {
            return Err("Negotiation timeout: start your XMODEM sender".into());
        }
        if attempt >= max_negotiation_attempts {
            return Err("Negotiation failed: no response from sender".into());
        }

        let request = if attempt < crc_attempts { CRC_REQUEST } else { NAK };
        if attempt == crc_attempts {
            mode = TransferMode::Checksum;
        }
        if verbose { glog!("XMODEM recv: attempt {} sending 0x{:02X} ({})",
            attempt, request, if request == CRC_REQUEST { "CRC req" } else { "NAK" }); }
        raw_write_byte(writer, request, is_tcp).await?;

        match tokio::time::timeout(
            std::time::Duration::from_secs(3),
            raw_read_byte(reader, is_tcp),
        )
        .await
        {
            Ok(Ok(byte)) => {
                if verbose { glog!("XMODEM recv: got 0x{:02X} during negotiation", byte); }
                if is_esc_key(byte, is_petscii) {
                    return Err("Transfer cancelled".into());
                }
                if byte == SOH || byte == STX {
                    let block_size = if byte == STX {
                        XMODEM_1K_BLOCK_SIZE
                    } else {
                        XMODEM_BLOCK_SIZE
                    };
                    if verbose {
                        glog!(
                            "XMODEM recv: {} received, reading block #1 ({}-byte)",
                            if byte == STX { "STX" } else { "SOH" },
                            block_size,
                        );
                    }
                    match tokio::time::timeout(
                        std::time::Duration::from_secs(BLOCK_BODY_TIMEOUT_SECS),
                        receive_block(
                            reader,
                            &mut expected_block,
                            mode,
                            is_tcp,
                            verbose,
                            block_size,
                        ),
                    )
                    .await
                    {
                        Ok(Ok(data)) => {
                            if verbose { glog!("XMODEM recv: block #1 OK"); }
                            file_data.extend_from_slice(&data);
                            raw_write_byte(writer, ACK, is_tcp).await?;
                        }
                        Ok(Err(e)) => {
                            if verbose { glog!("XMODEM recv: block #1 error: {}", e); }
                            raw_write_byte(writer, NAK, is_tcp).await?;
                        }
                        Err(_) => {
                            if verbose { glog!("XMODEM recv: block #1 timeout"); }
                            raw_write_byte(writer, NAK, is_tcp).await?;
                        }
                    }
                    break;
                }
                if byte == EOT {
                    raw_write_byte(writer, ACK, is_tcp).await?;
                    return Ok(file_data);
                }
                if byte == CAN {
                    return Err("Transfer cancelled by sender".into());
                }
                if verbose { glog!("XMODEM recv: ignoring unexpected byte 0x{:02X}", byte); }
            }
            Ok(Err(e)) => return Err(e),
            Err(_) => {
                if verbose { glog!("XMODEM recv: attempt {} timeout, retrying", attempt); }
            }
        }

        attempt = attempt.saturating_add(1);
    }

    // Main receive loop
    let mut error_count: usize = 0;
    loop {
        if file_data.len() > MAX_FILE_SIZE {
            raw_write_bytes(writer, &[CAN, CAN, CAN], is_tcp).await?;
            return Err("File exceeds 8 MB size limit".into());
        }

        let byte = match tokio::time::timeout(
            std::time::Duration::from_secs(block_timeout),
            raw_read_byte(reader, is_tcp),
        )
        .await
        {
            Ok(Ok(b)) => b,
            Ok(Err(e)) => return Err(e),
            Err(_) => return Err("Transfer timeout".into()),
        };

        match byte {
            SOH | STX => {
                let block_size = if byte == STX {
                    XMODEM_1K_BLOCK_SIZE
                } else {
                    XMODEM_BLOCK_SIZE
                };
                match tokio::time::timeout(
                    std::time::Duration::from_secs(BLOCK_BODY_TIMEOUT_SECS),
                    receive_block(
                        reader,
                        &mut expected_block,
                        mode,
                        is_tcp,
                        verbose,
                        block_size,
                    ),
                )
                .await
                {
                    Ok(Ok(data)) => {
                        file_data.extend_from_slice(&data);
                        raw_write_byte(writer, ACK, is_tcp).await?;
                        error_count = 0;
                    }
                    Ok(Err(ref e)) if e == "Duplicate block" => {
                        raw_write_byte(writer, ACK, is_tcp).await?;
                    }
                    Ok(Err(_)) | Err(_) => {
                        error_count += 1;
                        if error_count > max_retries {
                            raw_write_bytes(writer, &[CAN, CAN, CAN], is_tcp).await?;
                            return Err("Too many block errors".into());
                        }
                        raw_write_byte(writer, NAK, is_tcp).await?;
                    }
                }
            }
            EOT => {
                raw_write_byte(writer, ACK, is_tcp).await?;
                break;
            }
            CAN => {
                return Err("Transfer cancelled by sender".into());
            }
            _ => {
                raw_write_byte(writer, NAK, is_tcp).await?;
            }
        }
    }

    // Strip trailing SUB (0x1A) padding from last block.
    while file_data.last() == Some(&SUB) {
        file_data.pop();
    }

    Ok(file_data)
}

/// Receive and validate a single XMODEM block (after SOH or STX was
/// already read).  `block_size` is 128 for SOH blocks, 1024 for STX
/// (XMODEM-1K) blocks — within a single transfer the sender may mix
/// block sizes, so each call picks up the right size from its header.
async fn receive_block(
    reader: &mut (impl AsyncRead + Unpin),
    expected_block: &mut u8,
    mode: TransferMode,
    is_tcp: bool,
    verbose: bool,
    block_size: usize,
) -> Result<Vec<u8>, String> {
    let block_num = raw_read_byte(reader, is_tcp).await?;
    let block_complement = raw_read_byte(reader, is_tcp).await?;

    if verbose { glog!("XMODEM recv block: num=0x{:02X} complement=0x{:02X} expected=0x{:02X} size={} mode={}",
        block_num, block_complement, *expected_block, block_size,
        match mode { TransferMode::Crc16 => "CRC16", TransferMode::Checksum => "Checksum" }); }

    let mut data = vec![0u8; block_size];
    for byte in data.iter_mut() {
        *byte = raw_read_byte(reader, is_tcp).await?;
    }

    let valid = match mode {
        TransferMode::Checksum => {
            let recv_checksum = raw_read_byte(reader, is_tcp).await?;
            let calc_checksum = data.iter().fold(0u8, |acc, &b| acc.wrapping_add(b));
            if verbose { glog!("XMODEM recv block: checksum recv=0x{:02X} calc=0x{:02X}", recv_checksum, calc_checksum); }
            recv_checksum == calc_checksum
        }
        TransferMode::Crc16 => {
            let crc_hi = raw_read_byte(reader, is_tcp).await?;
            let crc_lo = raw_read_byte(reader, is_tcp).await?;
            let recv_crc = ((crc_hi as u16) << 8) | crc_lo as u16;
            let calc_crc = crc16_xmodem(&data);
            if verbose { glog!("XMODEM recv block: CRC recv=0x{:04X} calc=0x{:04X}", recv_crc, calc_crc); }
            recv_crc == calc_crc
        }
    };

    if block_complement != !(block_num) {
        if verbose { glog!("XMODEM recv block: FAIL complement mismatch 0x{:02X} != !0x{:02X} (0x{:02X})",
            block_complement, block_num, !(block_num)); }
        return Err("Block complement mismatch".into());
    }
    if !valid {
        return Err("Checksum/CRC error".into());
    }
    if block_num == expected_block.wrapping_sub(1) {
        return Err("Duplicate block".into());
    }
    if block_num != *expected_block {
        if verbose { glog!("XMODEM recv block: FAIL block number 0x{:02X} != expected 0x{:02X}", block_num, *expected_block); }
        return Err("Block number mismatch".into());
    }

    *expected_block = expected_block.wrapping_add(1);
    Ok(data)
}

// =============================================================================
// XMODEM PROTOCOL - SEND (DOWNLOAD)
// =============================================================================

pub(crate) async fn xmodem_send(
    reader: &mut (impl AsyncRead + Unpin),
    writer: &mut (impl AsyncWrite + Unpin),
    data: &[u8],
    is_tcp: bool,
    is_petscii: bool,
    verbose: bool,
    use_1k: bool,
) -> Result<(), String> {
    let cfg = config::get_config();
    let negotiation_timeout = cfg.xmodem_negotiation_timeout;
    let block_timeout = cfg.xmodem_block_timeout;
    let max_retries = cfg.xmodem_max_retries;

    let negotiation_deadline =
        tokio::time::Instant::now() + tokio::time::Duration::from_secs(negotiation_timeout);

    if verbose { glog!("XMODEM send: starting negotiation (is_tcp={}, is_petscii={}, data_len={})",
        is_tcp, is_petscii, data.len()); }

    // Wait for receiver's mode request (C = CRC, NAK = checksum)
    let mode = loop {
        let remaining = negotiation_deadline.duration_since(tokio::time::Instant::now());
        if remaining.is_zero() {
            return Err("Negotiation timeout: start your XMODEM receiver".into());
        }

        match tokio::time::timeout(remaining, raw_read_byte(reader, is_tcp)).await {
            Ok(Ok(byte)) => {
                if verbose { glog!("XMODEM send: negotiation got 0x{:02X}", byte); }
                if is_esc_key(byte, is_petscii) {
                    return Err("Transfer cancelled".into());
                }
                match byte {
                    CRC_REQUEST => {
                        if verbose { glog!("XMODEM send: receiver requests CRC mode"); }
                        break TransferMode::Crc16;
                    }
                    NAK => {
                        if verbose { glog!("XMODEM send: receiver requests Checksum mode"); }
                        break TransferMode::Checksum;
                    }
                    CAN => {
                        return Err("Transfer cancelled by receiver".into());
                    }
                    _ => {
                        if verbose { glog!("XMODEM send: ignoring byte 0x{:02X} during negotiation", byte); }
                        continue;
                    }
                }
            }
            Ok(Err(e)) => return Err(e),
            Err(_) => {
                return Err("Timeout waiting for receiver to start".into());
            }
        }
    };

    // Drain any trailing negotiation bytes (e.g. IMP8 sends 'C' then 'K' for
    // XMODEM-1K; we accepted 'C' but 'K' is still in the buffer).
    // Uses raw_read_byte to properly handle any IAC sequences on TCP.
    tokio::time::sleep(std::time::Duration::from_millis(200)).await;
    while let Ok(Ok(b)) = tokio::time::timeout(
        std::time::Duration::from_millis(50),
        raw_read_byte(reader, is_tcp),
    )
    .await
    {
        if verbose { glog!("XMODEM send: drained negotiation byte 0x{:02X}", b); }
    }

    // Pad data to a 128-byte boundary (the minimum granularity).  When
    // 1K mode is active we consume 1024 bytes per block for full
    // chunks and fall back to 128 for the final partial chunk.
    let mut padded = data.to_vec();
    if padded.is_empty() {
        padded.push(SUB);
    }
    while !padded.len().is_multiple_of(XMODEM_BLOCK_SIZE) {
        padded.push(SUB);
    }

    let mut block_num: u8 = 1;
    // Tracks the runtime 1K preference.  Starts from the caller's
    // intent and flips to false if the first STX block is rejected by
    // the receiver — from then on we stay with SOH for the rest of
    // the transfer.
    let mut use_1k_runtime = use_1k;
    let mut offset = 0usize;
    let mut block_idx = 0usize;
    if verbose { glog!("XMODEM send: data_len={} padded_len={} use_1k={}",
        data.len(), padded.len(), use_1k); }

    while offset < padded.len() {
        // Choose the block size for this iteration: STX (1024) if the
        // runtime flag still permits and we have a full 1024 bytes
        // left; otherwise SOH (128).  This naturally degrades to a
        // partial final SOH block when the file doesn't divide evenly.
        let use_stx = use_1k_runtime
            && padded.len() - offset >= XMODEM_1K_BLOCK_SIZE;
        let block_size = if use_stx { XMODEM_1K_BLOCK_SIZE } else { XMODEM_BLOCK_SIZE };
        let header = if use_stx { STX } else { SOH };
        let block = &padded[offset..offset + block_size];

        let mut retries = 0;
        loop {
            if retries >= max_retries {
                raw_write_bytes(writer, &[CAN, CAN, CAN], is_tcp).await?;
                return Err("Too many retries, transfer aborted".into());
            }

            let mut packet = Vec::with_capacity(3 + block_size + 2);
            packet.push(header);
            packet.push(block_num);
            packet.push(!block_num);
            packet.extend_from_slice(block);

            match mode {
                TransferMode::Checksum => {
                    let checksum = block.iter().fold(0u8, |acc, &b| acc.wrapping_add(b));
                    packet.push(checksum);
                }
                TransferMode::Crc16 => {
                    let crc = crc16_xmodem(block);
                    packet.push((crc >> 8) as u8);
                    packet.push((crc & 0xFF) as u8);
                }
            }

            if block_idx == 0 && retries == 0 && verbose {
                glog!(
                    "XMODEM send: block #1 header=0x{:02X} size={} num=0x{:02X} complement=0x{:02X} packet_len={}",
                    header, block_size, block_num, !block_num, packet.len(),
                );
            }

            raw_write_bytes(writer, &packet, is_tcp).await?;

            // Wait for ACK/NAK
            match tokio::time::timeout(
                std::time::Duration::from_secs(block_timeout),
                raw_read_byte(reader, is_tcp),
            )
            .await
            {
                Ok(Ok(ACK)) => {
                    if verbose && (block_idx < 3 || retries > 0) {
                        glog!("XMODEM send: block #{} ACK (retries={}, size={})",
                            block_idx + 1, retries, block_size);
                    }
                    break;
                }
                Ok(Ok(CAN)) => {
                    if verbose { glog!("XMODEM send: CAN received at block #{}", block_idx + 1); }
                    return Err("Transfer cancelled by receiver".into());
                }
                Ok(Ok(NAK)) => {
                    if verbose { glog!("XMODEM send: block #{} NAK (retry {})", block_idx + 1, retries + 1); }
                    // Opportunistic fallback: if the very first block
                    // we sent used STX and the receiver rejected it,
                    // the receiver probably doesn't support 1K.  Drop
                    // to SOH for the rest of the transfer and retry
                    // with a 128-byte block from the same offset.
                    if use_stx && block_idx == 0 && retries == 0 {
                        if verbose { glog!(
                            "XMODEM send: STX rejected on first block, \
                             falling back to 128-byte SOH"
                        ); }
                        use_1k_runtime = false;
                        break;
                    }
                    retries += 1;
                    continue;
                }
                Ok(Ok(byte)) => {
                    if verbose { glog!("XMODEM send: block #{} unexpected response 0x{:02X} (retry {})",
                        block_idx + 1, byte, retries + 1); }
                    retries += 1;
                    continue;
                }
                Ok(Err(e)) => return Err(e),
                Err(_) => {
                    if verbose { glog!("XMODEM send: block #{} timeout (retry {})", block_idx + 1, retries + 1); }
                    retries += 1;
                    continue;
                }
            }
        }

        // Advance.  If we just fell back from STX to SOH we leave the
        // offset alone and the next loop iteration sends the same
        // payload bytes in a 128-byte SOH block.
        if use_1k_runtime || !use_stx {
            offset += block_size;
            block_idx += 1;
            block_num = block_num.wrapping_add(1);
        }
    }

    // Send EOT and wait for ACK
    for _ in 0..max_retries {
        raw_write_byte(writer, EOT, is_tcp).await?;
        match tokio::time::timeout(
            std::time::Duration::from_secs(block_timeout),
            raw_read_byte(reader, is_tcp),
        )
        .await
        {
            Ok(Ok(ACK)) => return Ok(()),
            Ok(Ok(NAK)) => continue,
            Ok(Ok(b)) => {
                if verbose { glog!("XMODEM send: unexpected EOT response 0x{:02X}, treating as ACK", b); }
                return Ok(());
            }
            Ok(Err(e)) => {
                if verbose { glog!("XMODEM send: read error during EOT: {}", e); }
                return Err(format!("Read error during EOT: {}", e));
            }
            Err(_) => continue,
        }
    }
    if verbose { glog!("XMODEM send: EOT not ACKed after {} retries, assuming success", max_retries); }
    Ok(())
}

// =============================================================================
// XMODEM CRC-16 (CCITT polynomial 0x1021)
// =============================================================================

fn crc16_xmodem(data: &[u8]) -> u16 {
    let mut crc: u16 = 0;
    for &byte in data {
        crc ^= (byte as u16) << 8;
        for _ in 0..8 {
            if crc & 0x8000 != 0 {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc <<= 1;
            }
        }
    }
    crc
}

// =============================================================================
// RAW I/O - TELNET IAC AWARE
// =============================================================================

/// Write a single raw byte, with telnet IAC escaping for TCP connections.
async fn raw_write_byte(
    writer: &mut (impl AsyncWrite + Unpin),
    byte: u8,
    is_tcp: bool,
) -> Result<(), String> {
    if is_tcp && byte == IAC {
        writer
            .write_all(&[IAC, IAC])
            .await
            .map_err(|e| e.to_string())?;
    } else {
        writer
            .write_all(&[byte])
            .await
            .map_err(|e| e.to_string())?;
    }
    writer.flush().await.map_err(|e| e.to_string())?;
    Ok(())
}

/// Write multiple raw bytes, with telnet IAC escaping for TCP connections.
async fn raw_write_bytes(
    writer: &mut (impl AsyncWrite + Unpin),
    data: &[u8],
    is_tcp: bool,
) -> Result<(), String> {
    if is_tcp {
        let mut buf = Vec::with_capacity(data.len() + 8);
        for &byte in data {
            if byte == IAC {
                buf.push(IAC);
            }
            buf.push(byte);
        }
        writer.write_all(&buf).await.map_err(|e| e.to_string())?;
        writer.flush().await.map_err(|e| e.to_string())?;
    } else {
        writer.write_all(data).await.map_err(|e| e.to_string())?;
        writer.flush().await.map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// Read a single raw byte, handling telnet IAC sequences for TCP connections.
async fn raw_read_byte(
    reader: &mut (impl AsyncRead + Unpin),
    is_tcp: bool,
) -> Result<u8, String> {
    let mut buf = [0u8; 1];
    loop {
        reader
            .read_exact(&mut buf)
            .await
            .map_err(|e| e.to_string())?;

        if is_tcp && buf[0] == IAC {
            reader
                .read_exact(&mut buf)
                .await
                .map_err(|e| e.to_string())?;
            if buf[0] == IAC {
                return Ok(IAC);
            }
            consume_telnet_command(reader, buf[0]).await?;
        } else {
            return Ok(buf[0]);
        }
    }
}

/// Consume a telnet command sequence after the IAC and command byte were read.
async fn consume_telnet_command(
    reader: &mut (impl AsyncRead + Unpin),
    command: u8,
) -> Result<(), String> {
    let mut buf = [0u8; 1];
    match command {
        SB => {
            let sb_result = tokio::time::timeout(tokio::time::Duration::from_secs(5), async {
                loop {
                    reader
                        .read_exact(&mut buf)
                        .await
                        .map_err(|e| e.to_string())?;
                    if buf[0] == IAC {
                        reader
                            .read_exact(&mut buf)
                            .await
                            .map_err(|e| e.to_string())?;
                        if buf[0] == SE {
                            break;
                        }
                    }
                }
                Ok::<(), String>(())
            })
            .await;
            match sb_result {
                Err(_) => return Err("Telnet subnegotiation timed out".into()),
                Ok(r) => r?,
            }
        }
        WILL | WONT | DO_CMD | DONT => {
            reader
                .read_exact(&mut buf)
                .await
                .map_err(|e| e.to_string())?;
        }
        _ => {}
    }
    Ok(())
}

// =============================================================================
// TESTS
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_crc16_xmodem() {
        let data = b"123456789";
        assert_eq!(crc16_xmodem(data), 0x31C3);
    }

    #[test]
    fn test_crc16_empty() {
        assert_eq!(crc16_xmodem(&[]), 0x0000);
    }

    #[test]
    fn test_crc16_single_byte() {
        assert_eq!(crc16_xmodem(&[0x00]), 0x0000);
        assert_eq!(crc16_xmodem(&[0xFF]), 0x1EF0);
    }

    /// Run an xmodem_send / xmodem_receive pair over a DuplexStream.
    async fn xmodem_round_trip(original: &[u8]) -> Vec<u8> {
        xmodem_round_trip_mode(original, false).await
    }

    /// Round-trip with the sender's 1K preference controllable.  The
    /// receiver is always prepared to accept both SOH and STX blocks.
    async fn xmodem_round_trip_mode(original: &[u8], use_1k: bool) -> Vec<u8> {
        let (sender_half, receiver_half) = tokio::io::duplex(16384);
        let (mut send_read, mut send_write) = tokio::io::split(sender_half);
        let (mut recv_read, mut recv_write) = tokio::io::split(receiver_half);

        let data = original.to_vec();
        let send_task = tokio::spawn(async move {
            xmodem_send(
                &mut send_read,
                &mut send_write,
                &data,
                false,
                false,
                false,
                use_1k,
            )
            .await
            .unwrap();
        });
        let recv_task = tokio::spawn(async move {
            xmodem_receive(&mut recv_read, &mut recv_write, false, false, false)
                .await
                .unwrap()
        });

        send_task.await.unwrap();
        recv_task.await.unwrap()
    }

    #[tokio::test]
    async fn test_xmodem_round_trip_small() {
        let original = b"Hello, XModem!";
        let received = xmodem_round_trip(original).await;
        assert_eq!(received, original);
    }

    #[tokio::test]
    async fn test_xmodem_round_trip_exact_block() {
        let original: Vec<u8> = (0..128).map(|i| (i & 0xFF) as u8).collect();
        let received = xmodem_round_trip(&original).await;
        assert_eq!(received, original);
    }

    #[tokio::test]
    async fn test_xmodem_round_trip_multi_block() {
        let original: Vec<u8> = (0..448).map(|i| (i % 251) as u8).collect();
        let received = xmodem_round_trip(&original).await;
        assert_eq!(received, original);
    }

    #[tokio::test]
    async fn test_xmodem_round_trip_all_byte_values() {
        let original: Vec<u8> = (0..=255).collect();
        let received = xmodem_round_trip(&original).await;
        assert_eq!(received, original);
    }

    #[tokio::test]
    async fn test_xmodem_round_trip_trailing_sub() {
        let mut original = vec![0x41; 100];
        original.push(SUB);
        original.push(SUB);
        let received = xmodem_round_trip(&original).await;
        assert_eq!(received, vec![0x41; 100]);
    }

    #[tokio::test]
    async fn test_xmodem_round_trip_random_4k() {
        let mut rng: u64 = 0xDEAD_BEEF;
        let original: Vec<u8> = (0..4096)
            .map(|_| {
                rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                (rng >> 33) as u8
            })
            .collect();
        let received = xmodem_round_trip(&original).await;
        assert_eq!(received, original);
    }

    #[tokio::test]
    async fn test_xmodem_round_trip_block_boundary() {
        let original: Vec<u8> = vec![0x55; 256 * XMODEM_BLOCK_SIZE];
        let received = xmodem_round_trip(&original).await;
        assert_eq!(received, original);
    }

    // ─── XMODEM-1K (STX) round-trips ──────────────────────

    #[tokio::test]
    async fn test_xmodem_1k_round_trip_exact_1024() {
        let original: Vec<u8> = (0..XMODEM_1K_BLOCK_SIZE).map(|i| (i & 0xFF) as u8).collect();
        let received = xmodem_round_trip_mode(&original, true).await;
        assert_eq!(received, original);
    }

    #[tokio::test]
    async fn test_xmodem_1k_round_trip_mixed_stx_and_final_soh() {
        // 1024 + 128 partial + few spare bytes to force a mix: one STX
        // block followed by one SOH block.  The receiver transparently
        // handles both headers; the sender degrades to SOH for the
        // sub-1K remainder.
        let original: Vec<u8> = (0..(XMODEM_1K_BLOCK_SIZE + 200))
            .map(|i| ((i * 7) & 0xFF) as u8)
            .collect();
        let received = xmodem_round_trip_mode(&original, true).await;
        assert_eq!(received, original);
    }

    #[tokio::test]
    async fn test_xmodem_1k_round_trip_multi_1k_blocks() {
        // 3 full 1K blocks, no partial.
        let original: Vec<u8> = (0..(3 * XMODEM_1K_BLOCK_SIZE))
            .map(|i| (i & 0xFF) as u8)
            .collect();
        let received = xmodem_round_trip_mode(&original, true).await;
        assert_eq!(received, original);
    }

    #[tokio::test]
    async fn test_xmodem_1k_small_file_still_uses_soh() {
        // Under 1024 bytes: even with use_1k=true, the sender must
        // emit an SOH block (one partial) because STX requires a full
        // 1024-byte payload.
        let original = b"Hello, XMODEM-1K on a short file!";
        let received = xmodem_round_trip_mode(original, true).await;
        assert_eq!(received, original);
    }

    #[tokio::test]
    async fn test_xmodem_1k_round_trip_protocol_bytes_in_data() {
        // Payload contains every protocol byte (SOH/STX/ACK/NAK/CAN/EOT
        // etc.) to verify the 1K path is byte-transparent.
        let mut original: Vec<u8> = Vec::with_capacity(XMODEM_1K_BLOCK_SIZE);
        for i in 0..XMODEM_1K_BLOCK_SIZE {
            original.push((i & 0xFF) as u8);
        }
        let received = xmodem_round_trip_mode(&original, true).await;
        assert_eq!(received, original);
    }

    #[tokio::test]
    async fn test_xmodem_1k_opportunistic_fallback() {
        // Simulate a receiver that doesn't support STX: it reads the
        // STX header byte and NAKs.  Our sender should fall back to
        // SOH for the same offset and complete the transfer with
        // 128-byte blocks.
        //
        // We drive the sender against a handwritten "minimal receiver"
        // that NAKs on STX and ACKs on SOH.  The test just verifies
        // the sender completes without a Too-Many-Retries error.
        let (sender_half, receiver_half) = tokio::io::duplex(16384);
        let (mut send_read, mut send_write) = tokio::io::split(sender_half);
        let (mut recv_read, mut recv_write) = tokio::io::split(receiver_half);

        // 1024-byte file so the sender's first attempt is STX.
        let data: Vec<u8> = (0..XMODEM_1K_BLOCK_SIZE).map(|i| (i & 0xFF) as u8).collect();
        let data_clone = data.clone();

        let send_task = tokio::spawn(async move {
            xmodem_send(
                &mut send_read,
                &mut send_write,
                &data_clone,
                false,
                false,
                false,
                true, // use_1k
            )
            .await
        });

        // Fake receiver: request CRC mode ('C'), then:
        //   - on STX: NAK (rejects XMODEM-1K).
        //   - on SOH: read the rest of the 128-byte block + 2-byte CRC,
        //     ACK.
        //   - on EOT: ACK, done.
        let recv_task = tokio::spawn(async move {
            // Kick off with 'C' for CRC mode.
            raw_write_byte(&mut recv_write, CRC_REQUEST, false).await.unwrap();

            // Block 1 first try: expect STX.
            let hdr1 = raw_read_byte(&mut recv_read, false).await.unwrap();
            assert_eq!(hdr1, STX, "sender should try STX first when use_1k=true");
            // Drain the rest of the 1K packet: num + !num + 1024 bytes + 2 CRC.
            for _ in 0..(2 + XMODEM_1K_BLOCK_SIZE + 2) {
                raw_read_byte(&mut recv_read, false).await.unwrap();
            }
            // NAK the STX block → triggers fallback.
            raw_write_byte(&mut recv_write, NAK, false).await.unwrap();

            // All remaining blocks should be SOH (128-byte each).
            // 1024 bytes / 128 = 8 SOH blocks to cover the same payload.
            for _ in 0..8 {
                let hdr = raw_read_byte(&mut recv_read, false).await.unwrap();
                assert_eq!(hdr, SOH, "fallback should use SOH for the rest");
                for _ in 0..(2 + XMODEM_BLOCK_SIZE + 2) {
                    raw_read_byte(&mut recv_read, false).await.unwrap();
                }
                raw_write_byte(&mut recv_write, ACK, false).await.unwrap();
            }

            // EOT
            let eot = raw_read_byte(&mut recv_read, false).await.unwrap();
            assert_eq!(eot, EOT);
            raw_write_byte(&mut recv_write, ACK, false).await.unwrap();
        });

        // Both tasks should succeed.
        send_task.await.unwrap().unwrap();
        recv_task.await.unwrap();
        let _ = data; // silence unused warning
    }

    #[tokio::test]
    async fn test_xmodem_round_trip_single_byte() {
        let received = xmodem_round_trip(&[0x42]).await;
        assert_eq!(received, vec![0x42]);
    }

    #[tokio::test]
    async fn test_xmodem_round_trip_empty() {
        let received = xmodem_round_trip(&[]).await;
        assert!(received.is_empty());
    }

    #[tokio::test]
    async fn test_xmodem_round_trip_one_over_block() {
        let original: Vec<u8> = (0..129).map(|i| (i & 0xFF) as u8).collect();
        let received = xmodem_round_trip(&original).await;
        assert_eq!(received, original);
    }

    #[tokio::test]
    async fn test_xmodem_round_trip_two_exact_blocks() {
        let original: Vec<u8> = (0..256).map(|i| (i & 0xFF) as u8).collect();
        let received = xmodem_round_trip(&original).await;
        assert_eq!(received, original);
    }

    #[tokio::test]
    async fn test_xmodem_round_trip_data_with_protocol_bytes() {
        let original = vec![SOH, EOT, ACK, NAK, CAN, SUB, 0x00, 0xFF];
        let received = xmodem_round_trip(&original).await;
        assert_eq!(received, original);
    }

    #[test]
    fn test_crc16_full_zero_block() {
        let block = [0u8; XMODEM_BLOCK_SIZE];
        assert_eq!(crc16_xmodem(&block), 0x0000);
    }

    #[test]
    fn test_crc16_full_ff_block() {
        let block = [0xFFu8; XMODEM_BLOCK_SIZE];
        let crc = crc16_xmodem(&block);
        assert_ne!(crc, 0x0000);
        assert_eq!(crc, crc16_xmodem(&[0xFF; XMODEM_BLOCK_SIZE]));
    }

    #[test]
    fn test_crc16_sequential_block() {
        let block: Vec<u8> = (0..128).collect();
        let crc = crc16_xmodem(&block);
        assert_eq!(crc, crc16_xmodem(&(0u8..128).collect::<Vec<u8>>()));
        assert_ne!(crc, 0);
    }

    #[tokio::test]
    async fn test_xmodem_receive_rejects_oversized() {
        let oversized = vec![0xAA; MAX_FILE_SIZE + XMODEM_BLOCK_SIZE];
        let (sender_half, receiver_half) = tokio::io::duplex(16384);
        let (mut send_read, mut send_write) = tokio::io::split(sender_half);
        let (mut recv_read, mut recv_write) = tokio::io::split(receiver_half);

        let send_task = tokio::spawn(async move {
            let _ = xmodem_send(
                &mut send_read,
                &mut send_write,
                &oversized,
                false,
                false,
                false,
                false,
            )
            .await;
        });
        let recv_task = tokio::spawn(async move {
            xmodem_receive(&mut recv_read, &mut recv_write, false, false, false).await
        });

        send_task.await.unwrap();
        let result = recv_task.await.unwrap();
        assert!(result.is_err());
        let err_msg = result.unwrap_err();
        assert!(
            err_msg.contains("8 MB"),
            "Expected '8 MB' in error, got: {}",
            err_msg
        );
    }

    #[test]
    fn test_transfer_timeout_is_reasonable() {
        let cfg = config::get_config();
        assert!(
            cfg.xmodem_negotiation_timeout >= 30,
            "too short — user needs time to start sender"
        );
        assert!(cfg.xmodem_negotiation_timeout <= 300, "excessive negotiation timeout");
    }

    #[test]
    fn test_block_timeout_less_than_negotiation_timeout() {
        let cfg = config::get_config();
        assert!(cfg.xmodem_block_timeout < cfg.xmodem_negotiation_timeout);
    }

    #[test]
    fn test_max_retries_is_reasonable() {
        let cfg = config::get_config();
        assert!(cfg.xmodem_max_retries >= 3, "too few retries");
        assert!(cfg.xmodem_max_retries <= 50, "excessive retries");
    }

    #[tokio::test]
    async fn test_consume_telnet_sb_normal() {
        let data: Vec<u8> = vec![0x18, 0x00, 0x41, IAC, SE];
        let mut reader = std::io::Cursor::new(data);
        let result = consume_telnet_command(&mut reader, SB).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_consume_telnet_sb_long() {
        let mut data: Vec<u8> = Vec::new();
        data.extend(std::iter::repeat_n(0x42, 1000));
        data.push(IAC);
        data.push(SE);
        let mut reader = std::io::Cursor::new(data);
        let result = consume_telnet_command(&mut reader, SB).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_consume_telnet_sb_escaped_iac() {
        let data: Vec<u8> = vec![0x18, IAC, IAC, 0x01, IAC, SE];
        let mut reader = std::io::Cursor::new(data);
        let result = consume_telnet_command(&mut reader, SB).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_consume_telnet_will() {
        let data: Vec<u8> = vec![0x01];
        let mut reader = std::io::Cursor::new(data);
        let result = consume_telnet_command(&mut reader, WILL).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_consume_telnet_unknown_command() {
        let data: Vec<u8> = vec![];
        let mut reader = std::io::Cursor::new(data);
        let result = consume_telnet_command(&mut reader, 0xF1).await;
        assert!(result.is_ok());
    }

    #[test]
    fn test_xmodem_esc_key_petscii_false() {
        assert!(is_esc_key(0x1B, false));
        assert!(!is_esc_key(0x5F, false));
    }

    #[test]
    fn test_xmodem_esc_key_petscii_true() {
        assert!(is_esc_key(0x1B, true));
        assert!(is_esc_key(0x5F, true));
    }
}
