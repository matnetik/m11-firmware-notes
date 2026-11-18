# M11 firmware: flashing results and what the updater checks

Status as of 2026-11-18. Tested on one M11, starting from Leica firmware 2.6.4.

## Camera results

| Flash | Contents | Hidden version | Label | Result |
|---|---|---|---|---|
| A | Leica's stock 2.6.4 image, repacked by `m11build.py` | 1.26.36.37 | 2.6.4.1 | ✅ installed and boots normally. Camera Information shows 2.6.4.1, and profiles and DNG+JPG work. |
| B | Film tune (`filmtune-build.md`), 2,926 changed bytes in R2Y plus their hashes | 1.26.36.38 | 2.6.4.2 | ✅ installed and boots normally |

So the method in this repo is confirmed on a real camera: window-safe packing, the inner hash-chain repair, the 8-byte label slot and the version bump.

## Compression: stay inside Leica's own limits

Measured on Leica's stock `LEICA_M11_2.6.4.FW` stream:

| | Leica stock | Old `m11build.py` (before this fix) | Current `m11build.py` |
|---|---|---|---|
| Max back-reference distance | **65,534** | ~97,800,000 | 65,534 |
| Max match length | 65,534 | 32,768 | ≤ 65,534 |
| Overlapping copies (distance < length) | **0** | 55,157 | 0 |
| Varint bytes | ≤ 3 | 4 | ≤ 3 |

The camera very likely decompresses through a 64 KB window. The update log names a hardware `Im_RAW` decoder with a "LIMIT OVER" error and a software fallback. **Builds from the old compressor were never flashed and should not be.** They decompress correctly in Python, but they use references Leica's stream never uses. The current `compress()` enforces `WINDOW = 65534`, `MAX_MATCH = 65534`, and never lets a match overlap itself.

Always check a build's stream against these limits before flashing, as well as the payload MD5 and the inner manifest.

## What the updater checks

This comes from the update code's own log strings in the stock image (image file #86, `HSK: FW UPD …`). It's string evidence, not a full decompile.

1. **Header**: magic and an end-of-header marker. The `EOH != ` check is probably on `+0x44`.
2. **Decompress the whole file into RAM**, using the hardware decoder first and software as the fallback. The uncompressed length must match `+0x0C`.
3. **TOC header MD5** (the table MD5 at image `+0x14`), then **every TOC entry's MD5**.
4. **Device ID and serial-range checks**.
5. Only then: `*RUN UPDATE PROCESS*` → `str_if_write_fw_file`.

So a corrupt payload should be refused before anything is written. The remaining hard risk is power loss during the write.

### Version numbers

- `.FW +0x30` (u32) is the **bundle version**, printed `%02i.%02i.%02i.%02i` from its bytes in reverse. Stock 2.6.4 = `0x011a2424` = **1.26.36.36**.
- An update is refused when its bundle version is **equal** ("same version") or **lower** ("old version"). It must be strictly higher.
- `.FW +0x3C` is the **release label**, display text only. The slot is 8 bytes (`0x3C–0x43`) and stock pads it with `0xAA` after the NUL. Don't touch `+0x44–0x47`.
- **Bump only the lowest byte** (`.37`, `.38`, …) so Leica's next official release still counts as newer. Going back to "stock" means flashing the stock image under a *higher* number, because you can't install a lower one. The label can be anything up to 7 characters. The camera never compares labels.

### Other things in the update code

- A debug/service `repair` command reinstalls from an internal firmware copy. Users can't trigger it, so don't count on it as a recovery path.
- A `CustomFW` flag file is read from the card (`Bundle: Type(%s), Version(0x%04X)`). Its purpose isn't known yet.

## R2Y table inventory (stock 2.6.4)

R2Y holds 315 entries across 18 parameter IDs. Several entries can **share one data block**, so editing one changes all of them:

| pid | Entries | Data | Shared? | Notes |
|---|---|---|---|---|
| `0x06` contrast gain curve | 7 (−3…+3) | 1024 × u16 | **separate per step** | Luma gain, 4096 = 1.0 |
| `0x2a` saturation | 8 (−3…+3, 10 = B&W) | 22 × i16 | **separate per step** | Fields 4/5 equal chroma gains (588/588 at step 0). Field 6 is about 0.86 × that. Fields 7–10 are constant (`26, 0, -4, -20`). Fields 11–13 vary by step (e.g. `100, 771, 922`). Fields 16–18 = toning enable/Cb/Cr. |
| `0x05` contrast mode | 7 | 29 × u16 | **one shared block**, so it's global | Luma weights `77/149/29`, a 4096 gain, six `4095` limits |
| `0x0d` CC0 color matrix | 4 ISO bands | 3×3 @512 + extras | separate | |
| `0x14` gamma | 1 | 256 × u16 | | |
| `0x18` RGB→YCbCr | 1 | BT.601 ×256 | | |
| `0x03`, `0x0e`, `0x0f`, `0x19`, `0x29`, `0x04` | 1 each | | | Not decoded yet. `0x29` ends in `360, 668, 976`, possibly hue-related. |
| `0x10/0x11/0x1000/0x2000/0x2010` | ~280 | | some shared | Noise reduction and sharpening by sensor mode / ISO / exposure |

Other ISP table files in the image: `img/data/cnr.bin` (#69), `r2y.bin` (#71), `ela.bin` (#73), `ltm.bin` (#75, local tone mapping). `R2Y_TF_REMAPPING_CM.bin` is named in code but not packed in the image.

## Where this is heading: per-film "slots"

[lukebaze/LeicaM8](https://github.com/lukebaze/LeicaM8) put Kodachrome 64 and Portra 160 into the M8's colour-space slots. Each slot is one 3×3 matrix plus one curve, fitted to Kodak datasheet simulations, and he notes the matrix carries most of each look. The M11 has no per-colour-space matrices, but its **contrast curves and saturation entries are separate per step**. If the saturation entry's extra fields turn out to hold a per-step chroma transform, each film could get its own (contrast step, saturation step) pair, which would be the M11's version of a per-film slot. A probe build that changes one unknown saturation field per step (Standard 0/0 kept stock as the control) is the next experiment.
