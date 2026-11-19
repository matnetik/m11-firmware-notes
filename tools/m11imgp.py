#!/usr/bin/env python3
"""Build a partial ("IMGP") Leica M11 firmware update: ONE image-parameter component only.

A full .FW rebuilds and re-flashes the whole 60 MB image. A partial update carries a single
component from the image's file table (one of the `img/data/*.bin` parameter blocks: r2y, ltm,
cnr, sro, ela, b2b, sdm) and nothing else. The camera writes just that file. It does NOT touch
the RTOS, the bootloader or the bundle version, and it installs in a few seconds.

This is the safest kind of edit: a bad parameter value gives wrong colours, not a camera that
won't boot, and the update does not consume a version number.

  python3 -I m11imgp.py list   STOCK.FW
  python3 -I m11imgp.py extract STOCK.FW img/data/r2y.bin r2y.bin
  python3 -I m11imgp.py build   STOCK.FW img/data/r2y.bin edited_r2y.bin out.FW --label 2.6.4a

`out.FW` is YOUR build from YOUR stock file. Flashing it is at your own risk (see README).
Verify it (`verify`) before flashing, and keep a stock-image downgrade file ready
(see docs/partial-updates.md). READ-ONLY to any camera: this only writes files on disk.
"""
import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m11fw  # noqa: E402
import m11build  # noqa: E402

IMGP = 0x494D4750       # bundle type that selects the per-component update path ("IMGP")
IMG_PARAM_TYPE = 0x02020001


def _image(fw):
    img = m11fw.decompress(fw)
    magic, _, tbl, n, tl = struct.unpack_from("<5I", img, 0)
    if magic != 0x70C4EAD3:
        raise SystemExit("not a decompressed M11 image (inner magic mismatch)")
    return img, tbl, n, tbl + tl


def _entries(img, tbl, n, dbase):
    for i in range(n):
        e = tbl + i * 0x38
        typ, = struct.unpack_from("<I", img, e + 4)
        doff, dsz = struct.unpack_from("<II", img, e + 0x18)
        alen, aoff = struct.unpack_from("<II", img, e + 0x30)
        name = img[dbase + aoff:dbase + aoff + alen].rstrip(b"\0").decode("latin1")
        yield i, e, typ, doff, dsz, aoff, alen, name


def cmd_list(path):
    fw = open(path, "rb").read()
    img, tbl, n, dbase = _image(fw)
    print("idx  type        size      name")
    for i, e, typ, doff, dsz, aoff, alen, name in _entries(img, tbl, n, dbase):
        if typ == IMG_PARAM_TYPE:
            print("%3d  0x%08x  %8d  %s" % (i, typ, dsz, name))


def _find(path, want):
    fw = open(path, "rb").read()
    img, tbl, n, dbase = _image(fw)
    for i, e, typ, doff, dsz, aoff, alen, name in _entries(img, tbl, n, dbase):
        if name == want and typ == IMG_PARAM_TYPE:
            return fw, img, tbl, dbase, e, doff, dsz, aoff, alen, name
    raise SystemExit("component %r not found (run `list`)" % want)


def cmd_extract(path, name, out):
    _, img, _, dbase, e, doff, dsz, aoff, alen, nm = _find(path, name)
    open(out, "wb").write(img[dbase + doff:dbase + doff + dsz])
    print("wrote %d bytes of %s to %s" % (dsz, nm, out))


