#!/usr/bin/env python3
"""Build a modified Leica M11 .FW (compressor + header assembler).  READ-ONLY to any camera.

Educational tool for the owner's own M11. It never contacts a camera; it only
writes a .FW file to disk that YOU may choose to flash. Flashing carries brick
risk and voids warranty — that decision and its consequences are yours.

  self-test : python3 -I m11build.py selftest  STOCK.FW
  build     : python3 -I m11build.py tone-test STOCK.FW OUT.FW [--version 2.6.5]

Compression format (verified): literal bytes; E,len,dist = copy; E,0 = literal E.
Varints big-endian, 7 bits/byte, MSB=continue.  E = header byte 0x48.
"""
import array
import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m11fw  # noqa: E402

MIN_MATCH = 4
CHAIN_MAX = 48
MAX_MATCH = 65534      # Leica's own stream never exceeds 65534
WINDOW = 65534         # Leica's stream never references further back than 65534 bytes


def _emit_varint(out, v):
    if v == 0:
        out.append(0)
        return
    groups = []
    while v > 0:
        groups.append(v & 0x7F)
        v >>= 7
    groups.reverse()
    for g in groups[:-1]:
        out.append(g | 0x80)
    out.append(groups[-1])


def compress(data, E):
    n = len(data)
    out = bytearray()
    HBITS = 21
    MASK = (1 << HBITS) - 1
    head = array.array('i', bytes(4 * (1 << HBITS)))   # 0 = empty (stores pos+1)
    prev = array.array('i', bytes(4 * n)) if n else array.array('i')
    mv = memoryview(data)

    def h4(i):
        return (data[i] | data[i + 1] << 8 | data[i + 2] << 16 | data[i + 3] << 24) * 2654435761 >> 11 & MASK

    i = 0
    while i < n:
        best_len, best_dist = 0, 0
        if i + MIN_MATCH <= n:
            hv = h4(i)
            cand = head[hv] - 1
            chain = CHAIN_MAX
            maxl = min(MAX_MATCH, n - i)
            while cand >= 0 and chain:
                dist = i - cand
                if dist > WINDOW:          # stay inside the camera's 64 KB window
                    break
                lim = min(maxl, dist)      # never overlap: Leica's stream has no D < L copies
                if best_len < lim and data[cand + best_len] == data[i + best_len]:   # quick reject
                    l = 0
                    while l < lim and data[cand + l] == data[i + l]:
                        l += 1
                    if l > best_len:
                        best_len, best_dist = l, dist
                        if l >= maxl:
                            break
                cand = prev[cand] - 1
                chain -= 1
        if best_len >= MIN_MATCH:
            out.append(E)
            _emit_varint(out, best_len)
            _emit_varint(out, best_dist)
            end = i + best_len
            while i < end:
                if i + MIN_MATCH <= n:
                    hv = h4(i)
                    prev[i] = head[hv]
                    head[hv] = i + 1
                i += 1
        else:
            b = data[i]
            if b == E:
                out.append(E)
                out.append(0)
            else:
                out.append(b)
            if i + MIN_MATCH <= n:
                hv = h4(i)
                prev[i] = head[hv]
                head[hv] = i + 1
            i += 1
    return bytes(out)


def assemble(stock_fw, decomp, version=None, build_bump=0x00010000):
    """Rebuild a .FW around a modified decompressed image.

    build_bump is added to the internal build counter at 0x30 so the updater
    sees the image as newer than stock. Pass a larger bump for a file meant to
    flash *after* another modified file (e.g. a revert over a tuned image)."""
    E = stock_fw[0x48]
    stream = compress(decomp, E)
    payload = bytes([E]) + stream
    hdr = bytearray(stock_fw[:0x48])
    struct.pack_into("<I", hdr, 0x0C, len(decomp))        # decompressed size
    struct.pack_into("<I", hdr, 0x14, len(payload))       # payload size
    hdr[0x18:0x28] = hashlib.md5(payload).digest()        # payload MD5
    if version:
        asc = version.encode() + b"\0"
        hdr[0x3C:0x3C + len(asc)] = asc
    if build_bump:
        build = struct.unpack_from("<I", hdr, 0x30)[0]   # bump so updater sees it newer
        struct.pack_into("<I", hdr, 0x30, build + build_bump)
    return bytes(hdr) + payload


def locate_bw_toning(stock_fw):
    """Return (abs offset of the B&W saturation entry's toning fields, R2Y start)."""
    decomp = m11fw.decompress(stock_fw)
    blk, r2y_off = m11fw.extract_r2y(decomp)
    for e in m11fw.parse_r2y(blk):
        if e["pid"] == 0x2A and e["sel"] and e["sel"][-1] == 10:
            return decomp, r2y_off + e["doff"] + 16 * 2, e      # fields 16,17,18
    raise SystemExit("B&W saturation entry not found")


