# Partial updates and going back to stock (camera-tested)

Two things in this doc are confirmed on a real M11 (firmware 2.6.4, Nov 2026):

1. **Partial ("IMGP") updates** — flash one image-parameter block (e.g. the colour tables) on its
   own, in a ~16 KB file that installs in seconds, without rebuilding or re-flashing the 60 MB image.
2. **A real downgrade** — reinstall Leica's own stock image, with its original version number, even
   though the camera normally refuses anything that isn't newer.

Both are far safer than a full flash and are the recommended way to work.

---

## Partial / IMGP updates

A normal `.FW` carries the whole firmware bundle. Its outer header at `+0x28` holds a 4-byte **bundle
type**. The updater (`HSK_FW_UPDATE_UpdateDevice`) branches on it:

| Type at +0x28 | ASCII | What it does |
|---|---|---|
| `0x43555354` | `CUST` | normal customer update: version check, then write the whole image |
| `0x494d4750` | `IMGP` | **image-parameters update: write only the components in this file, no version check, no RTOS/boot rewrite** |
| `0x54455354` / `0x50524443` / `0x43414c42` | `TEST`/`PRDC`/`CALB` | factory/production/calibration paths |

An **IMGP** file contains a normal decompressed-image container (inner magic `0x70c4ead3`), but its
file table (TOC) has **one entry**: a single `img/data/*.bin` parameter block of type `0x02020001`.
`HSK_FW_UPDATE_UpdateComponents` walks the TOC and writes each component by its type; for an image
parameter file that is one `str_if`-level file write and nothing else.

The editable parameter blocks (from `m11imgp.py list`):

| Component | Size | Holds |
|---|---|---|
| `img/data/r2y.bin` | 53008 | the `R2Y` colour database: colour matrix, contrast curves, saturation, gamma (see `color-pipeline.md`) |
| `img/data/ltm.bin` | 13988 | local tone mapping (local-contrast) tables |
| `img/data/cnr.bin` | 22756 | chroma noise reduction |
| `img/data/sro.bin`, `ela.bin`, `b2b.bin`, `default_sdm.bin` | — | other pipeline stages |

**Why this matters:** a bad value in one of these gives wrong colours, not a camera that fails to
boot — the RTOS and bootloader are untouched — and the update **does not consume a bundle version**,
so you can iterate as many times as you like. On the test camera, an `r2y.bin` IMGP file was offered
on the update screen, installed in a couple of seconds, left `Camera Information` on the same version,
and changed the JPEG colours exactly as the edited tables predicted.

Build one with `tools/m11imgp.py` (`list` → `extract` → edit the block → `build` → `verify`).

## Going back to stock

The bundle version lives at `.FW +0x30` (little-endian; stock 2.6.4 = `0x011a2424`). For a `CUST`
update, `HSK_FW_UPDATE_CheckValidCustomerDeviceUpdate` decides whether to accept it:

- `+0x2c` must equal the camera's device ID.
- **`+0x34` is a "from" version.** If it is `0`, the file's bundle (`+0x30`) must be strictly greater
  than the camera's current bundle — the usual "must be newer" rule.
- **If `+0x34` is non-zero**, the check is only `current >= from` (and `current <= +0x38` when that is
  non-zero). There is **no newer-than test.**

So to reinstall Leica's exact 2.6.4 while on a higher modified version, take Leica's own `.FW`,
unchanged, and set the one header word at `+0x34` to `1`. Its payload is Leica's, so it needs no
recompression, and the camera accepts it from any version. On the test camera this installed and
`Camera Information` went back to reading `2.6.4`. Leica's next official update then installs normally.

This was first worked out by emulating `CheckValidCustomerDeviceUpdate` (see `updater-internals.md`)
and then confirmed on the camera.

## Numbering for modified builds

For `CUST` builds that do bump the version, raise only the **lowest byte** (`…2424` → `…2524` → …).
That keeps the bundle below Leica's next real release, so the official update still counts as newer.
The release label (`+0x3c`, 8-byte slot, `0xAA`-padded) is display text only and the camera never
compares it. IMGP files don't change the version at all, so most day-to-day work never touches it.

## Keep a way back on the card

Before flashing anything, build the stock-downgrade file above and keep it on a card. As long as the
camera still boots, you can always return to Leica's firmware with it. A full modified `CUST` flash is
the only kind that rewrites the RTOS; if one of those fails mid-write, see the risk note in the README.
