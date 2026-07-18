import { useCallback, useState } from 'react'
import { api } from '../api'
import { useCapabilities } from '../capabilities'
import { useLocale } from '../locale'

/** Local software defaults (match backend DeviceParamsG/H/J) — not device values. */
const DEFAULT_G: Record<string, number> = {
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

const DEFAULT_H: Record<string, number> = {
  charge_LiIon_mV: 4100,
  maintain_LiIon_mV: 4050,
  charge_LiPo_mV: 4200,
  maintain_LiPo_mV: 4150,
  charge_Pb_mV: 2350,
  maintain_Pb_mV: 2260,
}

const DEFAULT_J: Record<string, number | boolean> = {
  discharge_LiFePO4_mV: 2300,
  charge_LiFePO4_mV: 3650,
  maintain_LiFePO4_mV: 3450,
  illumination: 1,
  alarm_beep: false,
  button_beep: false,
  contrast: 8,
}

export function ChemistryParams() {
  const { t } = useLocale()
  const { capabilities } = useCapabilities()
  const showHj = capabilities.chemistry_hj
  const [g, setG] = useState<Record<string, number>>(() => ({ ...DEFAULT_G }))
  const [h, setH] = useState<Record<string, number>>(() => ({ ...DEFAULT_H }))
  const [j, setJ] = useState<Record<string, number | boolean>>(() => ({ ...DEFAULT_J }))
  const [fromDevice, setFromDevice] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    const res = await api.deviceParams()
    setG(res.g)
    setH(res.h)
    setJ(res.j)
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
        await api.putJ({
          discharge_LiFePO4_mV: j.discharge_LiFePO4_mV,
          charge_LiFePO4_mV: j.charge_LiFePO4_mV,
          maintain_LiFePO4_mV: j.maintain_LiFePO4_mV,
          illumination: j.illumination,
          alarm_beep: j.alarm_beep,
          button_beep: j.button_beep,
          contrast: j.contrast,
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

  const doDefaults = async () => {
    setErr('')
    setMsg('')
    setBusy(true)
    try {
      await api.restoreDefaults()
      await load()
      setMsg(t('chem.defaultsOk'))
    } catch (e) {
      setErr(String((e as Error).message || e))
    } finally {
      setBusy(false)
    }
  }

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

  const actionButtons = (
    <div className="row chem-actions">
      <button type="button" onClick={doRead} disabled={busy}>
        {t('chem.read')}
      </button>
      <button type="button" className="primary-danger" onClick={doApply} disabled={busy}>
        {t('chem.apply')}
      </button>
      <button type="button" onClick={doDefaults} disabled={busy}>
        {t('chem.defaults')}
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

      <div className="panel">
        <h2>{t('chem.sectionG')}</h2>
        <section className="chem-subtype">
          <h3>{t('chem.groupNiCd')}</h3>
          <div className="form-grid">
            {numField(g, setG, 'discharge_NiCd_mV', t('chem.dischargeNiCd'))}
            {numField(g, setG, 'dU_NiCd', t('chem.dUNiCd'))}
            {numField(g, setG, 'cycles_cycle_NiCd', t('chem.cyclesCycleNiCd'))}
            {numField(g, setG, 'cycles_form_NiCd', t('chem.cyclesFormNiCd'))}
          </div>
        </section>
        <section className="chem-subtype">
          <h3>{t('chem.groupNiMH')}</h3>
          <div className="form-grid">
            {numField(g, setG, 'discharge_NiMH_mV', t('chem.dischargeNiMH'))}
            {numField(g, setG, 'dU_NiMH', t('chem.dUNiMH'))}
            {numField(g, setG, 'cycles_cycle_NiMH', t('chem.cyclesCycleNiMH'))}
            {numField(g, setG, 'cycles_form_NiMH', t('chem.cyclesFormNiMH'))}
          </div>
        </section>
        <section className="chem-subtype">
          <h3>{t('chem.groupLi41')}</h3>
          <div className="form-grid">
            {numField(g, setG, 'discharge_LiIon_mV', t('chem.dischargeLi41'))}
          </div>
        </section>
        <section className="chem-subtype">
          <h3>{t('chem.groupLi42')}</h3>
          <div className="form-grid">
            {numField(g, setG, 'discharge_LiPo_mV', t('chem.dischargeLi42'))}
          </div>
        </section>
        <section className="chem-subtype">
          <h3>{t('chem.groupPb')}</h3>
          <div className="form-grid">
            {numField(g, setG, 'discharge_Pb_mV', t('chem.dischargePb'))}
          </div>
        </section>
        <section className="chem-subtype">
          <h3>{t('chem.groupGeneral')}</h3>
          <div className="form-grid">
            {numField(g, setG, 'pause_min', t('chem.pauseMin'))}
          </div>
        </section>
      </div>

      {showHj && (
        <div className="panel">
          <h2>{t('chem.sectionH')}</h2>
          <section className="chem-subtype">
            <h3>{t('chem.groupLi41')}</h3>
            <div className="form-grid">
              {numField(h, setH, 'charge_LiIon_mV', t('chem.chargeLi41'))}
              {numField(h, setH, 'maintain_LiIon_mV', t('chem.maintainLi41'))}
            </div>
          </section>
          <section className="chem-subtype">
            <h3>{t('chem.groupLi42')}</h3>
            <div className="form-grid">
              {numField(h, setH, 'charge_LiPo_mV', t('chem.chargeLi42'))}
              {numField(h, setH, 'maintain_LiPo_mV', t('chem.maintainLi42'))}
            </div>
          </section>
          <section className="chem-subtype">
            <h3>{t('chem.groupPb')}</h3>
            <div className="form-grid">
              {numField(h, setH, 'charge_Pb_mV', t('chem.chargePb'))}
              {numField(h, setH, 'maintain_Pb_mV', t('chem.maintainPb'))}
            </div>
          </section>
        </div>
      )}

      {showHj && (
        <div className="panel">
          <h2>{t('chem.sectionJ')}</h2>
          <section className="chem-subtype">
            <h3>{t('chem.groupLiFe')}</h3>
            <div className="form-grid">
              <label className="field">
                {t('chem.dischargeLiFe')}
                <input
                  type="number"
                  value={Number(j.discharge_LiFePO4_mV || 0)}
                  onChange={(e) => setJ({ ...j, discharge_LiFePO4_mV: Number(e.target.value) })}
                />
              </label>
              <label className="field">
                {t('chem.chargeLiFe')}
                <input
                  type="number"
                  value={Number(j.charge_LiFePO4_mV || 0)}
                  onChange={(e) => setJ({ ...j, charge_LiFePO4_mV: Number(e.target.value) })}
                />
              </label>
              <label className="field">
                {t('chem.maintainLiFe')}
                <input
                  type="number"
                  value={Number(j.maintain_LiFePO4_mV || 0)}
                  onChange={(e) => setJ({ ...j, maintain_LiFePO4_mV: Number(e.target.value) })}
                />
              </label>
            </div>
          </section>
          <section className="chem-subtype">
            <h3>{t('chem.groupSetup')}</h3>
            <div className="form-grid">
              <label className="field">
                {t('chem.illumination')}
                <input
                  type="number"
                  value={Number(j.illumination || 0)}
                  onChange={(e) => setJ({ ...j, illumination: Number(e.target.value) })}
                />
              </label>
              <label className="field">
                {t('chem.contrast')}
                <input
                  type="number"
                  value={Number(j.contrast || 0)}
                  onChange={(e) => setJ({ ...j, contrast: Number(e.target.value) })}
                />
              </label>
              <label className="field">
                {t('chem.alarmBeep')}
                <select
                  value={j.alarm_beep ? 1 : 0}
                  onChange={(e) => setJ({ ...j, alarm_beep: e.target.value === '1' })}
                >
                  <option value={0}>{t('common.off')}</option>
                  <option value={1}>{t('common.on')}</option>
                </select>
              </label>
              <label className="field">
                {t('chem.buttonBeep')}
                <select
                  value={j.button_beep ? 1 : 0}
                  onChange={(e) => setJ({ ...j, button_beep: e.target.value === '1' })}
                >
                  <option value={0}>{t('common.off')}</option>
                  <option value={1}>{t('common.on')}</option>
                </select>
              </label>
            </div>
          </section>
        </div>
      )}

      <div className="row chem-actions chem-actions-footer">
        <button type="button" className="primary-danger" onClick={doApply} disabled={busy}>
          {t('chem.apply')}
        </button>
      </div>
    </>
  )
}
