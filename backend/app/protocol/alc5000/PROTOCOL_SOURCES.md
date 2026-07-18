# ALC 5000 Mobile protocol sources

Source PDF: ELVjournal 3/09 “ChargeEasy für das ALC 3000 PC Teil 2”
(local: `ELV_ALC5000_Mobile_Firmware_2x_Datenprotokoll.pdf` / ELV `76962_alc3000pc_teil2.pdf`).

Page mapping: **PDF file page N** = **Journal page (42+N)** (PDF 1 → p.43 … PDF 7 → p.49).

Target device: Ident prefix **`j`** (ALC 5000 mobile, firmware > 2.00). Prefix **`f`** rejected.

| Topic | PDF page | Journal page | Notes |
|-------|----------|--------------|-------|
| Scope FW 2.x / 5000 mobile | 1 | 43 | Shared protocol; model specifics in text |
| Serial 38400 8E1, STX/ETX, escape | 2 | 44 | |
| Channel = printed − 1 | 2 | 44 | Not fixed 0 |
| `p`/`P` field lists | 2–4 | 44–46 | Read includes Messende; write has Vollfaktor |
| Table 1 lengths/scales | 3–4 | 45–46 | |
| FLAGS activator bit0 (5000) | 3 | 45 | |
| Ident `j` / `f` | 4 | 46 | |
| `A`/`a`, `m`+channel, `d`/`D`, `t` | 4 | 46 | |
| Logger `v`, RTC in header (5000 only) | 5 | 47 | |
| `g`/`G`, `h`/`H` + LowBat (5000) | 5 | 47 | |
| `j`/`J` | 5–6 | 47–48 | |
| `u` FW(10)+pad(2)+SN(10) | 6 | 48 | |
| Logger index `i`, clear `L`, helper `b` | 6–7 | 48–49 | |
| RTC `C`/`c` BCD (5000 only) | 7 | 49 | |
| `K`, `N`/`n` | 7 | 49 | **3000 PC only — not implemented** |

## Assumptions (not stated in PDF)

| Item | Assumption | Label in tests |
|------|------------|----------------|
| Multi-byte endian | Big-endian (same digit packing as USB ALC family) | `assumed` |
| Channel count | 2 (project profile; PDF only gives numbering rule) | `assumed` |
| FW > 2.00 check | Ident prefix `j` implies FW > 2.00 per PDF table | PDF-backed mapping |
| Trailing `stage` on `p` read | After Vollfaktor (PDF lists stage only on `a`; same dashboard extension as alc3000/Mock) | `assumed` |
