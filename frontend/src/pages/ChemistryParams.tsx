import { useCallback, useState, type ReactNode } from 'react'
import { api } from '../api'
import { useCapabilities } from '../capabilities'
import { useLocale } from '../locale'

/**
 * ELV factory voltage defaults from ELV Firm-/Software-Upgrade ALC 8500 Expert-2.
 * Pause / cycles / −ΔU: previous software defaults (not numeric in ELV PDF tables).
 */
const ELV_FACTORY_G: Record<string, number> = {
  discharge_NiCd_mV: 900,
  discharge_NiMH_mV: 900,
  discharge_LiIon_mV: 3000,
  discharge_LiPo_mV: 3100,
  discharge_Pb_mV: 1850,
  pause_min: 1,
  cycles_cycle_NiCd: 5,
  cycles_cycle_NiMH: 5,
  cycles_form_NiCd: 5,
  cycles_form_NiMH: 5,
  dU_NiCd: 40,
  dU_NiMH: 20,
}

const ELV_FACTORY_H: Record<string, number> = {
  charge_LiIon_mV: 4100,
  maintain_LiIon_mV: 4050,
  charge_LiPo_mV: 4200,
  maintain_LiPo_mV: 4150,
  charge_Pb_mV: 2350,
  maintain_Pb_mV: 2260,
}

const ELV_FACTORY_J: Record<string, number> = {
  discharge_LiFePO4_mV: 2300,
  charge_LiFePO4_mV: 3650,
  maintain_LiFePO4_mV: 3450,
}

/** Longevity-oriented: earlier cut-off, lower charge voltage — less capacity, kinder to cells. */
const GENTLE_G: Record<string, number> = {
  discharge_NiCd_mV: 1000,
  discharge_NiMH_mV: 1000,
  discharge_LiIon_mV: 3100,
  discharge_LiPo_mV: 3200,
  discharge_Pb_mV: 1900,
  pause_min: 5,
  cycles_cycle_NiCd: 3,
  cycles_cycle_NiMH: 3,
  cycles_form_NiCd: 3,
  cycles_form_NiMH: 3,
  dU_NiCd: 25,
  dU_NiMH: 12,
}

const GENTLE_H: Record<string, number> = {
  charge_LiIon_mV: 4000,
  maintain_LiIon_mV: 3950,
  charge_LiPo_mV: 4100,
  maintain_LiPo_mV: 4050,
  charge_Pb_mV: 2350,
  maintain_Pb_mV: 2260,
}

const GENTLE_J: Record<string, number> = {
  discharge_LiFePO4_mV: 2400,
  charge_LiFePO4_mV: 3600,
  maintain_LiFePO4_mV: 3400,
}

