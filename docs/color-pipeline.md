# Leica M11 firmware: color pipeline findings

Read-only analysis of M11 2.6.4, M11 2.1.3 and M11 Monochrom 2.6.4. Nothing was modified or flashed.

## Container
- `.FW` = 72-byte header + LZ-compressed payload.
- Header: `+0x0c` decompressed size, `+0x14` payload size, `+0x18` **plain MD5 of payload** (no signature seen in the container), `+0x48` escape byte (differs per build: `0x60`, `0xa1`, `0xa2`).
- Compression: literal bytes; `E, len, dist` back-references; `E, 0` = literal E. Varints are big-endian, 7 bits/byte.
- `m11fw.py` decompresses all three files; output size matches the header exactly.

## Where the look lives
`img/data/R2Y_CC0_CM.bin` → section `R2YS…R2YE` (`img/data/r2y.bin`), a parameter database: directory of entries `[type, len, data_len, data_off, param_id, selectors…]`.

| pid | What it is | Selector |
|---|---|---|
| `0x0d` | **Camera color matrix (CC0)**, 3×3 @ 512 = 1.0, white-preserving | 4 ISO bands (saturation drops at high ISO) |
| `0x2a` | **Saturation** chroma gains; fields 16–18 = **toning enable/Cb/Cr** (unused on color M11) | -3…+3, `10` = B&W |
| `0x06` | **Contrast** gain curves, 1024 × u16 (4096 = 1.0) | -3…+3 (-3 = linear) |
| `0x14` | **Gamma** curve, 256 points → 0…1023 | none |
| `0x18` | RGB→YCbCr (BT.601) | none |
| `0x03` | Secondary 3×3 matrix | none |
| `0x10/0x11/0x1000/0x2000/0x2010` | Noise reduction / sharpening | sensor mode, ISO band, exposure band, -3…+3 |

- Monochrom = same structure; CC0 is the identity matrix, and pid `0x2a` selects toning presets.
- Film styles (Standard / Vivid / Natural / BW Natural / BW High Contrast) each store their own Contrast / Sharpness / Saturation step, which pick entries in these tables. The seven steps likely mean the menu's 5 steps shifted ±1 by the style (inference, not yet confirmed in code).

## Version history
- 2.1.3 → 2.6.4: **no look table changed.** Only the NR/sharpening tables gained entries.
- 2.6's color shift = **"WB Adjustment"** (new strings in 2.6.4): a white-balance fine-tune applied in code, not in these tables.
- Toning existed already in 2.1.3. "HDR Gain Map" is new in 2.6.4.

## What a custom baked-in look can change
CC0 matrix (hue/saturation character), saturation steps, toning Cb/Cr offsets (global tint), contrast curves, gamma. These are global transforms, so no selective 3D-LUT color.
