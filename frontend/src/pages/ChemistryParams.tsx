import { useCallback, useState, type ReactNode } from 'react'
import { api } from '../api'
import { useCapabilities } from '../capabilities'
import { useLocale } from '../locale'
import {
  CHEM_RANGES,
  clampChem,
  clampChemRecord,
  formatChemValue,
  type ChemRangeKey,
} from '../chemistryRanges'

/**
 * ELV / device factory chemistry — taken from a stock ALC 8500-2 Expert (device read).
 * Li-Ion charge ends at 4.1 V per ELV range; LiPo at 4.2 V.
 */
const ELV_FACTORY_G: Record<string, number> = clampChemRecord({
  discharge_NiCd_mV: 900,
  discharge_NiMH_mV: 1000,
  discharge_LiIon_mV: 3000,
  discharge_LiPo_mV: 3100,
  discharge_Pb_mV: 1850,
  pause_min: 10,
  cycles_cycle_NiCd: 10,
  cycles_cycle_NiMH: 10,
  cycles_form_NiCd: 10,
  cycles_form_NiMH: 5,
  dU_NiCd: 5,
  dU_NiMH: 5,
})

const ELV_FACTORY_H: Record<string, number> = clampChemRecord({
  charge_LiIon_mV: 4100,
  maintain_LiIon_mV: 4050,
  charge_LiPo_mV: 4200,
  maintain_LiPo_mV: 4150,
  charge_Pb_mV: 2360,
  maintain_Pb_mV: 2260,
})

const ELV_FACTORY_J: Record<string, number> = clampChemRecord({
  discharge_LiFePO4_mV: 2300,
  charge_LiFePO4_mV: 3650,
  maintain_LiFePO4_mV: 3450,
})

function pickLiFe(j: Record<string, number | boolean>): Record<string, number> {
  return clampChemRecord({
    discharge_LiFePO4_mV: Number(j.discharge_LiFePO4_mV ?? 0),
    charge_LiFePO4_mV: Number(j.charge_LiFePO4_mV ?? 0),
    maintain_LiFePO4_mV: Number(j.maintain_LiFePO4_mV ?? 0),
  })
}

function ChemSlider({
  label,
  rangeKey,
  value,
  onChange,
}: {
  label: string
  rangeKey: ChemRangeKey
  value: number
  onChange: (v: number) => void
}) {
  const r = CHEM_RANGES[rangeKey]
  const v = clampChem(rangeKey, value)
  return (
    <label className="field field-span-2">
      {label}
      <div className="setup-slider-row">
        <input
          type="range"
          className="setup-slider"
          min={r.min}
          max={r.max}
          step={r.step}
          value={v}
          onChange={(e) => onChange(clampChem(rangeKey, Number(e.target.value)))}
        />
        <span className="setup-slider-value">{formatChemValue(rangeKey, v)}</span>
      </div>
    </label>
  )
}

