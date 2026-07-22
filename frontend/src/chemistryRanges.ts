/** ELV ALC 8500-2 C/D-Para limits (manual): 10 mV / 0.01 % / integer steps. */

export type ChemRange = {
  min: number
  max: number
  step: number
  /** How to format the live value next to the slider. */
  format: 'mV' | 'dU' | 'int'
}

export const CHEM_RANGES = {
  discharge_NiCd_mV: { min: 800, max: 1100, step: 10, format: 'mV' },
  discharge_NiMH_mV: { min: 800, max: 1100, step: 10, format: 'mV' },
  discharge_LiIon_mV: { min: 2700, max: 3100, step: 10, format: 'mV' },
  discharge_LiPo_mV: { min: 2700, max: 3200, step: 10, format: 'mV' },
  discharge_Pb_mV: { min: 1700, max: 2000, step: 10, format: 'mV' },
  discharge_LiFePO4_mV: { min: 1800, max: 3000, step: 10, format: 'mV' },

  charge_LiIon_mV: { min: 3900, max: 4100, step: 10, format: 'mV' },
  charge_LiPo_mV: { min: 4000, max: 4200, step: 10, format: 'mV' },
  charge_Pb_mV: { min: 2250, max: 2500, step: 10, format: 'mV' },
  charge_LiFePO4_mV: { min: 3400, max: 3800, step: 10, format: 'mV' },

  maintain_LiIon_mV: { min: 3850, max: 4050, step: 10, format: 'mV' },
  maintain_LiPo_mV: { min: 3950, max: 4150, step: 10, format: 'mV' },
  maintain_Pb_mV: { min: 2200, max: 2280, step: 10, format: 'mV' },
  maintain_LiFePO4_mV: { min: 3250, max: 3650, step: 10, format: 'mV' },

  /** Wire: value / 100 = percent (40 → 0.40 %). */
  dU_NiCd: { min: 5, max: 100, step: 1, format: 'dU' },
  dU_NiMH: { min: 5, max: 40, step: 1, format: 'dU' },

  cycles_cycle_NiCd: { min: 2, max: 20, step: 1, format: 'int' },
  cycles_cycle_NiMH: { min: 2, max: 20, step: 1, format: 'int' },
  cycles_form_NiCd: { min: 2, max: 20, step: 1, format: 'int' },
  cycles_form_NiMH: { min: 2, max: 20, step: 1, format: 'int' },

  pause_min: { min: 0, max: 60, step: 1, format: 'int' },
} as const satisfies Record<string, ChemRange>

export type ChemRangeKey = keyof typeof CHEM_RANGES

export function clampChem(key: ChemRangeKey, value: number): number {
  const r = CHEM_RANGES[key]
  if (!Number.isFinite(value)) return r.min
  const stepped = Math.round(value / r.step) * r.step
  return Math.max(r.min, Math.min(r.max, stepped))
}

export function clampChemRecord<T extends Record<string, number>>(obj: T): T {
  const out = { ...obj }
  for (const key of Object.keys(out)) {
    if (key in CHEM_RANGES) {
      ;(out as Record<string, number>)[key] = clampChem(key as ChemRangeKey, Number(out[key]))
    }
  }
  return out
}

export function formatChemValue(key: ChemRangeKey, value: number): string {
  const r = CHEM_RANGES[key]
  const v = clampChem(key, value)
  if (r.format === 'mV') return `${v} mV`
  if (r.format === 'dU') return `${(v / 100).toFixed(2)} %`
  return String(v)
}
