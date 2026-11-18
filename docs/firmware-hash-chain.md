# M11 firmware: the inner hash chain

Getting the camera to accept a rebuilt image is the hard part. Beyond the outer package
MD5, the decompressed image carries its own integrity manifest that must be repaired after
any edit, or the camera rejects the update (or reads stale tables).

## Outer container (`.FW`)

72-byte header + LZ-compressed payload:

- `+0x0c` decompressed size
- `+0x14` payload size
- `+0x18` **MD5 of the payload** (no signature beyond this was found in the container)
- `+0x48` escape byte, differs per build (`0x60`, `0xa1`, `0xa2`)

Compression: literal bytes; `E, len, dist` back-references; `E, 0` = a literal `E`. Varints
are big-endian, 7 bits/byte. `m11fw.py` round-trips all three analyzed files to the exact
header size.

## Inner manifest (inside the decompressed image)

The decompressed 2.6.4 image starts with a header:

- magic `0x70c4ead3`
- table offset `0x28`, entry count `89`, table length `0x1378`
- **MD5 of the file table at `0x14`**

The table holds `0x38`-byte entries, one per packed file:

- file offset at `+0x18` (relative to the end of the table)
- size at `+0x1c`
- **MD5 of that file at `+0x20`**

Stock verifies 89/89 and covers 100% of the image. The R2Y color tables are entry **71**
(`0x2c5428`, 53008 bytes).

## What an edit must repair, in order

1. The edited inner file's own MD5 (entry `+0x20`).
2. The file-table MD5 at `+0x14` (it covers the whole table, including step 1).
3. Recompress the payload.
4. The outer payload MD5 at container `+0x18`.

`m11build.py` does all four (`fix_manifest` / `manifest_ok`). An early build missed the
inner chain, so it verified 88/89 — the camera would likely refuse or mis-read it.

## Confirmed on a camera

A stock image rebuilt this way, and a tuned image, both installed on an M11 on 2026-11-17.
The updater checks the TOC header MD5 and every entry MD5 after decompressing and before
writing (see `flashing-results.md`), so this chain really is what gates an update. The
compressed stream must also stay inside Leica's limits (64 KB window, no overlapping copies).
