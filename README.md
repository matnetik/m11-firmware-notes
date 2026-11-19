# Leica M11 firmware notes

Reverse-engineering notes and tooling for the **Leica M11's JPEG color pipeline** and the
`.FW` firmware container, worked out from firmware **2.6.4 / 2.1.3** and the M11 Monochrom
**2.6.4** by read-only analysis of the firmware image.

The point is the straight-out-of-camera JPEG: the default color and noise reduction are weak
next to the DNG, and the knobs that could fix it live in a handful of tables inside the
firmware. This documents where those tables are, how the container and its integrity checks
work, and the tools to decompress, edit, and rebuild a valid image.

This repo is the **findings and the tools**, not flashable firmware. See scope below.

---

## ⚠️ Scope and safety — read this

- **No firmware binaries are in this repo, and none will be.** Not Leica's stock image, not
  any modified `.FW`. The method has now been confirmed on one camera (see
  `docs/flashing-results.md`), but any flash can still brick a body if power fails mid-write,
  and a modified flash may affect your warranty. Builds are also ~99.9% Leica's own
  copyrighted code, so distributing them would be a copyright problem.
- **Prefer the low-risk path.** Partial `IMGP` updates (`m11imgp.py`) touch only an image
  parameter block, never the RTOS or bootloader, so a bad value gives wrong colours, not a dead
  camera — and you can always reinstall Leica's exact stock image (`docs/partial-updates.md`).
  Only a full modified `CUST` flash rewrites the RTOS, which is the one with real brick risk, and
  the M11 has **no independent recovery updater** if that ever fails (`docs/updater-internals.md`).
- You already have the firmware if you're working on this — Leica publishes it, and tools
  like REA read it directly. What's shareable and useful is the **method**: where the tables
  live, how the container and hash chain work. That's what this is.
- Nothing here touches a camera. The tools read and rebuild image files on disk only.
- Independent work, **not affiliated with or endorsed by Leica Camera AG.** "Leica" and "M11"
  are trademarks of their owners.

---

## What's here

### `docs/` — the findings
| File | What it covers |
|---|---|
| `color-pipeline.md` | The `.FW` container, the `R2Y` parameter database, and which table holds the color matrix / saturation / contrast / gamma / NR. The core map of the JPEG engine, and what a custom baked-in look can and can't change. |
| `firmware-hash-chain.md` | The inner MD5 manifest that gatekeeps a rebuilt image — the part you **must** repair (per-file + table + outer package) or the camera rejects or mis-reads the file. The hard part. |
| `flashing-results.md` | **Camera-tested results**, what the updater checks, version numbering, the compression limits a build must respect, and the full R2Y table inventory. Read this before building anything. |
| `partial-updates.md` | **The safe way to work (camera-tested).** Flash one parameter block (`IMGP`) in a ~16 KB file with no version bump or RTOS rewrite, and go back to Leica's exact stock image via the header's `+0x34` "from" field. |
| `updater-internals.md` | The updater read from inside the RTOS: where it lives (image #86 @ `0x41000000`), the four integrity checks it runs before writing, and how to emulate its accept/reject decision on a PC with no camera. |
| `filmtune-build.md` | An experimental global tune: the exact table edits and numbers (matte toe on the contrast curves, widened outer saturation steps, a gentle film color matrix). The build itself is not distributed. It has been flashed and is running on one M11 (see `flashing-results.md`). |

### `tools/` — scripts (Python 3, standard library)
All take **your own** stock `.FW`, downloaded from Leica, as input. None is included.
| File | Does |
|---|---|
| `m11fw.py` | Decompress a `.FW` payload to the raw image, and re-compress. |
| `m11build.py` | Edit the color tables and **rebuild a valid image**: repairs the inner MD5 manifest and the outer package MD5, and bumps the build counter so the updater accepts it. Its compressor stays inside Leica's own stream limits (64 KB window, no overlapping copies). Versions before 2026-11-17 did not, so don't use builds from them. |
| `m11imgp.py` | Build a **partial `IMGP` update**: carry a single `img/data/*.bin` parameter block (e.g. `r2y.bin`) in a tiny file that installs in seconds, no version bump, no RTOS rewrite. `list` / `extract` / `build` / `verify`. The low-risk way to iterate on colour. |
| `rebuild_original.py` | Round-trip check: decompress → recompress → confirm byte-identical against the stock payload. |

---

## The short version of the findings

- **Container:** `.FW` = 72-byte header + LZ-compressed payload. The only integrity on the
  outside is a plain MD5 of the payload at `+0x18` — no signature was found.
- **Inner manifest:** the decompressed image has a file table with a per-file MD5 and a table
  MD5. Any edit must repair both, then the outer MD5. `firmware-hash-chain.md` + `m11build.py`.
- **The JPEG look lives in `R2Y`**, a parameter database keyed by `param_id`: color matrix
  (`0x0d`, per ISO band), saturation (`0x2a`), contrast curves (`0x06`), gamma (`0x14`), plus
  NR/sharpening. `color-pipeline.md` has the table.
- **One shared color science.** Standard / Vivid / Natural share the same matrix and curve
  families; there is no per-style hue table. So a firmware edit retunes the shared response —
  it can't hold several discrete color sciences, and can't do grain or halation (no engine
  for them).
- **2.1.3 → 2.6.4** changed no look table; only NR/sharpening gained entries.

---

## Status

- **Camera-confirmed (one M11, Nov 2026):** a repacked stock image and a modified `CUST` build
  install and boot normally (`m11build.py`); **partial `IMGP` updates** flash a single parameter
  block in seconds with no version bump or RTOS rewrite (`m11imgp.py`); and a **downgrade** back
  to Leica's exact stock image works via the header `+0x34` field. See `docs/flashing-results.md`
  and `docs/partial-updates.md`.
- The updater has been read and emulated from inside the RTOS (`docs/updater-internals.md`); the
  R2Y saturation fields were mapped by measured IMGP probes (`docs/color-pipeline.md`).
- Still open: the lens `.shb` shading-grid layout, `ltm.bin` (local-contrast / bloom) behaviour,
  and whether any install-time check exists beyond the MD5s.

Contributions and corrections welcome, especially from anyone decompiling the pipeline in
REA or measuring the JPEG engine against the DNG.

## License

MIT (see `LICENSE`). Covers the original notes and tools only — not any Leica firmware, which
is Leica's. No Leica firmware binary is distributed here.