def build_looks(stock_path, looks_json, out_dir, base_ver=(2, 6, 5)):
    """Build one committed-look .FW per look. Each overwrites, inside the R2Y
    section only, the shared color matrix + the contrast-0 and saturation-0
    slots, so the camera's Standard style renders that look. Versions increment
    so they can be flashed in sequence without reinstalling stock first."""
    import json
    stock = open(stock_path, "rb").read()
    looks = json.load(open(looks_json))["looks"]
    base = m11fw.decompress(stock)
    blk, r2y_off = m11fw.extract_r2y(base)
    ents = m11fw.parse_r2y(blk)
    cc0 = [e for e in ents if e["pid"] == 0x0D]
    con0 = next(e for e in ents if e["pid"] == 0x06 and e["sel"] and e["sel"][0] == 0)
    sat0 = next(e for e in ents if e["pid"] == 0x2A and e["sel"] and e["sel"][-1] == 0)
    results = []
    for n, (key, L) in enumerate(looks.items()):
        d = bytearray(base)
        fw = L["firmware"]
        regions = []

        def put(entry, values, fmt):
            off = r2y_off + entry["doff"]
            struct.pack_into(fmt % len(values), d, off, *values)
            regions.append((off, off + entry["dlen"]))

        for i, e in enumerate(cc0):
            put(e, fw["pid0x0d_cc0_bands"][i]["v"], "<%dh")
        put(con0, fw["pid0x06_contrast_gain"], "<%dH")
        put(sat0, fw["pid0x2a_sat_entry"], "<%dh")

        ver = "%d.%d.%d" % (base_ver[0], base_ver[1], base_ver[2] + n)
        out = "%s/M11_%s_%s.FW" % (out_dir, key, ver)
        built = assemble(stock, bytes(d), ver)
        open(out, "wb").write(built)
        red = m11fw.decompress(built)
        diffs = [k for k in range(len(base)) if base[k] != red[k]]
        inside = all(any(a <= k < b for a, b in regions) for k in diffs)
        ok = (len(red) == len(base) and inside
              and hashlib.md5(built[0x48:]).digest() == built[0x48 - 0x30:0x48 - 0x20])
        results.append((L["name"], ver, out, len(built), len(diffs), inside,
                        hashlib.md5(built[0x48:]).digest() == built[0x18:0x28]))
        print("%-16s v%s  %.1fMB  changed %d bytes  all-in-color-tables=%s  md5ok=%s  -> %s"
              % (L["name"], ver, len(built) / 1e6, len(diffs), inside,
                 hashlib.md5(built[0x48:]).digest() == built[0x18:0x28], out.split("/")[-1]))
    return results


# ---------------------------------------------------------------------------
# Layer A: ONE global firmware tuning (not six looks).
#
# The owner does not need a neutral in-camera JPEG (DNG stays raw), so the baseline
# itself is made filmic. Still ONE global response shared by every film style; the six
# looks differ by profile. Reshaped:
#   * contrast family (pid 0x06): EVERY slot, 0 included, gets a lifted toe (matte,
#     film-like blacks); positive slots also get a softened highlight shoulder.
#   * saturation family (pid 0x2a): step 0 and the B&W step (10) left stock; the OUTER
#     steps (+-2, +-3) are widened.
#   * CC0 color matrix (pid 0x0d, all ISO bands): a gentle film color science - a bit
#     more saturation with a warm-red / deep-blue lean. Rows keep summing to ~512, so
#     neutrals stay neutral (no global cast); the per-look magenta fix stays in profiles.
#   * B&W toning, gamma, dynamic-range tables: left at stock (toning tints all B&W;
#     gamma/DR tables are not well enough understood to edit blind). Could be a later step.
# This is designed by theory - there is no test flash - so the Look Lab preview and the
# owner's own frames are the real validation. Everything else in the image is stock.
TOE_LIFT = {0: 0.08, -1: 0.14, -2: 0.22, -3: 0.30}  # fraction of headroom added at the deepest toe
SHOULDER = {1: 0.05, 2: 0.08, 3: 0.11}      # fraction of the mid/high boost rolled off
SAT_EXPAND = {1: 1.00, 2: 1.10, 3: 1.18}    # outward scaling of each step's deviation from step 0
GAIN_FLOOR, GAIN_CEIL = 700, 6144           # stay inside Leica's proven range (stock span 819..6139)
# Film color science applied to each CC0 band as new = FILM_CM @ stock. Rows sum to 1.0
# so a neutral (R=G=B) input stays neutral; off-diagonals lean reds warm and blues deep.
FILM_CM = [[1.05, -0.01, -0.04],
           [-0.03, 1.05, -0.02],
           [-0.02, -0.05, 1.07]]