function pickLiFe(j: Record<string, number | boolean>): Record<string, number> {
  return {
    discharge_LiFePO4_mV: Number(j.discharge_LiFePO4_mV ?? 0),
    charge_LiFePO4_mV: Number(j.charge_LiFePO4_mV ?? 0),
    maintain_LiFePO4_mV: Number(j.maintain_LiFePO4_mV ?? 0),
  }
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
    setG(res.g)
    setH(res.h)
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
      await api.putG({
        discharge_NiCd_mV: g.discharge_NiCd_mV,
        discharge_NiMH_mV: g.discharge_NiMH_mV,
        discharge_LiIon_mV: g.discharge_LiIon_mV,
        discharge_LiPo_mV: g.discharge_LiPo_mV,
        discharge_Pb_mV: g.discharge_Pb_mV,
        pause_min: g.pause_min,
        cycles_cycle_NiCd: g.cycles_cycle_NiCd,
        cycles_cycle_NiMH: g.cycles_cycle_NiMH,
        cycles_form_NiCd: g.cycles_form_NiCd,
        cycles_form_NiMH: g.cycles_form_NiMH,
        dU_NiCd: g.dU_NiCd,
        dU_NiMH: g.dU_NiMH,
      })
      if (showHj) {
        await api.putH({
          charge_LiIon_mV: h.charge_LiIon_mV,
          maintain_LiIon_mV: h.maintain_LiIon_mV,
          charge_LiPo_mV: h.charge_LiPo_mV,
          maintain_LiPo_mV: h.maintain_LiPo_mV,
          charge_Pb_mV: h.charge_Pb_mV,
          maintain_Pb_mV: h.maintain_Pb_mV,
        })
        // Preserve device display/setup bytes that share the j frame.
        const cur = await api.deviceParams()
        await api.putJ({
          discharge_LiFePO4_mV: j.discharge_LiFePO4_mV,
          charge_LiFePO4_mV: j.charge_LiFePO4_mV,
          maintain_LiFePO4_mV: j.maintain_LiFePO4_mV,
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
    okKey: 'chem.factoryOk' | 'chem.gentleOk',
  ) => {
    setErr('')
    setG({ ...gPreset })
    setH({ ...hPreset })
    setJ({ ...jPreset })
    setFromDevice(false)
    setMsg(t(okKey))
  }

  const doElvFactory = () => loadPreset(ELV_FACTORY_G, ELV_FACTORY_H, ELV_FACTORY_J, 'chem.factoryOk')
  const doGentle = () => loadPreset(GENTLE_G, GENTLE_H, GENTLE_J, 'chem.gentleOk')

  const numField = (
    obj: Record<string, number>,
    setObj: (v: Record<string, number>) => void,
    key: string,
    label: string,
  ) => (
    <label className="field" key={key}>
      {label}
      <input
        type="number"
        value={Number(obj[key] ?? 0)}
        onChange={(e) => setObj({ ...obj, [key]: Number(e.target.value) })}
      />
    </label>
  )

  const typePanel = (title: string, fields: ReactNode) => (
    <div className="panel">
      <h2>{title}</h2>
      <div className="form-grid">{fields}</div>
    </div>
  )

  const actionButtons = (
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
      <button type="button" onClick={doGentle} disabled={busy}>
        {t('chem.gentle')}
      </button>
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
          {numField(g, setG, 'discharge_NiCd_mV', t('chem.discharge'))}
          {numField(g, setG, 'dU_NiCd', t('chem.dU'))}
          {numField(g, setG, 'cycles_cycle_NiCd', t('chem.cyclesCycle'))}
          {numField(g, setG, 'cycles_form_NiCd', t('chem.cyclesForm'))}
        </>,
      )}

      {typePanel(
        t('chem.groupNiMH'),
        <>
          {numField(g, setG, 'discharge_NiMH_mV', t('chem.discharge'))}
          {numField(g, setG, 'dU_NiMH', t('chem.dU'))}
          {numField(g, setG, 'cycles_cycle_NiMH', t('chem.cyclesCycle'))}
          {numField(g, setG, 'cycles_form_NiMH', t('chem.cyclesForm'))}
        </>,
      )}

      {typePanel(
        t('chem.groupLi41'),
        <>
          {numField(g, setG, 'discharge_LiIon_mV', t('chem.discharge'))}
          {showHj && (
            <>
              {numField(h, setH, 'charge_LiIon_mV', t('chem.charge'))}
              {numField(h, setH, 'maintain_LiIon_mV', t('chem.maintain'))}
            </>
          )}
        </>,
      )}

      {typePanel(
        t('chem.groupLi42'),
        <>
          {numField(g, setG, 'discharge_LiPo_mV', t('chem.discharge'))}
          {showHj && (
            <>
              {numField(h, setH, 'charge_LiPo_mV', t('chem.charge'))}
              {numField(h, setH, 'maintain_LiPo_mV', t('chem.maintain'))}
            </>
          )}
        </>,
      )}

      {typePanel(
        t('chem.groupPb'),
        <>
          {numField(g, setG, 'discharge_Pb_mV', t('chem.discharge'))}
          {showHj && (
            <>
              {numField(h, setH, 'charge_Pb_mV', t('chem.charge'))}
              {numField(h, setH, 'maintain_Pb_mV', t('chem.maintain'))}
            </>
          )}
        </>,
      )}

      {showHj &&
        typePanel(
          t('chem.groupLiFe'),
          <>
            {numField(j, setJ, 'discharge_LiFePO4_mV', t('chem.discharge'))}
            {numField(j, setJ, 'charge_LiFePO4_mV', t('chem.charge'))}
            {numField(j, setJ, 'maintain_LiFePO4_mV', t('chem.maintain'))}
          </>,
        )}

      {typePanel(t('chem.groupGeneral'), <>{numField(g, setG, 'pause_min', t('chem.pauseMin'))}</>)}

      <div className="row chem-actions chem-actions-footer">
        <button type="button" className="primary-danger" onClick={doApply} disabled={busy}>
          {t('chem.apply')}
        </button>
      </div>
    </>
  )
}
