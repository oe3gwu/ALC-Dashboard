/**
 * Nominal charge-end voltage per cell (V), aligned with simulator _CHEM charge_end
 * and ChargeProfessional pack max display (type × cells).
 */
const CHARGE_END_V_PER_CELL: Record<number, number> = {
  0x00: 1.45, // NiCd
  0x01: 1.45, // NiMH
  0x02: 4.1, // Li-4.1
  0x03: 4.2, // Li-4.2
  0x04: 2.4, // Pb
  0x05: 3.6, // LiFePO4
  0x06: 4.35, // Li-4.35
  0x07: 1.9, // NiZn
  0x08: 2.45, // AGM/CA
}

/** Theoretical pack max voltage (V) from battery type × cell count. */
export function maxPackVoltageV(batteryType: number, cells: number): number | null {
  const vCell = CHARGE_END_V_PER_CELL[batteryType]
  if (vCell == null || !Number.isFinite(vCell)) return null
  const n = Math.max(1, Math.floor(Number(cells)) || 1)
  return Math.round(vCell * n * 100) / 100
}

export function formatMaxPackVoltage(batteryType: number, cells: number): string {
  const v = maxPackVoltageV(batteryType, cells)
  if (v == null) return '—'
  return `${v.toFixed(2)} V`
}