def _raised_cos_down(i, width):
    """1.0 at i=0, smooth cosine falloff to 0.0 at i>=width."""
    import math
    if i >= width:
        return 0.0
    return 0.5 * (1.0 + math.cos(math.pi * i / width))


def _ramp_up(i, start, end=1023):
    """0.0 below start, smooth rise to 1.0 at end."""
    import math
    if i <= start:
        return 0.0
    if i >= end:
        return 1.0
    return 0.5 * (1.0 - math.cos(math.pi * (i - start) / (end - start)))


def reshape_contrast(stock, k):
    """Return a reshaped 1024-entry gain curve for contrast slot k.
    k <= 0 gets a lifted toe (matte blacks); k > 0 gets a softened highlight shoulder."""
    out = list(stock)
    if k <= 0:                                           # lift the toe -> faded blacks
        a, width = TOE_LIFT[k], 220
        for i in range(width):
            f = _raised_cos_down(i, width)
            out[i] = stock[i] + a * f * (GAIN_CEIL - stock[i])
    else:                                                # soften the highlight shoulder
        sh, start = SHOULDER[k], 540
        for i in range(start, 1024):
            r = _ramp_up(i, start)
            boost = stock[i] - 4096.0                     # only pull back where it boosts (>1.0x)
            if boost > 0:
                out[i] = stock[i] - sh * r * boost
    return [int(round(min(GAIN_CEIL, max(GAIN_FLOOR, v)))) for v in out]


def reshape_cc0(v):
    """Apply FILM_CM to one CC0 entry's 3x3 (fields 1..9, @512). Returns a new 16-int list."""
    out = list(v)
    m = [v[1 + r * 3:1 + r * 3 + 3] for r in range(3)]   # stock 3x3
    for r in range(3):
        for c in range(3):
            val = sum(FILM_CM[r][k] * m[k][c] for k in range(3))
            out[1 + r * 3 + c] = int(round(max(-32768, min(32767, val))))
    return out


def reshape_sat(sat, k):
    """Return a reshaped 22-field saturation entry for step k (outer steps only)."""
    s0 = sat[0]
    exp = SAT_EXPAND[abs(k)]
    out = []
    for j in range(22):
        if sat[-3][j] == sat[3][j]:                       # field constant across the family -> leave
            out.append(sat[k][j])
        else:
            v = s0[j] + exp * (sat[k][j] - s0[j])
            out.append(int(round(max(-32768, min(32767, v)))))
    return out


def _transfer_monotonic(gain):
    """Check out(i) = i * gain[i] is non-decreasing (a valid tone response)."""
    prev = -1.0
    for i in range(1024):
        y = i * gain[i]
        if y < prev - 1e-6:
            return False, i
        prev = y
    return True, -1


def fix_manifest(d):
    """Recompute the decompressed image's internal hash chain.

    The image starts with a header (magic, ?, table offset, entry count, table length,
    MD5 of the table at 0x14) followed by a table of 0x38-byte file entries. Each entry
    holds the file's offset (+0x18, relative to the end of the table), its size (+0x1C)
    and the MD5 of its bytes (+0x20). Stock 2.6.4 verifies 89/89. Any edit to a file's
    bytes must update that file's MD5 and then the table MD5, or the chain breaks.
    Returns the byte ranges it rewrote."""
    _, _, tbl_off, n, tbl_len = struct.unpack_from("<5I", d, 0)
    base = tbl_off + tbl_len
    touched = []
    for i in range(n):
        e = tbl_off + i * 0x38
        off, size = struct.unpack_from("<II", d, e + 0x18)
        h = hashlib.md5(bytes(d[base + off:base + off + size])).digest()
        if bytes(d[e + 0x20:e + 0x30]) != h:
            d[e + 0x20:e + 0x30] = h
            touched.append((e + 0x20, e + 0x30))
    th = hashlib.md5(bytes(d[tbl_off:base])).digest()
    if bytes(d[0x14:0x24]) != th:
        d[0x14:0x24] = th
        touched.append((0x14, 0x24))
    return touched


