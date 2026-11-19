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

## Per-step editing and the saturation fields (measured)

Contrast (`0x06`) and saturation (`0x2a`) store a **separate block per step**, so each of the 7
contrast steps and 8 saturation steps can be edited independently. The contrast-*mode* block (`0x05`)
is a single shared block, so it is global, not per-step.

Each saturation entry is 22 × int16. Changing one field at a time and measuring a ColorChecker
(IMGP-flashed probes, chart shots differenced against stock) gives:

| Field | Effect |
|---|---|
| 4 | overall chroma gain, both axes (434→700 gave ×1.56 on every patch, hue unchanged) |
| 5 | no visible effect |
| 6 | chroma of the brightest tones only (white patch) |
| 8 | a second chroma boost, slight warm-red hue push |
| 11 | **shadow chroma**: raising it enriched dark reds/blues/purples, bright colours unchanged |
| 12 | mid-bright chroma rolloff |
| 13 | **bright chroma rolloff**: lowering it drained yellows and light skin |
| 16/17/18 | toning enable / Cb / Cr. On the B&W step these give a warm or sepia tone (17 ≈ Cb, 18 ≈ Cr). On a colour step, toning makes the image nearly monochrome, so it is not a usable colour tint. |

So each saturation step is effectively a small **saturation-vs-brightness curve** (overall level,
shadow boost, highlight rolloff, top end). There is **no per-hue control** in these tables — the
field that looked hue-selective was luminance-dependent (bright patches happen to be the saturated
ones on a ColorChecker). This matches the "global transforms, no selective 3D-LUT colour" conclusion.

Because these blocks live in `r2y.bin`, all of this is reachable with a partial IMGP update
(`partial-updates.md`): no version bump, no RTOS rewrite, installs in seconds.
