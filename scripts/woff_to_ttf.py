"""Turn a WOFF 1.0 font into a TrueType file Android can load. Standard library only.

Usage: python scripts/woff_to_ttf.py in.woff out.ttf
Used once to make tv/app/src/main/res/font/fredoka_*.ttf from the @fontsource/fredoka package (OFL-1.1).
"""
import struct
import sys
import zlib


def convert(data: bytes) -> bytes:
    sig, flavor, _length, num, _r, _total, _maj, _min, *_ = struct.unpack(">4sIIHHIHHIIIII", data[:44])
    if sig != b"wOFF":
        raise ValueError("not a WOFF 1.0 file")
    tables = []
    for i in range(num):
        tag, off, clen, olen, csum = struct.unpack(">4sIIII", data[44 + i * 20:64 + i * 20])
        raw = data[off:off + clen]
        if clen < olen:
            raw = zlib.decompress(raw)
        if len(raw) != olen:
            raise ValueError(f"table {tag!r} has the wrong length")
        tables.append((tag, csum, raw))
    tables.sort(key=lambda t: t[0])
    pow2 = 1
    while pow2 * 2 <= num:
        pow2 *= 2
    out = struct.pack(">IHHHH", flavor, num, pow2 * 16, pow2.bit_length() - 1, num * 16 - pow2 * 16)
    offset = 12 + num * 16
    body = b""
    for tag, csum, raw in tables:
        out += struct.pack(">4sIII", tag, csum, offset + len(body), len(raw))
        body += raw + b"\0" * (-len(raw) % 4)
    return out + body


if __name__ == "__main__":
    with open(sys.argv[1], "rb") as f:
        ttf = convert(f.read())
    with open(sys.argv[2], "wb") as f:
        f.write(ttf)
    print(sys.argv[2], len(ttf), "bytes")