def manifest_ok(d):
    """True when every file MD5 and the table MD5 in the image verify."""
    _, _, tbl_off, n, tbl_len = struct.unpack_from("<5I", d, 0)
    base = tbl_off + tbl_len
    if hashlib.md5(d[tbl_off:base]).digest() != d[0x14:0x24]:
        return False
    for i in range(n):
        e = tbl_off + i * 0x38
        off, size = struct.unpack_from("<II", d, e + 0x18)
        if hashlib.md5(d[base + off:base + off + size]).digest() != d[e + 0x20:e + 0x30]:
            return False
    return True


def build_layer_a(stock_path, out_dir, version="2.6.5", revert_version="2.6.6"):
    import json as _json
    stock = open(stock_path, "rb").read()
    base = m11fw.decompress(stock)
    blk, r2y_off = m11fw.extract_r2y(base)
    ents = m11fw.parse_r2y(blk)
    con = {e["sel"][0]: e for e in ents if e["pid"] == 0x06}
    sat_ent = {e["sel"][-1]: e for e in ents if e["pid"] == 0x2A}
    sat_vals = {k: list(struct.unpack("<22h", e["data"])) for k, e in sat_ent.items()}
    cc0 = [e for e in ents if e["pid"] == 0x0D]

    d = bytearray(base)
    regions, report = [], {"contrast": {}, "saturation": {}, "cc0": []}

    for k, e in con.items():                              # every slot, 0 included
        stock_curve = list(struct.unpack("<1024H", e["data"]))
        new = reshape_contrast(stock_curve, k)
        mono, bad = _transfer_monotonic(new)
        if not mono:
            raise SystemExit("contrast slot %+d not monotonic at idx %d" % (k, bad))
        off = r2y_off + e["doff"]
        struct.pack_into("<1024H", d, off, *new)
        regions.append((off, off + e["dlen"]))
        samp = [0, 128, 256, 512, 768, 1023]
        report["contrast"][k] = {"changed": True,
                                 "stock": [stock_curve[i] for i in samp],
                                 "tuned": [new[i] for i in samp]}

    for k, e in sat_ent.items():
        if k in (0, 10):
            report["saturation"][k] = {"changed": False}
            continue
        new = reshape_sat(sat_vals, k)
        off = r2y_off + e["doff"]
        struct.pack_into("<22h", d, off, *new)
        regions.append((off, off + e["dlen"]))
        report["saturation"][k] = {"changed": True,
                                   "stock_chroma": sat_vals[k][4],
                                   "tuned_chroma": new[4]}

    cc0_rows_ok = True
    for e in cc0:
        v = list(struct.unpack("<16h", e["data"]))
        new = reshape_cc0(v)
        off = r2y_off + e["doff"]
        struct.pack_into("<16h", d, off, *new)
        regions.append((off, off + e["dlen"]))
        rs = [sum(new[1 + r * 3:1 + r * 3 + 3]) for r in range(3)]
        if any(abs(s - 512) > 8 for s in rs):             # neutrals must stay neutral
            cc0_rows_ok = False
        report["cc0"].append({"band": e["sel"],
                              "stock_rows": [sum(v[1 + r * 3:1 + r * 3 + 3]) for r in range(3)],
                              "tuned_rows": rs})

    # --- repair the image's internal hash chain (file MD5 + table MD5) -------
    if not manifest_ok(base):
        raise SystemExit("stock image's hash chain doesn't verify; refusing to build")
    regions += fix_manifest(d)

    # --- assemble tuned image ------------------------------------------------
    tuned = assemble(stock, bytes(d), version, build_bump=0x00010000)
    red = m11fw.decompress(tuned)
    diffs = [i for i in range(len(base)) if base[i] != red[i]]
    inside = all(any(a <= i < b for a, b in regions) for i in diffs)
    md5_ok = hashlib.md5(tuned[0x48:]).digest() == tuned[0x18:0x28]
    size_ok = len(red) == len(base)
    # saturation step-0 and the B&W step stay stock (Standard saturation unchanged)
    sat0_untouched = base[r2y_off + sat_ent[0]["doff"]:r2y_off + sat_ent[0]["doff"] + 44] == \
        red[r2y_off + sat_ent[0]["doff"]:r2y_off + sat_ent[0]["doff"] + 44]

    chain_ok = manifest_ok(red)

    tuned_path = "%s/M11_filmtune_%s.FW" % (out_dir, version)
    open(tuned_path, "wb").write(tuned)

    # --- assemble revert (stock payload, higher build counter) --------------
    revert = assemble(stock, base, revert_version, build_bump=0x00020000)
    rev_red = m11fw.decompress(revert)
    revert_ok = rev_red == base and hashlib.md5(revert[0x48:]).digest() == revert[0x18:0x28]
    revert_path = "%s/M11_revert_stock_%s.FW" % (out_dir, revert_version)
    open(revert_path, "wb").write(revert)

    result = {
        "tuned": {"path": tuned_path, "version": version, "bytes": len(tuned),
                  "bytes_changed": len(diffs), "all_in_target_tables": inside,
                  "md5_ok": md5_ok, "size_ok": size_ok, "sat0_untouched": sat0_untouched,
                  "cc0_rows_neutral": cc0_rows_ok, "internal_hash_chain_ok": chain_ok},
        "revert": {"path": revert_path, "version": revert_version, "bytes": len(revert),
                   "restores_stock_payload": revert_ok},
        "report": report,
    }
    open("%s/layer_a_report.json" % out_dir, "w").write(_json.dumps(result, indent=2))
    print("TUNED  %s" % tuned_path.split("/")[-1])
    print("  %.1f MB  changed %d bytes  all-in-target-tables+hashes=%s  md5_ok=%s  size_ok=%s  sat0 untouched=%s  CC0 rows neutral=%s  internal hash chain=%s"
          % (len(tuned) / 1e6, len(diffs), inside, md5_ok, size_ok, sat0_untouched, cc0_rows_ok, chain_ok))
    for k in sorted(report["contrast"]):
        r = report["contrast"][k]
        if r["changed"]:
            print("  contrast %+d  @0,128,256,512,768,1023  stock=%s  tuned=%s" % (k, r["stock"], r["tuned"]))
    for k in sorted(report["saturation"]):
        r = report["saturation"][k]
        if r["changed"]:
            print("  sat %+d  chroma gain  stock=%d  tuned=%d" % (k, r["stock_chroma"], r["tuned_chroma"]))
    for c in report["cc0"]:
        print("  CC0 band %s  row sums stock=%s  tuned=%s" % (c["band"], c["stock_rows"], c["tuned_rows"]))
    print("REVERT %s  restores exact stock payload=%s" % (revert_path.split("/")[-1], revert_ok))
    all_ok = inside and md5_ok and size_ok and sat0_untouched and cc0_rows_ok and revert_ok and chain_ok
    print("ALL CHECKS PASS" if all_ok else "*** CHECK FAILED ***")
    return result


