# Feature matrix: ChargeProfessional → ELV ALC Dashboard

Primarily for **ALC 8500-2 Expert**. Other profiles: see [devices.md](devices.md).

| ChargeProfessional | Status | Notes |
|--------------------|--------|-------|
| Connection manager | yes | Free-text port, auto-detect, **simulator** |
| Multi-device (profiles) | yes | 3000 + 5000 Mobile + 7000 + 8000 Plus + 8500 Expert + 8500-2 |
| Channel overview | yes | Live via WebSocket, `channel_count` from profile |
| Channel window | yes | Detail + chart |
| Start process | yes | Parameter dialog; battery types/programs filtered |
| Safety confirm | yes | Corrections highlighted in red |
| All programs | yes | Per profile |
| Chemistry types CP 3.x | yes (8500-2) | Mapping to verify; 8000/8500 Expert only 00–04 |
| Battery-type parameters | yes | 8500-2: g/h/j; 8000/8500 Expert: g/G only; 7000 hidden |
| Maximum charge | yes (8500-2, 5000) | Capability `full_factor`; hidden on 8000/8500 Expert / 3000 |
| Factory defaults | yes | Restore defaults where chemistry is available |
| Device battery database | yes | Except 7000 |
| Battery DB import/export to ALC | yes | Except 7000 |
| Live monitoring | yes | U/I/C; temp per device; simulator idle ≈ `1.25 V × cells` |
| Data logger | yes | 8500-2 + 8500 Expert; **not** 8000 Plus |
| Charts | yes | uPlot |
| CSV export | yes | `data/logger/` |
| PDF export | yes | In addition to CP |
| Device info | yes | Temp; SN/FW in simulator |
| Firmware update | guided (USB models) | Instructions only — **no in-app flash**; 7000 not enabled |
| Ri measurement | no | Device only |
| Lead activator | yes | Capability; typically channel 2 |
