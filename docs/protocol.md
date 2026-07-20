# ALC 8500-2 interface protocol (short reference)

Source: ELV user manual chapter 18 + ChargeProfessional 3.x upgrade docs.

## Serial parameters

| Parameter | Value |
|-----------|-------|
| Baud rate | 38400 |
| Data bits | 8 |
| Parity | even |
| Stop bits | 1 |
| Framing | STX `02h` … ETX `03h` |
| Escape | `02/03/05` → `05 12 / 05 13 / 05 15` |

The device never initiates a transfer — the PC always polls.

## Units

| Quantity | Resolution |
|----------|------------|
| Current | 0.1 mA / digit (1 A = 10000) |
| Capacity | 1 mAh = 10000 digits |
| Voltage | 1 mV / digit |
| Temperature | 0.01 °C / digit |

Multi-byte values: **big-endian**.

## Commands

| Cmd | Meaning |
|-----|---------|
| `p` / `P` | Read / set channel parameters |
| `a` / `A` | Read activity / start(0)/stop(1) |
| `m` | Measurements (classic: all channels; FW 2.08: per channel) |
| `t` | Temperatures |
| `d` / `D` | Read / write battery database |
| `v` | Data-logger block (100 samples) |
| `L` | Clear logger for one channel |
| `g` / `G` | Discharge / cycle parameters |
| `h` / `H` | Charge / maintain voltages Li/Pb |
| `j` / `J` | LiFePO4 + backlight / beep / contrast |

Backlight / setup byte in `j`/`J` (mask `0x07`; `ALBEEP_EN=0x08`, `BUBEEP_EN=0x10`):

| Value | Mode |
|------:|------|
| 0 | Off |
| 1 | Always on (protocol only; omitted in dashboard UI) |
| 2 | 1 min |
| 3 | 5 min |
| 4 | 10 min |
| 5 | 30 min |
| 6 | 60 min |

| `u` | Ident: FW field (10) + pad (2) + serial (10) |

### Firmware V2.08 notes (Ident prefix `h`, e.g. serial `WEQ…`)

Verified against ALC 8500-2 Expert hardware:

| Topic | Behavior |
|-------|----------|
| Measurements `m` | Per channel: request `m` + ch; reply `m` + ch + U/I/C (bare `m` often NAK). Client auto-detects vs classic 32-byte all-channel reply. |
| Activity `a` | Often `ch` + `stage` only (no action byte) |
| Battery DB `d`/`D` | 25-byte Cap→Id→Ic entries: trailer is `flags` + `full_factor` + `0xFF` (no forming). Older decode wrongly treated trailer as forming and dropped Vollfaktor (UI showed Aus). |
| Channel `P` Vollfaktor | Off is stored as `0` (API still uses `250` = off); forming current may be floored by device |
| Ident `u` | Pad bytes may be `FFh` instead of `00h`; FW string starts with Ident letter (`h`) |
| Logger `v` | NAK under poll race — client retries after a `p` probe; may lack classic 3-record header |

## Battery types (byte)

| Byte | Name (CP 3.x) |
|------|----------------|
| 00 | NiCd |
| 01 | NiMH |
| 02 | Li-4.1 (Li-Ion) |
| 03 | Li-4.2 (LiPo) |
| 04 | Pb |
| 05 | LiFePO4 |
| 06 | Li-4.35* |
| 07 | NiZn* |
| 08 | AGM/CA* |
| FF | no type |

\* Extensions per CP 3.x — verify on device.

## Programs

00 None · 01 Charge · 02 Discharge · 03 Discharge–Charge · 04 Test · 05 Maintain · 06 Forming · 07 Cycle · 08 Refresh

## ChargeProfessional feature matrix

See [feature-matrix.md](feature-matrix.md) and [devices.md](devices.md). Not available over USB: Ri measurement.

---

# ALC 8000 Plus / ALC 8500 Expert (ELVjournal)

Implementation: `backend/app/protocol/alc8xxx/` — **separate** from the 8500-2 stack.

