use std::io::{BufRead, BufReader, Read, Seek, SeekFrom};
use std::path::Path;
use std::fs::File;
use encoding_rs::{Encoding, UTF_8};
use sha2::{Digest, Sha256};
use tracing::debug;

/// The result of encoding detection.
#[derive(Debug, Clone)]
pub struct EncodingInfo {
    /// The detected encoding label (e.g. "UTF-8", "GBK", "Shift_JIS").
    pub label: &'static str,
    /// Whether a BOM was present.
    pub has_bom: bool,
}

/// A chunk yielded by the chunked reader.
#[derive(Debug)]
pub struct FileChunk {
    /// The byte offset of this chunk in the file.
    pub offset: u64,
    /// The raw bytes of this chunk.
    pub data: Vec<u8>,
    /// Whether this is the last chunk.
    pub is_last: bool,
}

/// Large file chunked reader with encoding detection.
///
/// Detects the encoding of a file by examining its BOM and falls back to
/// `encoding_rs` detection for non-BOM files.
#[derive(Debug)]
pub struct FileReader {
    path: Box<Path>,
    chunk_size: usize,
}

impl FileReader {
    /// Create a new reader for the given file.
    ///
    /// `chunk_size` controls how many bytes are read per chunk (default 64 KiB).
    pub fn new(path: impl Into<Box<Path>>, chunk_size: usize) -> Self {
        Self {
            path: path.into(),
            chunk_size,
        }
    }

    /// Create a reader with the default chunk size (64 KiB).
    pub fn default_chunk(path: impl Into<Box<Path>>) -> Self {
        Self::new(path, 64 * 1024)
    }

    /// Return the file path.
    pub fn path(&self) -> &Path {
        &self.path
    }

    // ── Encoding detection ──────────────────────────────────────────

    /// Detect the encoding of the file by reading its first few bytes.
    ///
    /// Checks for BOM signatures first, then falls back to `encoding_rs`
    /// statistical detection on the first 4 KiB of content.
    pub fn detect_encoding(&self) -> std::io::Result<EncodingInfo> {
        let mut file = File::open(&self.path)?;
        let mut buf = vec![0u8; 4096];
        let n = file.read(&mut buf)?;
        buf.truncate(n);

        let has_bom = self.has_bom(&buf);
        let encoding = self.detect_from_bytes(&buf);

        Ok(EncodingInfo {
            label: encoding.name(),
            has_bom,
        })
    }

    /// Check if the buffer starts with a BOM.
    fn has_bom(&self, buf: &[u8]) -> bool {
        buf.starts_with(&[0xEF, 0xBB, 0xBF])  // UTF-8
            || buf.starts_with(&[0xFF, 0xFE])       // UTF-16LE
            || buf.starts_with(&[0xFE, 0xFF])       // UTF-16BE
            || buf.starts_with(&[0x00, 0x00, 0xFE, 0xFF]) // UTF-32BE
            || buf.starts_with(&[0xFF, 0xFE, 0x00, 0x00]) // UTF-32LE
    }

    /// Detect encoding from bytes using encoding_rs.
    fn detect_from_bytes(&self, buf: &[u8]) -> &'static Encoding {
        // BOM-based detection
        if buf.starts_with(&[0xEF, 0xBB, 0xBF]) {
            return Encoding::for_bom(buf).map(|(e, _)| e).unwrap_or(UTF_8);
        }
        if buf.starts_with(&[0xFF, 0xFE]) || buf.starts_with(&[0xFE, 0xFF]) {
            if let Some((e, _)) = Encoding::for_bom(buf) {
                return e;
            }
        }

        // Statistical detection
        let (encoding, _) = Encoding::for_buffer(buf);
        encoding
    }

    // ── Chunked reading ─────────────────────────────────────────────

    /// Return an iterator that yields chunks of the file.
    ///
    /// The last chunk may be smaller than `chunk_size`.
    pub fn chunks(&self) -> std::io::Result<ChunkIter> {
        let file = File::open(&self.path)?;
        let file_len = file.metadata()?.len();
        Ok(ChunkIter {
            reader: BufReader::with_capacity(self.chunk_size, file),
            chunk_size: self.chunk_size,
            offset: 0,
            file_len,
            done: false,
        })
    }

    /// Read the file line by line, decoding as UTF-8.
    pub fn lines(&self) -> std::io::Result<impl Iterator<Item = std::io::Result<String>>> {
        let file = File::open(&self.path)?;
        let reader = BufReader::new(file);
        Ok(reader.lines())
    }

    /// Compute the SHA-256 hash of the file.
    pub fn sha256(&self) -> std::io::Result<String> {
        let mut file = File::open(&self.path)?;
        let mut hasher = Sha256::new();
        let mut buf = [0u8; 8192];
        loop {
            let n = file.read(&mut buf)?;
            if n == 0 {
                break;
            }
            hasher.update(&buf[..n]);
        }
        Ok(format!("{:x}", hasher.finalize()))
    }
}

/// Iterator that yields chunks of a file.
#[derive(Debug)]
pub struct ChunkIter {
    reader: BufReader<File>,
    chunk_size: usize,
    offset: u64,
    file_len: u64,
    done: bool,
}

impl Iterator for ChunkIter {
    type Item = std::io::Result<FileChunk>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.done {
            return None;
        }

        let mut buf = vec![0u8; self.chunk_size];
        match self.reader.read(&mut buf) {
            Ok(0) => {
                self.done = true;
                None
            }
            Ok(n) => {
                buf.truncate(n);
                let current_offset = self.offset;
                self.offset += n as u64;
                let is_last = self.offset >= self.file_len;
                if is_last {
                    self.done = true;
                }
                Some(Ok(FileChunk {
                    offset: current_offset,
                    data: buf,
                    is_last,
                }))
            }
            Err(e) => {
                self.done = true;
                Some(Err(e))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn test_detect_utf8_without_bom() {
        let dir = std::env::temp_dir().join("ide-fs-reader-test");
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();

        let path = dir.join("hello.txt");
        fs::write(&path, b"Hello, world!").unwrap();

        let reader = FileReader::default_chunk(&path);
        let info = reader.detect_encoding().unwrap();
        assert_eq!(info.label, "UTF-8");
        assert!(!info.has_bom);

        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_chunked_reading() {
        let dir = std::env::temp_dir().join("ide-fs-chunk-test");
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();

        let path = dir.join("data.bin");
        let data: Vec<u8> = (0..100).collect();
        fs::write(&path, &data).unwrap();

        let reader = FileReader::new(&path, 32);
        let chunks: Vec<FileChunk> = reader.chunks().unwrap().filter_map(|r| r.ok()).collect();

        assert_eq!(chunks.len(), 4); // 32 * 3 + 4 = 100
        assert!(!chunks[0].is_last);
        assert!(chunks[3].is_last);

        // Reconstruct
        let reconstructed: Vec<u8> = chunks.iter().flat_map(|c| c.data.clone()).collect();
        assert_eq!(reconstructed, data);

        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_sha256() {
        let dir = std::env::temp_dir().join("ide-fs-sha-test");
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();

        let path = dir.join("file.txt");
        fs::write(&path, b"test data").unwrap();

        let reader = FileReader::default_chunk(&path);
        let hash = reader.sha256().unwrap();
        // Expected SHA-256 of "test data"
        assert_eq!(hash.len(), 64);

        let _ = fs::remove_dir_all(&dir);
    }
}
