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
  any modified `.FW`. Builds made with these tools are **untested — never flashed on a
  camera** — and a bad flash can brick the body. They are also ~99.9% Leica's own copyrighted
  code. Distributing them would be both unsafe and a copyright problem.
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
| `filmtune-build.md` | An experimental global tune: the exact table edits and numbers (matte toe on the contrast curves, widened outer saturation steps, a gentle film color matrix). The build itself is not distributed, and has never been flashed. |

### `tools/` — scripts (Python 3, standard library)
All take **your own** stock `.FW`, downloaded from Leica, as input. None is included.
| File | Does |
|---|---|
| `m11fw.py` | Decompress a `.FW` payload to the raw image, and re-compress. |
| `m11build.py` | Edit the color tables and **rebuild a valid image** — repairs the inner MD5 manifest and the outer package MD5, and bumps the build counter so the updater doesn't lock it out. |
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

The table map is from read-only analysis of the firmware image, cross-checked across three
firmwares. The hash-chain repair is implemented and self-verifies, but **has not been
confirmed by an actual flash** — treat a rebuilt image as a hypothesis, not a result. The
tune in `filmtune-build.md` is designed by theory (neutrals preserved, curves monotonic) and
has no test flash behind it.

Contributions and corrections welcome — especially from anyone decompiling the pipeline in
REA or measuring the JPEG engine against the DNG.

## License

MIT (see `LICENSE`). Covers the original notes and tools only — not any Leica firmware, which
is Leica's. No Leica firmware binary is distributed here.