def build(path, name, data_path, out, label):
    fw, img, tbl, dbase, e, doff, dsz, aoff, alen, nm = _find(path, name)
    data = open(data_path, "rb").read()
    if len(data) != dsz:
        raise SystemExit("edited %s is %d bytes, stock is %d (size must match)" % (nm, len(data), dsz))
    if len(label.encode()) > 7:
        raise SystemExit("label must be at most 7 characters (header slot is 8 bytes incl. NUL)")

    lead = img[dbase:dbase + 8]                         # the data section's own 8-byte lead (marker + pad)
    ent = bytearray(img[e:e + 0x38])
    struct.pack_into("<I", ent, 0x18, len(lead))        # this component's data offset
    struct.pack_into("<I", ent, 0x34, len(lead) + len(data))   # path offset, right after the data
    ent[0x20:0x30] = hashlib.md5(data).digest()         # this component's MD5

    hdr = bytearray(img[:0x28])
    struct.pack_into("<I", hdr, 0x0C, 1)                # one TOC entry
    struct.pack_into("<I", hdr, 0x10, 0x38)             # TOC length
    hdr[0x14:0x24] = hashlib.md5(bytes(ent)).digest()   # TOC MD5
    new_img = bytes(hdr) + bytes(ent) + bytes(lead) + data + img[dbase + aoff:dbase + aoff + alen]

    E = fw[0x48]
    payload = bytes([E]) + m11build.compress(new_img, E)
    out_hdr = bytearray(fw[:0x48])
    struct.pack_into("<I", out_hdr, 0x0C, len(new_img))
    struct.pack_into("<I", out_hdr, 0x14, len(payload))
    out_hdr[0x18:0x28] = hashlib.md5(payload).digest()
    out_hdr[0x28:0x2C] = struct.pack("<I", IMGP)        # bundle type -> IMGP (per-component path)
    lab = label.encode() + b"\0"
    out_hdr[0x3C:0x44] = lab + b"\xaa" * (8 - len(lab))  # stock pads the label slot with 0xAA
    open(out, "wb").write(bytes(out_hdr) + payload)
    print("wrote %s (%d bytes, component %s, label %s)" % (out, os.path.getsize(out), nm, label))
    return verify(out, path, name, data)


def verify(out_path, stock_path, name, data=None):
    fw = open(out_path, "rb").read()
    if fw[0x28:0x2C] != struct.pack("<I", IMGP):
        print("FAIL: bundle type is not IMGP"); return False
    ok = hashlib.md5(fw[0x48:]).digest() == fw[0x18:0x28]
    img = m11fw.decompress(fw)
    magic, _, tbl, n, tl = struct.unpack_from("<5I", img, 0)
    dbase = tbl + tl
    ok &= magic == 0x70C4EAD3 and n == 1
    ok &= hashlib.md5(img[tbl:tbl + 0x38]).digest() == img[0x14:0x24]
    ok &= struct.unpack_from("<I", img, dbase)[0] == 0xDA7ADA7A
    o, s = struct.unpack_from("<II", img, tbl + 0x18)
    ok &= hashlib.md5(img[dbase + o:dbase + o + s]).digest() == img[tbl + 0x20:tbl + 0x30]
    if data is not None:
        ok &= img[dbase + o:dbase + o + s] == data
    # compression stays inside the camera's limits (see docs/firmware-hash-chain.md)
    maxD, maxL, overlap = _stream_limits(fw)
    ok &= maxD <= 65534 and maxL <= 65534 and overlap == 0
    print("verify %s: %s (payload MD5, TOC MD5, entry MD5, IMGP type, window<=64KB)" % (out_path, "OK" if ok else "FAIL"))
    return ok


def _stream_limits(fw):
    E = fw[0x48]; Eb = bytes([E]); i = 0x49; n = len(fw); maxD = maxL = ov = 0
    def vi(i):
        v = 0
        while True:
            b = fw[i]; i += 1; v = (v << 7) | (b & 0x7F)
            if not b & 0x80:
                return v, i
    while i < n:
        j = fw.find(Eb, i)
        if j < 0:
            break
        i = j + 1
        L, i = vi(i)
        if L == 0:
            continue
        D, i = vi(i)
        maxD = max(maxD, D); maxL = max(maxL, L); ov += D < L
    return maxD, maxL, ov


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "list":
        cmd_list(a[1])
    elif a[0] == "extract":
        cmd_extract(a[1], a[2], a[3])
    elif a[0] == "build":
        label = a[a.index("--label") + 1] if "--label" in a else "2.6.4a"
        build(a[1], a[2], a[3], a[4], label)
    elif a[0] == "verify":
        verify(a[1], a[2] if len(a) > 2 else None, a[3] if len(a) > 3 else None)
    else:
        print(__doc__)