Source: [ELVjournal 1/06 Teil 7](https://media.elv.com/file/59066_alc8000_alc8500_expert_teil7.pdf).

| Parameter | Value |
|-----------|-------|
| Baud rate | 38400 |
| Data bits | 8 |
| Parity | even |
| Stop bits | 1 |
| Framing | STX `02h` … ETX `03h` (same escape table as 8500-2) |

### Differences from 8500-2

| Topic | 8000 / 8500 Expert | 8500-2 |
|-------|--------------------|--------|
| Channel `P` | no full-factor byte after `flags` | `flags` + `full_factor` |
| Battery types | `00`–`04`, `FF` | + CP 3.x `05`–`08` |
| Device parameters | `g`/`G` only | + `h`/`H`, `j`/`J` |
| Logger | 8500 Expert yes; **8000 no** | yes |
| Channels | 8000: 3; 8500 Expert: 4 | 4 |

Ident prefix (article): `b` = 8500 Expert, `c`/`e` = 8000 / 8000 Plus, `d` = 8500-2 (not handled by this package).

Byte layouts from the article plus differences vs the 8500-2 manual; **hardware unverified**.

---

# ALC 3000 PC (ChargeEasy Teil 2)

Implementation: `backend/app/protocol/alc3000/`.

Source: [ChargeEasy Teil 2 — protocol (PDF)](https://media.elv.com/file/76962_alc3000pc_teil2.pdf).

| Parameter | Value |
|-----------|-------|
| Baud rate | 38400 |
| Framing | STX/ETX + escape as 8500 family |
| Channels | 1 (channel byte always `00h`) |
| Battery types | `00`–`05` (incl. LiFePO), `FF` |
| Full factor | not in `P` frame (API: 250 = off) |

Commands (MVP): `p`/`P`, `a`/`A`, `m`, `t`, `d`/`D`, `v`, `L`, `g`/`G`, `h`/`H`, `j`/`J`, `u`.  
Not in the dashboard: transponder `K`, active DB slot `N`/`n`, ring index `i`, slow read `b`.

---

# ALC 5000 Mobile (ChargeEasy Teil 2, Ident `j`)

Implementation: `backend/app/protocol/alc5000/`. Sources: [`PROTOCOL_SOURCES.md`](../backend/app/protocol/alc5000/PROTOCOL_SOURCES.md).

Source: [ChargeEasy Teil 2 — protocol (PDF)](https://media.elv.com/file/76962_alc3000pc_teil2.pdf) (same article as 3000 PC; model-specific notes for 5000).

| Parameter | Value |
|-----------|-------|
| Baud rate | 38400 |
| Framing | STX/ETX + escape as 8500 family |
| Ident | **`j`** only (FW &gt; 2.00); **`f`** rejected |
| Channels | 2 (profile; PDF: printed − 1) |
| Measurements | `m` + channel (not all-channels like 8500-2) |
| Full factor | yes (`FAh` = off) |
| Activator | FLAGS bit0 |
| RTC | `C`/`c` (6× BCD) — 5000 only |

Not implemented (3000-only in PDF): `K`, `N`/`n`.  
Multi-byte endianness: **assumed big-endian** (not stated in PDF).

---

# ALC 7000 Expert (RS-232)

Implementation: `backend/app/protocol/alc7000/`.

### Protocol origin / licence note

The **wire behaviour** (framing, escape, command set, scales) matches the historical PC protocol as described/implemented in **alc7t.bas** (Frank Steinberg, 2006) and the GPLv2 port **pyALC7T** / `alcrs232.py` (Joachim Siebold).  
Our layer is a **separate reimplementation** (no copy of the Qt UI), wire-compatible. Copyright of the original alc7t / pyALC7T authors remains reserved; this dashboard’s own code is licensed separately (see repository `LICENSE`).

| Parameter | Value |
|-----------|-------|
| Baud rate | 9600 |
| Data bits | 8 |
| Parity | **even** (8E1) |
| Stop bits | 1 |
| Framing | STX `02h` … ETX `03h` |
| Escape | `02/03/05` → `05` + `(byte+10h)` |
| Write ACK | `06h` |
| Channel in frame | 0-based |

### String commands

`STX | cmd | ETX` — reply until ETX (discard control characters):

| Cmd | Meaning |
|-----|---------|
| `v` | Identification |
| `V` | Version |

### Data commands

`STX | cmd | enc(ch) | enc(param…) | ETX`

| Cmd | Meaning | Scale |
|-----|---------|-------|
| `f`/`F` | Program r/w | 0=Charge … 5=Refresh |
| `u`/`U` | Cell count | 1 byte |
| `i`/`I` | Charge current | digits/1000 → A |
| `e`/`E` | Discharge current | digits/1000 → A |
| `k`/`K` | Nominal capacity | digits/100 → Ah |
| `t`/`T` | Battery type | 0=NiCd/NiMH, 1=lead |
| `w` | Measurements | 3×u16: U/1000 V, I/1000 A, C/100 Ah |
| `a` | Channel status | 0=inactive, 1=active |
| `s` | Battery status | 0..3 |
| `h` | Current direction | 0/1/2 |
| `A` | Start/stop | 1=active, 0=inactive |

Dashboard programs/battery types are mapped to these IDs in `mapping.py`. No temperature sensor, no on-device battery DB `d`/`D`.
