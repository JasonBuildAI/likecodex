use std::fs::File;
use std::io::{BufRead, BufReader, Read};
use std::path::Path;
use encoding_rs::{Encoding, UTF_8};
use sha2::{Digest, Sha256};

#[derive(Debug, Clone)]
pub struct EncodingInfo {
    pub label: &'static str,
    pub has_bom: bool,
}

#[derive(Debug)]
pub struct FileChunk {
    pub offset: u64,
    pub data: Vec<u8>,
    pub is_last: bool,
}

#[derive(Debug)]
pub struct FileReader {
    path: Box<Path>,
    chunk_size: usize,
}

impl FileReader {
    pub fn new(path: impl Into<Box<Path>>, chunk_size: usize) -> Self {
        Self { path: path.into(), chunk_size }
    }

    pub fn default_chunk(path: impl Into<Box<Path>>) -> Self {
        Self::new(path, 64 * 1024)
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn detect_encoding(&self) -> std::io::Result<EncodingInfo> {
        let mut file = File::open(&self.path)?;
        let mut buf = vec![0u8; 4096];
        let n = file.read(&mut buf)?;
        buf.truncate(n);
        let has_bom = self.has_bom(&buf);
        let encoding = Self::detect_from_bytes(&buf);
        Ok(EncodingInfo { label: encoding.name(), has_bom })
    }

    fn has_bom(&self, buf: &[u8]) -> bool {
        buf.starts_with(&[0xEF, 0xBB, 0xBF])
            || buf.starts_with(&[0xFF, 0xFE])
            || buf.starts_with(&[0xFE, 0xFF])
            || buf.starts_with(&[0x00, 0x00, 0xFE, 0xFF])
            || buf.starts_with(&[0xFF, 0xFE, 0x00, 0x00])
    }

    fn detect_from_bytes(buf: &[u8]) -> &'static Encoding {
        if let Some((encoding, _)) = Encoding::for_bom(buf) {
            return encoding;
        }
        UTF_8
    }

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

    pub fn lines(&self) -> std::io::Result<impl Iterator<Item = std::io::Result<String>>> {
        let file = File::open(&self.path)?;
        let reader = BufReader::new(file);
        Ok(reader.lines())
    }

    pub fn sha256(&self) -> std::io::Result<String> {
        let mut file = File::open(&self.path)?;
        let mut hasher = Sha256::new();
        let mut buf = [0u8; 8192];
        loop {
            let n = file.read(&mut buf)?;
            if n == 0 { break; }
            hasher.update(&buf[..n]);
        }
        Ok(format!("{:x}", hasher.finalize()))
    }
}

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
        if self.done { return None; }
        let mut buf = vec![0u8; self.chunk_size];
        match self.reader.read(&mut buf) {
            Ok(0) => { self.done = true; None }
            Ok(n) => {
                buf.truncate(n);
                let current_offset = self.offset;
                self.offset += n as u64;
                let is_last = self.offset >= self.file_len;
                if is_last { self.done = true; }
                Some(Ok(FileChunk { offset: current_offset, data: buf, is_last }))
            }
            Err(e) => { self.done = true; Some(Err(e)) }
        }
    }
}
