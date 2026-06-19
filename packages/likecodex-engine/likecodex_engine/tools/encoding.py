"""Encoding detection helpers for reading/writing non-UTF-8 files.

LikeCodex targets CJK Windows environments where source files are frequently
stored as GBK / GB18030 or UTF-16. Reading such files as UTF-8 silently
corrupts them, and naively writing back as UTF-8 changes the on-disk encoding.

These helpers detect the original encoding on read and preserve it on write so
the read/edit/write round-trip keeps the file's encoding intact.
"""

from __future__ import annotations

from dataclasses import dataclass

# Ordered list of byte-order marks we recognise. Longer marks first so that a
# UTF-8 BOM is not mistaken for something shorter.
_BOMS: list[tuple[bytes, str]] = [
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
]


@dataclass
class DecodedText:
    """Result of decoding raw bytes with a detected encoding."""

    text: str
    encoding: str
    had_bom: bool


def detect_encoding(raw: bytes) -> str:
    """Return a best-effort encoding name for the given bytes.

    Detection order: BOM -> strict UTF-8 -> UTF-16 heuristic -> GB18030
    (a superset of GBK/GB2312) -> latin-1 fallback (never fails).
    """
    for bom, enc in _BOMS:
        if raw.startswith(bom):
            return enc

    if not raw:
        return "utf-8"

    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # UTF-16 without BOM: a text file dominated by ASCII shows many NUL bytes
    # in one of the two byte positions.
    sample = raw[:4096]
    nul = sample.count(0)
    if nul > len(sample) // 4:
        even_nul = sample[0::2].count(0)
        odd_nul = sample[1::2].count(0)
        return "utf-16-be" if even_nul > odd_nul else "utf-16-le"

    # GB18030 covers GBK and GB2312; try it before giving up.
    try:
        raw.decode("gb18030")
        return "gb18030"
    except UnicodeDecodeError:
        pass

    return "latin-1"


def decode_bytes(raw: bytes) -> DecodedText:
    """Decode bytes using the detected encoding."""
    enc = detect_encoding(raw)
    had_bom = any(raw.startswith(bom) for bom, name in _BOMS if name == enc)
    if enc == "utf-8-sig":
        had_bom = True
    text = raw.decode(enc, errors="replace")
    return DecodedText(text=text, encoding=enc, had_bom=had_bom)


def read_text_detect(path) -> DecodedText:
    """Read a file from disk, detecting its encoding."""
    with open(path, "rb") as handle:
        raw = handle.read()
    return decode_bytes(raw)


def encode_text(text: str, encoding: str) -> bytes:
    """Encode text back to bytes using a previously detected encoding.

    Falls back to UTF-8 if the original encoding cannot represent the new
    content (for example, new non-GBK characters added to a GBK file).
    """
    enc = encoding or "utf-8"
    try:
        return text.encode(enc)
    except (UnicodeEncodeError, LookupError):
        return text.encode("utf-8")


def write_text_preserve(path, text: str, encoding: str) -> str:
    """Write text to disk preserving the given encoding. Returns encoding used."""
    enc = encoding or "utf-8"
    try:
        data = text.encode(enc)
    except (UnicodeEncodeError, LookupError):
        enc = "utf-8"
        data = text.encode("utf-8")
    with open(path, "wb") as handle:
        handle.write(data)
    return enc