export function ChemistryParams() {
  const { t } = useLocale()
  const { capabilities } = useCapabilities()
  const showHj = capabilities.chemistry_hj
  const [g, setG] = useState<Record<string, number>>(() => ({ ...ELV_FACTORY_G }))
  const [h, setH] = useState<Record<string, number>>(() => ({ ...ELV_FACTORY_H }))
  const [j, setJ] = useState<Record<string, number>>(() => ({ ...ELV_FACTORY_J }))
  const [fromDevice, setFromDevice] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    const res = await api.deviceParams()
    setG(clampChemRecord({ ...res.g }))
    setH(clampChemRecord({ ...res.h }))
    setJ(pickLiFe(res.j))
    setFromDevice(true)
  }, [])

  const doRead = async () => {
    setErr('')
    setMsg('')
    setBusy(true)
    try {
      await load()
      setMsg('')
    } catch (e) {
      setErr(String((e as Error).message || e))
      setFromDevice(false)
    } finally {
      setBusy(false)
    }
  }

  const doApply = async () => {
    setErr('')
    setMsg('')
    setBusy(true)
    try {
      const cg = clampChemRecord({ ...g })
      const ch = clampChemRecord({ ...h })
      const cj = clampChemRecord({ ...j })
      setG(cg)
      setH(ch)
      setJ(cj)
      await api.putG({
        discharge_NiCd_mV: cg.discharge_NiCd_mV,
        discharge_NiMH_mV: cg.discharge_NiMH_mV,
        discharge_LiIon_mV: cg.discharge_LiIon_mV,
        discharge_LiPo_mV: cg.discharge_LiPo_mV,
        discharge_Pb_mV: cg.discharge_Pb_mV,
        pause_min: cg.pause_min,
        cycles_cycle_NiCd: cg.cycles_cycle_NiCd,
        cycles_cycle_NiMH: cg.cycles_cycle_NiMH,
        cycles_form_NiCd: cg.cycles_form_NiCd,
        cycles_form_NiMH: cg.cycles_form_NiMH,
        dU_NiCd: cg.dU_NiCd,
        dU_NiMH: cg.dU_NiMH,
      })
      if (showHj) {
        await api.putH({
          charge_LiIon_mV: ch.charge_LiIon_mV,
          maintain_LiIon_mV: ch.maintain_LiIon_mV,
          charge_LiPo_mV: ch.charge_LiPo_mV,
          maintain_LiPo_mV: ch.maintain_LiPo_mV,
          charge_Pb_mV: ch.charge_Pb_mV,
          maintain_Pb_mV: ch.maintain_Pb_mV,
        })
        // Preserve device display/setup bytes that share the j frame.
        const cur = await api.deviceParams()
        await api.putJ({
          discharge_LiFePO4_mV: cj.discharge_LiFePO4_mV,
          charge_LiFePO4_mV: cj.charge_LiFePO4_mV,
          maintain_LiFePO4_mV: cj.maintain_LiFePO4_mV,
          illumination: cur.j.illumination,
          alarm_beep: cur.j.alarm_beep,
          button_beep: cur.j.button_beep,
          contrast: cur.j.contrast,
        })
      }
      setMsg(t('chem.applyOk'))
      await load()
    } catch (e) {
      setErr(String((e as Error).message || e))
    } finally {
      setBusy(false)
    }
  }

  const loadPreset = (
    gPreset: Record<string, number>,
    hPreset: Record<string, number>,
    jPreset: Record<string, number>,
    okKey: 'chem.factoryOk',
  ) => {
    setErr('')
    setG(clampChemRecord({ ...gPreset }))
    setH(clampChemRecord({ ...hPreset }))
    setJ(clampChemRecord({ ...jPreset }))
    setFromDevice(false)
    setMsg(t(okKey))
  }

  const doElvFactory = () => loadPreset(ELV_FACTORY_G, ELV_FACTORY_H, ELV_FACTORY_J, 'chem.factoryOk')

  const setGKey = (key: ChemRangeKey, v: number) => setG((prev) => ({ ...prev, [key]: v }))
  const setHKey = (key: ChemRangeKey, v: number) => setH((prev) => ({ ...prev, [key]: v }))
  const setJKey = (key: ChemRangeKey, v: number) => setJ((prev) => ({ ...prev, [key]: v }))

  const typePanel = (title: string, fields: ReactNode) => (
    <div className="panel">
      <h2>{title}</h2>
      <div className="form-grid">{fields}</div>
    </div>
  )

  const actionButtons = (
    <div className="panel">
      <div className="row chem-actions">
        <button type="button" onClick={doRead} disabled={busy}>
          {t('chem.read')}
        </button>
        <button type="button" className="primary-danger" onClick={doApply} disabled={busy}>
          {t('chem.apply')}
        </button>
        <button type="button" onClick={doElvFactory} disabled={busy}>
          {t('chem.factory')}
        </button>
      </div>
    </div>
  )

  return (
    <>
      <h1>{t('chem.title')}</h1>
      <p className="lead">{t('chem.lead')}</p>

      <div className="toast error" role="alert">
        {t('chem.warningAdvanced')}
      </div>
      {fromDevice ? (
        <div className="toast ok" role="status">
          {t('chem.fromDevice')}
        </div>
      ) : (
        <div className="toast" role="status">
          {t('chem.warningDefaults')}
        </div>
      )}

      {msg && <div className="toast ok">{msg}</div>}
      {err && <div className="toast error">{err}</div>}

      {actionButtons}

      {typePanel(
        t('chem.groupNiCd'),
        <>
          <ChemSlider
            label={t('chem.dischargeCutoff')}
            rangeKey="discharge_NiCd_mV"
            value={g.discharge_NiCd_mV}
            onChange={(v) => setGKey('discharge_NiCd_mV', v)}
          />
          <ChemSlider
            label={t('chem.dU')}
            rangeKey="dU_NiCd"
            value={g.dU_NiCd}
            onChange={(v) => setGKey('dU_NiCd', v)}
          />
          <ChemSlider
            label={t('chem.cyclesCycle')}
            rangeKey="cycles_cycle_NiCd"
            value={g.cycles_cycle_NiCd}
            onChange={(v) => setGKey('cycles_cycle_NiCd', v)}
          />
          <ChemSlider
            label={t('chem.cyclesForm')}
            rangeKey="cycles_form_NiCd"
            value={g.cycles_form_NiCd}
            onChange={(v) => setGKey('cycles_form_NiCd', v)}
          />
        </>,
      )}

      {typePanel(
        t('chem.groupNiMH'),
        <>
          <ChemSlider
            label={t('chem.dischargeCutoff')}
            rangeKey="discharge_NiMH_mV"
            value={g.discharge_NiMH_mV}
            onChange={(v) => setGKey('discharge_NiMH_mV', v)}
          />
          <ChemSlider
            label={t('chem.dU')}
            rangeKey="dU_NiMH"
            value={g.dU_NiMH}
            onChange={(v) => setGKey('dU_NiMH', v)}
          />
          <ChemSlider
            label={t('chem.cyclesCycle')}
            rangeKey="cycles_cycle_NiMH"
            value={g.cycles_cycle_NiMH}
            onChange={(v) => setGKey('cycles_cycle_NiMH', v)}
          />
          <ChemSlider
            label={t('chem.cyclesForm')}
            rangeKey="cycles_form_NiMH"
            value={g.cycles_form_NiMH}
            onChange={(v) => setGKey('cycles_form_NiMH', v)}
          />
        </>,
      )}

      {typePanel(
        t('chem.groupLi41'),
        <>
          <ChemSlider
            label={t('chem.dischargeCutoff')}
            rangeKey="discharge_LiIon_mV"
            value={g.discharge_LiIon_mV}
            onChange={(v) => setGKey('discharge_LiIon_mV', v)}
          />
          {showHj && (
            <>
              <ChemSlider
                label={t('chem.chargeVoltage')}
                rangeKey="charge_LiIon_mV"
                value={h.charge_LiIon_mV}
                onChange={(v) => setHKey('charge_LiIon_mV', v)}
              />
              <ChemSlider
                label={t('chem.maintainVoltage')}
                rangeKey="maintain_LiIon_mV"
                value={h.maintain_LiIon_mV}
                onChange={(v) => setHKey('maintain_LiIon_mV', v)}
              />
            </>
          )}
        </>,
      )}

      {typePanel(
        t('chem.groupLi42'),
        <>
          <ChemSlider
            label={t('chem.dischargeCutoff')}
            rangeKey="discharge_LiPo_mV"
            value={g.discharge_LiPo_mV}
            onChange={(v) => setGKey('discharge_LiPo_mV', v)}
          />
          {showHj && (
            <>
              <ChemSlider
                label={t('chem.chargeVoltage')}
                rangeKey="charge_LiPo_mV"
                value={h.charge_LiPo_mV}
                onChange={(v) => setHKey('charge_LiPo_mV', v)}
              />
              <ChemSlider
                label={t('chem.maintainVoltage')}
                rangeKey="maintain_LiPo_mV"
                value={h.maintain_LiPo_mV}
                onChange={(v) => setHKey('maintain_LiPo_mV', v)}
              />
            </>
          )}
        </>,
      )}

      {typePanel(
        t('chem.groupPb'),
        <>
          <ChemSlider
            label={t('chem.dischargeCutoff')}
            rangeKey="discharge_Pb_mV"
            value={g.discharge_Pb_mV}
            onChange={(v) => setGKey('discharge_Pb_mV', v)}
          />
          {showHj && (
            <>
              <ChemSlider
                label={t('chem.chargeVoltage')}
                rangeKey="charge_Pb_mV"
                value={h.charge_Pb_mV}
                onChange={(v) => setHKey('charge_Pb_mV', v)}
              />
              <ChemSlider
                label={t('chem.maintainVoltage')}
                rangeKey="maintain_Pb_mV"
                value={h.maintain_Pb_mV}
                onChange={(v) => setHKey('maintain_Pb_mV', v)}
              />
            </>
          )}
        </>,
      )}

      {showHj &&
        typePanel(
          t('chem.groupLiFe'),
          <>
            <ChemSlider
              label={t('chem.dischargeCutoff')}
              rangeKey="discharge_LiFePO4_mV"
              value={j.discharge_LiFePO4_mV}
              onChange={(v) => setJKey('discharge_LiFePO4_mV', v)}
            />
            <ChemSlider
              label={t('chem.chargeVoltage')}
              rangeKey="charge_LiFePO4_mV"
              value={j.charge_LiFePO4_mV}
              onChange={(v) => setJKey('charge_LiFePO4_mV', v)}
            />
            <ChemSlider
              label={t('chem.maintainVoltage')}
              rangeKey="maintain_LiFePO4_mV"
              value={j.maintain_LiFePO4_mV}
              onChange={(v) => setJKey('maintain_LiFePO4_mV', v)}
            />
          </>,
        )}

      {typePanel(
        t('chem.groupGeneral'),
        <>
          <ChemSlider
            label={t('chem.pauseMin')}
            rangeKey="pause_min"
            value={g.pause_min}
            onChange={(v) => setGKey('pause_min', v)}
          />
        </>,
      )}
    </>
  )
}
