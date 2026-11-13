# M11 "Film Tune" — the optional firmware (richer build)

This is the global firmware tuning that sits under the six profiles. It is **optional**:
the profiles alone carry each look with zero flash and full reversibility. This flash
deepens the *foundation* every look sits on. It is JPEG-only — DNG stays raw and neutral.

This build drops the earlier "keep Standard neutral" rule (you don't need a neutral
in-camera JPEG; DNG is your raw), so it reaches further than the first version.

## What it changes

| Shared table | Change |
|---|---|
| Contrast family, **every** slot (−3…+3, **including 0**) | lifted toe → matte, film-like blacks at every contrast step |
| Contrast family, positive slots | softened highlight shoulder (gentle rolloff) |
| Saturation family, outer steps ±2/±3 | widened (+2 more vivid, −2 more muted); step 0 and B&W left stock |
| **CC0 color matrix** (all 4 ISO bands) | **a gentle film color science**: ~5% more saturation with a warm-red / deep-blue lean |
| Gamma, dynamic-range/LTM, B&W toning, sensor tables | **left at stock** (not understood well enough to edit blind, or would tint all B&W) |

The color matrix rows still sum to ~512, so a neutral stays neutral — no global cast.
The per-look magenta fix stays in the profiles, where it was measured against your camera.

### Exact numbers (gain ×4096; CC0 as 3×3 row sums @512)

```
contrast  0  stock @0,128 = 1911,4281   tuned = 2250,4337   (matte toe on neutral)
contrast −1  stock @0      = 2185        tuned = 2739
contrast −2  stock @0      = 3004        tuned = 3695
contrast +2  stock @768    = 4648        tuned = 4628        (softer highlight)
saturation chroma gain:  +2 741→756   +3 818→859   −2 434→419   −3 357→315
CC0 diagonals (band 0, R/G/B self-response @512):  stock 1041/630/595 → tuned 1094/674/640
CC0 row sums every band stay 511–513  (neutrals preserved)
```

## The files (in `filmtune_rich/`)

- **`M11_filmtune_2.6.5.FW`** — the tune. 2,926 bytes changed, every one inside the
  contrast / saturation / CC0 tables or the hash manifest. Version 2.6.5, build counter
  bumped.
- **`M11_revert_stock_2.6.6.FW`** — the stock 2.6.4 payload, re-wrapped as 2.6.6 with a
  higher build counter so it flashes cleanly over the tune and restores stock exactly.

## Integrity (all verified, independently)

| File | Outer package MD5 | Inner hash chain (89 files + table) | CC0 rows neutral | Bytes vs stock |
|---|---|---|---|---|
| `M11_filmtune_2.6.5.FW` | ✅ | ✅ | ✅ | 2,926 |
| `M11_revert_stock_2.6.6.FW` | ✅ | ✅ | — | 0 |

## Honest risk statement

- **The color science is designed by theory, not measured.** There is no test flash. The
  math (neutral preserved, curves monotonic) checks out, but your own frames are the real
  proof. I can update the Look Lab preview so you can *see* the new baseline before deciding.
- It is still **one global color science shared by all six looks**, not six — the per-look
  work stays in the profiles.
- It has **never been flashed on a camera.** If the updater checks something I haven't
  found, the likely outcome is a refused file (harmless). The real risk is a flash that
  starts and fails partway — rare, but the brick scenario.
- If you flash: full battery, freshly formatted card, keep `revert_stock` on the card.
  Your profiles survive a flash (the camera offers to save them first).

A conservative build that leaves Standard/contrast-0 and the color matrix at stock still
exists in `filmtune_fw/` if you ever want the camera's neutral JPEG back without reverting.
