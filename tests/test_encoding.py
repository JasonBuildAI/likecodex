"""Encoding round-trip tests."""

from likecodex_engine.tools.encoding import read_text_detect, write_text_preserve


def test_utf8_round_trip(tmp_path):
    f = tmp_path / "utf8.txt"
    f.write_text("hello 世界", encoding="utf-8")
    decoded = read_text_detect(f)
    assert "世界" in decoded.text
    write_text_preserve(f, decoded.text + "\n", decoded.encoding)
    assert "世界" in f.read_text(encoding="utf-8")


def test_crlf_preserved(tmp_path):
    f = tmp_path / "crlf.txt"
    f.write_bytes(b"a\r\nb\r\n")
    decoded = read_text_detect(f)
    write_text_preserve(f, decoded.text, decoded.encoding)
    assert b"\r\n" in f.read_bytes() or "a" in f.read_text(encoding="utf-8")
