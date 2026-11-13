#!/usr/bin/env python3
"""Leica M11 firmware reader (read-only).

Decompresses a Leica M11-family .FW file, extracts the R2Y color-processing
parameter database, and prints the "look" parameters in readable form.

Usage:
  python3 -I m11fw.py decompress LEICA_M11_2.6.4.FW out.bin
  python3 -I m11fw.py r2y        LEICA_M11_2.6.4.FW            # directory summary
  python3 -I m11fw.py looks      LEICA_M11_2.6.4.FW            # matrix / saturation / curves

Format notes (verified on M11 2.1.3, M11 2.6.4, M11 Monochrom 2.6.4):
  Header (0x48 bytes): +0x00 magic 0x2e2caf3e, +0x04 header len 0x48,
    +0x0c decompressed size, +0x14 payload size, +0x18 MD5(payload),
    +0x28 'TSUC', +0x3c version string, +0x48 escape byte E.
  Payload: LZ stream starting at 0x49. Byte != E -> literal.
    E, L(varint), D(varint) -> copy L bytes from D back.  E, 0 -> literal E.
    Varints are big-endian, 7 bits per byte, MSB = continuation. No biases.
"""
import hashlib
import struct
import sys

LOOK_PIDS = {
    0x0D: "CC0 camera color matrix (3x3 @512=1.0, per ISO band)",
    0x2A: "Saturation steps (-3..+3; 10 = B&W) incl. toning Cb/Cr fields 16-18",
    0x06: "Contrast gain curves (-3..+3, 1024 x u16, 4096 = 1.0)",
    0x14: "Gamma curve (256 x u16, 0..1023)",
    0x18: "RGB->YCbCr matrix (BT.601 x256)",
    0x03: "Secondary 3x3 matrix (@512)",
}


def _varint(buf, i):
    v = 0
    while True:
        b = buf[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, i


def read_header(fw):
    magic, hlen, _, dsize, _, psize = struct.unpack_from("<6I", fw, 0)
    return dict(
        magic=magic, hlen=hlen, dsize=dsize, psize=psize,
        md5=fw[0x18:0x28], version=fw[0x3C:0x48].split(b"\0")[0].decode(errors="replace"),
        escape=fw[0x48],
    )


def decompress(fw):
    hdr = read_header(fw)
    E = hdr["escape"]
    Eb = bytes([E])
    out = bytearray()
    i, n = 0x49, len(fw)
    while i < n:
        j = fw.find(Eb, i)
        if j < 0:
            out += fw[i:]
            break
        out += fw[i:j]
        i = j + 1
        L, i = _varint(fw, i)
        if L == 0:
            out.append(E)
            continue
        D, i = _varint(fw, i)
        if D <= 0 or D > len(out):
            raise ValueError("bad back-reference at input 0x%x" % i)
        if D >= L:
            out += out[-D:len(out) - D + L]
        else:
            for _ in range(L):
                out.append(out[-D])
    if len(out) != hdr["dsize"]:
        raise ValueError("size mismatch: got %d, header says %d" % (len(out), hdr["dsize"]))
    return bytes(out)


def extract_r2y(dec):
    a = dec.find(b"UUUUimg/data/R2Y_CC0_CM.bin")
    s = dec.find(b"R2YS", a)
    e = dec.find(b"R2YE", s)
    if a < 0 or s < 0 or e < 0:
        raise ValueError("R2Y section not found")
    return dec[s:e + 4], s


def parse_r2y(blk):
    count = struct.unpack_from("<I", blk, 0x4C)[0]
    o, ents = 0x50, []
    for k in range(count):
        typ, elen = struct.unpack_from("<II", blk, o)
        f = struct.unpack_from("<%dI" % (elen // 4), blk, o)
        sel = [x - (1 << 32) if x >= 1 << 31 else x for x in f[5:]]
        ents.append(dict(idx=k, type=typ, dlen=f[2], doff=f[3], pid=f[4], sel=sel,
                         data=blk[f[3]:f[3] + f[2]]))
        o += elen
    return ents


def _load(path):
    fw = open(path, "rb").read()
    hdr = read_header(fw)
    ok = hashlib.md5(fw[hdr["hlen"]:]).digest() == hdr["md5"]
    return fw, hdr, ok


def cmd_r2y(path):
    fw, hdr, ok = _load(path)
    blk, _ = extract_r2y(decompress(fw))
    ents = parse_r2y(blk)
    print("firmware %s  md5 %s  R2Y %d bytes  %d entries" % (hdr["version"], "OK" if ok else "BAD", len(blk), len(ents)))
    seen = {}
    for e in ents:
        seen.setdefault(e["pid"], []).append(e)
    for pid, es in seen.items():
        print("  pid 0x%04x  n=%3d  dlen=%s  %s" % (pid, len(es), sorted({e["dlen"] for e in es}), LOOK_PIDS.get(pid, "")))


def cmd_looks(path):
    fw, hdr, ok = _load(path)
    ents = parse_r2y(extract_r2y(decompress(fw))[0])
    print("firmware %s (md5 %s)\n" % (hdr["version"], "OK" if ok else "BAD"))
    for e in ents:
        pid, d = e["pid"], e["data"]
        if pid == 0x0D:
            v = struct.unpack("<16h", d)
            m = v[1:10]
            print("CC0 matrix, band %s:" % e["sel"])
            for r in range(3):
                row = m[r * 3:r * 3 + 3]
                print("   [%6d %6d %6d]  = [%6.3f %6.3f %6.3f]  sum %d" % (*row, *(x / 512 for x in row), sum(row)))
        elif pid == 0x2A:
            v = struct.unpack("<22h", d)
            print("Saturation step %+3d: chroma gains %s  aux %s  toning(en,Cb,Cr) %s" % (e["sel"][-1], v[3:7], v[11:14], v[16:19]))
        elif pid == 0x06:
            v = struct.unpack("<1024H", d)
            print("Contrast %+d curve (gain x4096) @0,128,256,512,768,1023: %s" % (e["sel"][0], [v[i] for i in (0, 128, 256, 512, 768, 1023)]))
        elif pid == 0x14:
            v = struct.unpack("<256H", d)
            print("Gamma (256 pts) @0,32,64,128,192,255: %s" % [v[i] for i in (0, 32, 64, 128, 192, 255)])


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "decompress":
        open(sys.argv[3], "wb").write(decompress(open(path, "rb").read()))
        print("wrote", sys.argv[3])
    elif cmd == "r2y":
        cmd_r2y(path)
    elif cmd == "looks":
        cmd_looks(path)
    else:
        print(__doc__)
