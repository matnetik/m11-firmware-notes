# The updater, from inside the RTOS

Everything in `partial-updates.md` was found by reading and emulating the camera's own update code.
This doc records where that code lives and what it checks, so others can verify or extend it.

## Where the firmware lives

The decompressed image is a packed set of 89 files (`firmware-hash-chain.md`). The interesting ones:

| TOC index | Component | Notes |
|---|---|---|
| 0–65 | lens shading `.shb` | per-lens correction, selected by the 6-bit lens code |
| 68–76 | `img/data/*.bin` | the ISP parameter blocks (IMGP-updatable; see `partial-updates.md`) |
| 80 | **bootloader** | ~36 KB ARM stub; a Socionext *Stubby* loader (its strings include `[stubby]`, `(No security)`). No SD or update logic. |
| 84 | Linux kernel | loaded by Stubby |
| 86 | **main RTOS** | ~30 MB; contains the whole `HSK FW UPD` updater. The SoC is a Socionext Milbeaut (device-tree name SC2000-class; camera codename "Ludwig"). |
| 88 | romfs | UI assets |

**There is no independent recovery updater.** The updater runs inside the main RTOS (#86). The
bootloader can't read a card. The debug menu's "Firmware Fallback" / "Firmware Repair" entries also
call RTOS storage code. So a `CUST` flash that corrupts the RTOS and stops it booting has no
user-reachable way back — which is exactly why `partial-updates.md` prefers IMGP edits (they never
touch the RTOS) and why you keep a stock downgrade file on a card.

## Loading #86 for analysis

The RTOS is a raw ARM image. Its reset code sets the vector base to `0x41000000`
(`LDR r0,=0x41000000 ; MCR p15,0,r0,c12,c0,0`), so load it at that base. String references are
`MOVW`/`MOVT` pairs, not a literal pool. It disassembles cleanly as ARMv7-LE; a headless Ghidra
import at base `0x41000000` resolves the functions below.

## What the updater checks, in order

`HSK_FW_UPDATE_CheckFirmwareFile` runs before anything is written:

1. **Outer header** (`CheckFirmwareFileHeader`): magic `0x2e2caf3e`, header length ≥ 0x40, format word
   `0x10`, `file_size − header_len == payload_size`, end-of-header marker `0xd1d350c1` at `header_len−4`,
   and the payload **MD5** at `+0x18`. The header itself is not hashed.
2. **Decompress** the payload to the image (the hardware `Im_RAW` decoder first, with a "LIMIT OVER"
   error path and a software fallback). Uncompressed length must match.
3. **TOC header MD5** (`CheckFirmwareFileTOCHeader`): inner magic `0x70c4ead3`, table at `0x28`, data
   marker `0xda7ada7a`, and the MD5 of the file table.
4. **Every TOC entry MD5** (`CheckFirmwareFileTOCEntries`): the MD5 of each packed file.

Only if all of that passes does `UpdateDevice` branch on the bundle type (`partial-updates.md`) and
reach `*RUN UPDATE PROCESS*` / `str_if_write_fw_file`. **A corrupt payload is refused before any
write.** The remaining real risk is loss of power during the write of a full `CUST` image.

Version acceptance for `CUST` files is `CheckValidCustomerDeviceUpdate`, decompiled in
`partial-updates.md` (the `+0x34` "from" field is the downgrade lever).

## Emulating it (no camera)

Because the checks are ordinary functions, you can run them on a PC with a CPU emulator (Unicorn):
map #86 at `0x41000000`, point the function at a candidate file in emulated memory, and stub the few
OS calls (logging, timers, the MD5 helper if you prefer). This reproduces the camera's accept/reject
decision exactly, and mutation tests (corrupt a byte, confirm it now rejects) show the harness is
really exercising the check. Every result in `partial-updates.md` was emulated this way first and
then confirmed on the camera — recommended practice before any flash.

## Still open

- Whether the install-time path verifies anything beyond these MD5s (none was found; not proven).
- The lens `.shb` shading-grid layout (header `[256, 78, 52, 8192, …]`, values centred on 8192) and
  whether lens correction also affects the DNG.
- `ltm.bin` behaviour (local-contrast / possible highlight-bloom lever) — under test.