def selftest(path):
    fw = open(path, "rb").read()
    d = m11fw.decompress(fw)
    print("decompressed %d bytes; compressing (this is the slow step)..." % len(d))
    stream = compress(d, fw[0x48])
    back = m11fw.decompress(bytes(fw[:0x48]) + bytes([fw[0x48]]) + stream)
    ok = back == d
    print("round-trip %s   my payload %d vs Leica %d (%.0f%% of Leica)" % (
        "OK" if ok else "FAILED", len(stream) + 1, len(fw) - 0x48,
        100 * (len(stream) + 1) / (len(fw) - 0x48)))
    return ok


def tone_test(path, out, version):
    stock = open(path, "rb").read()
    decomp, off, e = locate_bw_toning(stock)
    before = struct.unpack_from("<3h", decomp, off)
    d = bytearray(decomp)
    struct.pack_into("<3h", d, off, 1, -40, 24)            # enable, Cb-, Cr+  (warm sepia)
    after = struct.unpack_from("<3h", d, off)
    print("B&W toning fields at decompressed 0x%08x: %s -> %s" % (off, before, after))
    fw = assemble(stock, bytes(d), version)
    open(out, "wb").write(fw)
    # verify round-trip and that ONLY those 6 bytes changed
    red = m11fw.decompress(fw)
    diffs = [k for k in range(len(decomp)) if decomp[k] != red[k]]
    h = m11fw.read_header(fw)
    md5_ok = hashlib.md5(fw[0x48:]).digest() == fw[0x18:0x28]
    print("wrote %s  (%d bytes, %.0f%% of stock)" % (out, len(fw), 100 * len(fw) / len(stock)))
    print("decompresses cleanly: %s   MD5 self-consistent: %s   version string now '%s'" % (
        len(red) == len(decomp), md5_ok, h["version"]))
    print("bytes changed vs stock image: %d  at %s" % (len(diffs), [hex(x) for x in diffs]))
    print("every change inside the 6-byte B&W toning field: %s" % (set(diffs) <= set(range(off, off + 6))))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "selftest":
        selftest(sys.argv[2])
    elif cmd == "tone-test":
        ver = None
        if "--version" in sys.argv:
            ver = sys.argv[sys.argv.index("--version") + 1]
        tone_test(sys.argv[2], sys.argv[3], ver)
    elif cmd == "build-looks":
        build_looks(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "layer-a":
        build_layer_a(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
