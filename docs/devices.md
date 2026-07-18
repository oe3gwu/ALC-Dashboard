# Device profiles

The dashboard supports multiple ALC models via **device profiles** (`device_model` in `config.yaml`). Capabilities (channel count, features, protocol) drive the backend and UI.

## Active models

| ID | Label | Channels | Protocol | Notes |
|----|-------|----------|----------|-------|
| `alc3000_pc` | ALC 3000 PC | 1 | USB/STX ChargeEasy | Simulator; hardware untested |
| `alc5000_mobile` | ALC 5000 Mobile | 2 | USB/STX ChargeEasy (Ident `j`) | Simulator; hardware untested |
| `alc7000_expert` | ALC 7000 Expert | 4 | Historical RS-232 PC protocol | 9600 8E1; NiCd/NiMH/Pb |
| `alc8000` | ALC 8000 Plus | 3 | USB/STX ELVjournal | No logger; hardware untested |
| `alc8500_expert` | ALC 8500 Expert | 4 | USB/STX ELVjournal | Simulator; hardware untested |
| `alc8500_2_expert` | ALC 8500-2 Expert | 4 | USB/STX (manual ch. 18) | Default on first start |

### ALC 3000 PC

- Source: [ChargeEasy Teil 2](https://media.elv.com/file/76962_alc3000pc_teil2.pdf).
- Implementation: `backend/app/protocol/alc3000/` (`protocol: alc3000_usb`).
- 1 channel; logger + battery DB; chemistry `g`/`h`/`j`; no full factor; no activator.
- Guided firmware **instructions** (manual §16.5); dashboard does **not** flash.
- Serial: **38400 8E1**. Hardware: **unverified**.

### ALC 5000 Mobile

- Source: same [ChargeEasy Teil 2](https://media.elv.com/file/76962_alc3000pc_teil2.pdf) (FW 2.x / Ident **`j`** only).
- Implementation: `backend/app/protocol/alc5000/` (`protocol: alc5000_usb`) — separate from `alc3000`.
- 2 channels (profile assumption; PDF: printed channel − 1); `m` per channel; Vollfaktor; activator; RTC `C`/`c`; LowBat in `h`.
- Connect gate: `u` → FW field must start with `j`; Ident `f` (FW &lt; 2.00) rejected.
- Guided firmware **instructions** (manual §30.5); dashboard does **not** flash.
- Serial: **38400 8E1**. Hardware: **unverified**.

### ALC 8500-2 Expert

- Public documentation: ELV manual chapter 18 (USB protocol).
- Features: logger, battery DB, chemistry parameters g/h/j, maximum charge, lead activator (channel 2).
- Guided firmware **instructions** (ELV upgrade PDF / Webcode #10073); dashboard does **not** flash.
- Serial: **38400 8E1**.
- Implementation: `backend/app/protocol/` (`alc8500_usb`).

### ALC 8500 Expert / ALC 8000 Plus

- Source: [ELVjournal 1/06 Teil 7](https://media.elv.com/file/59066_alc8000_alc8500_expert_teil7.pdf).
- **Not** the same wire layout as 8500-2 (e.g. no full-factor byte; no `h`/`j`; battery types NiCd…Pb only).
- Implementation: `backend/app/protocol/alc8xxx/` (`protocol: alc8xxx_usb`) — 8500-2 code remains untouched.
- Features: battery DB; chemistry `g`/`G` only; logger on 8500 Expert only; 8000 Plus: 3 channels.
- Guided firmware **instructions** (USB update per manuals; bootloader details from ELV package); no in-app flash.
- Serial: **38400 8E1**.
- Hardware behaviour: **unverified** until a real device is available.

### ALC 7000 Expert

- Classic RS-232 (USB–RS232 adapters may appear as `/dev/ttyUSB*` or `/dev/ttyS*`).
- Wire protocol compatible 1:1 with the historical PC interface (see [protocol.md](protocol.md) — lineage alc7t/pyALC7T).
- Implementation: `backend/app/protocol/alc7000/` (client + simulator speak the same frames).
- No on-device battery DB and no chemistry parameters `g`/`h`/`j`.
- No temperature sensor — UI shows “—”.
- **No** firmware assistant (no documented user USB flash).
- Serial: **9600 8E1**.

## Greyed-out models (visible, not selectable)

| ID | Label | Reason |
|----|-------|--------|
| `alc1800_pc` | ALC 1800 PC | PC datalogger option only; data protocol not publicly documented |
| `alc9000` | ALC 9000 | PC datalogger option only; data protocol not publicly documented |

Shown in Settings as disabled options (`enabled=false`, `protocol=none`).

## Simulator

`simulator: true` (only when `serial_port` is empty).

- Starts the **profile-specific** simulator (label includes `· ×10 Zeit`, e.g. `ALC 8500-2 Expert Simulator · ×10 Zeit`).
- **Shared physics** for all simulators: [`backend/app/services/sim_physics.py`](../backend/app/services/sim_physics.py) — chemistry-aware U/I/Cap (NiCd/NiMH, Li variants, Pb/AGM, LiFePO4, NiZn), CC→CV charge, discharge to cutoff, multi-phase programs.
- Wall clock is **×10 accelerated**; each phase is capped (~20–120 s) so GUI workflows finish in a few minutes. When a program finishes, the channel returns to idle (`running=False`).
- Wire simulators (7000, alc8xxx, alc3000, alc5000) still speak the **real** protocol of their device.
- Port set → simulator off.
- Legacy: `mock: true` → `simulator: true` on load.

## Port

Free-text field (e.g. `/dev/ttyUSB0`, `/dev/ttyACM0`, `/dev/ttyS0`). Empty = auto-detect. Suggestions from `list_ports` as a datalist.

## API

`GET /api/meta` returns `devices[]`, `device_model`, `capabilities` (including `full_factor`, `chemistry_hj`, `logger`, …).
