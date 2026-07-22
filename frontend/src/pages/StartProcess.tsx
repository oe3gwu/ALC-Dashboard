import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, type ChannelParams } from '../api'
import { formatMaxPackVoltage } from '../batteryVoltage'
import { useCapabilities } from '../capabilities'
import { useLive } from '../live'
import { useLocale } from '../locale'
import type { MessageKey } from '../i18n'
import { clearSeries } from '../liveSeries'

const SLOT_MANUAL = 0x28

/** Field keys from API corrections → same labels as the start form. */
const CORRECTION_LABELS: Record<string, MessageKey> = {
  charge_mA: 'start.chargeCurrent',
  discharge_mA: 'start.dischargeCurrent',
  forming_mA: 'start.formingCurrent',
  capacity_mAh: 'start.capacity',
  cells: 'start.cells',
  battery_type: 'start.batteryType',
  program: 'start.program',
  pause_s: 'start.pause',
  full_factor: 'start.fullFactor',
  activator: 'start.activator',
  channel: 'start.channel',
}

type Form = {
  channel: number
  battery_slot: number
  battery_type: number
  cells: number
  discharge_mA: number
  charge_mA: number
  capacity_mAh: number
  program: number
  forming_mA: number
  pause_s: number
  full_factor: number
  activator: boolean
}

const defaultForm: Form = {
  channel: 0,
  battery_slot: SLOT_MANUAL,
  battery_type: 1,
  cells: 4,
  discharge_mA: 500,
  charge_mA: 500,
  capacity_mAh: 2000,
  program: 1,
  forming_mA: 0,
  pause_s: 60,
  full_factor: 100,
  activator: false,
}

/** Protocol: 250 = off. UI slider 0% = off, 1–150 = percent. */
function toPercent(full: number): number {
  if (full > 150) return 0
  return Math.max(0, Math.min(150, full))
}

function fromPercent(pct: number): number {
  if (pct <= 0) return 250
  return Math.max(1, Math.min(150, pct))
}

type CorrectionMap = Record<string, { requested: unknown; device: unknown }>

/** Device quirks not worth blocking start for (forming floor, Vollfaktor echo). */
function notableCorrections(corrections: CorrectionMap | null | undefined): CorrectionMap {
  if (!corrections) return {}
  const out: CorrectionMap = {}
  for (const [k, v] of Object.entries(corrections)) {
    if (k === 'forming_mA' && Number(v.requested) === 0) continue
    if (k === 'full_factor') continue
    out[k] = v
  }
  return out
}

/** Copy DB fields into the form; always write as manual slot so FW does not reload EEPROM. */
function applyPreset(entry: Record<string, unknown>, prev: Form): Form {
  return {
    ...prev,
    battery_slot: SLOT_MANUAL,
    battery_type: Number(entry.battery_type ?? prev.battery_type),
    cells: Number(entry.cells ?? prev.cells),
    capacity_mAh: Number(entry.capacity_mAh ?? prev.capacity_mAh),
    charge_mA: Number(entry.charge_mA ?? prev.charge_mA),
    discharge_mA: Number(entry.discharge_mA ?? prev.discharge_mA),
    pause_s: Number(entry.pause_s ?? prev.pause_s),
    forming_mA: Number(entry.forming_mA ?? prev.forming_mA),
    full_factor: Number(entry.full_factor ?? prev.full_factor),
  }
}

/** Merge device P-echo into form (keeps channel/activator; skips known FW echo quirks). */
function formFromDeviceEcho(device: Record<string, unknown>, prev: Form): Form {
  const num = (k: keyof Form, fallback: number) => {
    const v = Number(device[k])
    return Number.isFinite(v) ? v : fallback
  }
  const forming = num('forming_mA', prev.forming_mA)
  return {
    ...prev,
    battery_slot: SLOT_MANUAL,
    battery_type: num('battery_type', prev.battery_type),
    cells: num('cells', prev.cells),
    capacity_mAh: num('capacity_mAh', prev.capacity_mAh),
    charge_mA: num('charge_mA', prev.charge_mA),
    discharge_mA: num('discharge_mA', prev.discharge_mA),
    pause_s: num('pause_s', prev.pause_s),
    // Keep requested 0 — device often floors forming; Vollfaktor echo is unreliable on P.
    forming_mA: prev.forming_mA === 0 ? 0 : forming,
    full_factor: prev.full_factor,
    program: num('program', prev.program),
  }
}

/** Load stored channel params from device into the start form (does not start). */
function formFromDeviceStored(device: ChannelParams, prev: Form): Form {
  return {
    ...prev,
    battery_slot: SLOT_MANUAL,
    battery_type: device.battery_type,
    cells: device.cells,
    capacity_mAh: device.capacity_mAh,
    charge_mA: device.charge_mA,
    discharge_mA: device.discharge_mA,
    pause_s: device.pause_s,
    forming_mA: device.forming_mA,
    full_factor: device.full_factor,
    program: device.program,
    activator: Boolean(device.activator),
  }
}

export function StartProcess() {
  const navigate = useNavigate()
  const [sp] = useSearchParams()
  const { t } = useLocale()
  const { connection } = useLive()
  const { capabilities, batteryTypes, programs } = useCapabilities()
  const [meta, setMeta] = useState<{ battery_types: Record<string, string>; programs: Record<string, string> } | null>(null)
  const [presets, setPresets] = useState<Record<string, unknown>[]>([])
  const [form, setForm] = useState<Form>({ ...defaultForm, channel: Number(sp.get('ch') || 0) })
  /** UI dropdown only — wire always uses form.battery_slot (manual after preset apply). */
  const [selectedPresetSlot, setSelectedPresetSlot] = useState(SLOT_MANUAL)
  const [preview, setPreview] = useState<{
    device: Record<string, unknown>
    corrections: Record<string, { requested: unknown; device: unknown }>
  } | null>(null)
  const [pendingCorrections, setPendingCorrections] = useState<Record<
    string,
    { requested: unknown; device: unknown }
  > | null>(null)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const activatorCh = capabilities.activator_channel
  const showActivator = capabilities.activator && activatorCh != null && form.channel === activatorCh
  const channelList = Array.from({ length: capabilities.channel_count }, (_, i) => i)
  const bt = meta?.battery_types || batteryTypes
  const prog = meta?.programs || programs

  useEffect(() => {
    api
      .meta()
      .then((m) => setMeta({ battery_types: m.battery_types, programs: m.programs }))
      .catch((e) => setErr(String(e.message || e)))
    if (capabilities.battery_db) {
      api
        .batteryDb()
        .then((r) => setPresets(Array.isArray(r.entries) ? r.entries : []))
        .catch(() => setPresets([]))
    } else {
      setPresets([])
    }
  }, [capabilities.battery_db])

  const set = (k: keyof Form, v: number | boolean) => {
    setPreview(null)
    setPendingCorrections(null)
    setMsg('')
    // Manual edit leaves preset values but drops DB association in the UI.
    if (k !== 'channel' && k !== 'activator' && k !== 'program') {
      setSelectedPresetSlot(SLOT_MANUAL)
    }
    setForm((f) => ({ ...f, [k]: v, battery_slot: SLOT_MANUAL }))
  }

  const setChannel = (ch: number) => {
    setPreview(null)
    setPendingCorrections(null)
    setMsg('')
    setForm((f) => ({
      ...f,
      channel: ch,
      activator: capabilities.activator && activatorCh != null && ch === activatorCh ? f.activator : false,
    }))
  }

  const selectPreset = (slot: number) => {
    setPreview(null)
    setPendingCorrections(null)
    setMsg('')
    setSelectedPresetSlot(slot)
    if (slot === SLOT_MANUAL) {
      setForm((f) => ({ ...f, battery_slot: SLOT_MANUAL }))
      return
    }
    const entry = presets.find((e) => Number(e.slot) === slot)
    if (entry) {
      setForm((f) => applyPreset(entry, f))
    } else {
      // Unknown slot: still write explicitly as manual to avoid FW slot reload.
      setForm((f) => ({ ...f, battery_slot: SLOT_MANUAL }))
    }
  }

  const loadFromDevice = async () => {
    setErr('')
    setMsg('')
    setBusy(true)
    try {
      const device = await api.getChannel(form.channel)
      if (device.battery_type === 0xff) {
        setErr(t('start.noDeviceConfig'))
        return
      }
      setForm((f) => formFromDeviceStored(device, f))
      setSelectedPresetSlot(SLOT_MANUAL)
      setPreview(null)
      setPendingCorrections(null)
      setMsg(t('start.loadedFromDevice'))
    } catch (e) {
      setErr(String((e as Error).message || e))
    } finally {
      setBusy(false)
    }
  }

  const correctedKeys = useMemo(
    () => new Set(Object.keys(notableCorrections(preview?.corrections))),
    [preview],
  )
  const fullPct = toPercent(form.full_factor)
  const fullOver = fullPct > 100
  const maxVoltageLabel = useMemo(
    () => formatMaxPackVoltage(form.battery_type, form.cells),
    [form.battery_type, form.cells],
  )

  const formatCorrectionValue = (key: string, value: unknown): string => {
    if (key === 'full_factor') {
      const n = Number(value)
      if (!Number.isFinite(n) || n <= 0 || n >= 250) return t('start.fullFactorOff')
      return `${n} %`
    }
    if (typeof value === 'number') return String(value)
    if (value == null) return '—'
    return String(value)
  }

  const formatCorrections = (corrections: CorrectionMap) =>
    Object.entries(notableCorrections(corrections))
      .map(([k, v]) => {
        const label = CORRECTION_LABELS[k] ? t(CORRECTION_LABELS[k]) : k
        return `${label}: ${formatCorrectionValue(k, v.requested)} → ${formatCorrectionValue(k, v.device)}`
      })
      .join(', ')

  const applyDeviceEcho = (device: Record<string, unknown>) => {
    setForm((f) => formFromDeviceEcho(device, f))
  }

  const payloadFrom = (f: Form) => ({
    ...f,
    full_factor: capabilities.full_factor ? f.full_factor : 250,
  })

  const payload = () => payloadFrom(form)

  const doPreview = async () => {
    setErr('')
    setPendingCorrections(null)
    setBusy(true)
    try {
      const res = await api.preview(payload())
      const corrections = notableCorrections(res.corrections)
      applyDeviceEcho(res.device)
      setPreview({ device: res.device, corrections })
    } catch (e) {
      setErr(String((e as Error).message || e))
    } finally {
      setBusy(false)
    }
  }

  const finishStart = async (params?: Form) => {
    const f = params ?? form
    clearSeries(f.channel)
    await api.start(payloadFrom(f))
    navigate('/')
  }

  const doStart = async () => {
    setErr('')
    setBusy(true)
    try {
      // Always re-check on the device so current limits are current
      const res = await api.preview(payload())
      const corrections = notableCorrections(res.corrections)
      const synced = formFromDeviceEcho(res.device, form)
      setForm(synced)
      setPreview({ device: res.device, corrections })
      if (Object.keys(corrections).length > 0) {
        setPendingCorrections(corrections)
        return
      }
      await finishStart(synced)
    } catch (e) {
      setErr(String((e as Error).message || e))
    } finally {
      setBusy(false)
    }
  }

  const confirmStartDespiteCorrections = async () => {
    setPendingCorrections(null)
    setErr('')
    setBusy(true)
    try {
      await finishStart()
    } catch (e) {
      setErr(String((e as Error).message || e))
    } finally {
      setBusy(false)
    }
  }

  const presetLabel = (entry: Record<string, unknown>) => {
    const name = String(entry.name || '').trim()
    const n = Number(entry.slot) + 1
    return name || t('start.presetEmpty', { n })
  }

  return (
    <>
      <h1>{t('start.title')}</h1>

      <div className="panel start-form">
        <section className="start-section">
          <h2 className="start-section-title">{t('start.sectionPrimary')}</h2>
          <div className="form-grid start-primary-grid">
            <label className="field">
              {t('start.channel')}
              <select value={form.channel} onChange={(e) => setChannel(Number(e.target.value))}>
                {channelList.map((n) => (
                  <option key={n} value={n}>
                    {t('common.channelN', { n: n + 1 })}
                  </option>
                ))}
              </select>
            </label>
            {capabilities.battery_db && (
            <label className="field">
              {t('start.preset')}
              <select
                value={selectedPresetSlot}
                onChange={(e) => selectPreset(Number(e.target.value))}
              >
                <option value={SLOT_MANUAL}>{t('start.presetManual')}</option>
                {presets.map((e) => (
                  <option key={String(e.slot)} value={Number(e.slot)}>
                    {presetLabel(e)}
                  </option>
                ))}
              </select>
            </label>
            )}
            <label className="field">
              {t('start.program')}
              <select value={form.program} onChange={(e) => set('program', Number(e.target.value))}>
                {Object.entries(prog).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {connection?.connected && (
            <div className="row" style={{ marginTop: '0.55rem' }}>
              <button type="button" disabled={busy} onClick={() => void loadFromDevice()}>
                {t('start.loadFromDevice')}
              </button>
            </div>
          )}
        </section>

        <section className="start-section">
          <h2 className="start-section-title">{t('start.sectionBattery')}</h2>
          <div className="form-grid">
            <label className="field">
              {t('start.batteryType')}
              <select value={form.battery_type} onChange={(e) => set('battery_type', Number(e.target.value))}>
                {Object.entries(bt)
                  .filter(([k]) => k !== '255')
                  .map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
              </select>
            </label>
            <label className="field">
              {t('start.cells')}
              <input
                className={correctedKeys.has('cells') ? 'corrected' : ''}
                type="number"
                value={form.cells}
                onChange={(e) => set('cells', Number(e.target.value))}
              />
            </label>
            <label className="field">
              {t('start.maxVoltage')}
              <input type="text" readOnly tabIndex={-1} value={maxVoltageLabel} aria-readonly="true" />
            </label>
            <label className="field">
              {t('start.capacity')}
              <input
                className={correctedKeys.has('capacity_mAh') ? 'corrected' : ''}
                type="number"
                value={form.capacity_mAh}
                onChange={(e) => set('capacity_mAh', Number(e.target.value))}
              />
            </label>
          </div>
        </section>

        <section className="start-section">
          <h2 className="start-section-title">{t('start.sectionCurrents')}</h2>
          <div className="form-grid">
            <label className="field">
              {t('start.chargeCurrent')}
              <input
                className={correctedKeys.has('charge_mA') ? 'corrected' : ''}
                type="number"
                value={form.charge_mA}
                onChange={(e) => set('charge_mA', Number(e.target.value))}
              />
            </label>
            <label className="field">
              {t('start.dischargeCurrent')}
              <input
                className={correctedKeys.has('discharge_mA') ? 'corrected' : ''}
                type="number"
                value={form.discharge_mA}
                onChange={(e) => set('discharge_mA', Number(e.target.value))}
              />
            </label>
            <label className="field">
              {t('start.formingCurrent')}
              <input type="number" value={form.forming_mA} onChange={(e) => set('forming_mA', Number(e.target.value))} />
            </label>
            <label className="field">
              {t('start.pause')}
              <input type="number" value={form.pause_s} onChange={(e) => set('pause_s', Number(e.target.value))} />
            </label>
          </div>
        </section>

        {capabilities.full_factor && (
          <section className="start-section">
            <h2 className="start-section-title">{t('start.fullFactor')}</h2>
            <div className="full-factor-control">
              <div className="full-factor-row">
                <div className="full-factor-track">
                  <input
                    type="range"
                    className={`full-factor-slider${fullOver ? ' over' : ''}`}
                    min={0}
                    max={150}
                    step={1}
                    value={fullPct}
                    onChange={(e) => set('full_factor', fromPercent(Number(e.target.value)))}
                    aria-label={t('start.fullFactor')}
                  />
                  <div className="full-factor-scale">
                    {[
                      { value: 25 },
                      { value: 33 },
                      { value: 50 },
                      { value: 66 },
                      { value: 75 },
                      { value: 90 },
                      { value: 100 },
                      { value: 110, over: true },
                      { value: 125, over: true },
                      { value: 150, over: true },
                    ].map(({ value, over }) => (
                      <button
                        key={value}
                        type="button"
                        className={`full-factor-mark${over ? ' full-factor-mark-over' : ''}${fullPct === value ? ' active' : ''}`}
                        style={{ left: `${(value / 150) * 100}%` }}
                        onClick={() => set('full_factor', fromPercent(value))}
                        aria-label={`${t('start.fullFactor')}: ${value}%`}
                      >
                        {value}%
                      </button>
                    ))}
                  </div>
                </div>
                <span className={`full-factor-value${fullOver ? ' full-factor-over' : ''}`}>
                  {fullPct === 0 ? t('start.fullFactorOff') : `${fullPct} %`}
                </span>
              </div>
            </div>
          </section>
        )}

        {showActivator && (
          <section className="start-section">
            <h2 className="start-section-title">{t('start.activator')}</h2>
            <label className="field start-activator-field">
              {t('start.activator')}
              <select value={form.activator ? 1 : 0} onChange={(e) => set('activator', e.target.value === '1')}>
                <option value={0}>{t('common.off')}</option>
                <option value={1}>{t('common.on')}</option>
              </select>
            </label>
          </section>
        )}

        <div className="row start-actions">
          <button type="button" onClick={doPreview} disabled={busy}>
            {t('start.preview')}
          </button>
          <button type="button" className="primary" onClick={doStart} disabled={busy}>
            {t('start.start')}
          </button>
        </div>

        {preview && Object.keys(preview.corrections).length > 0 && (
          <div className="toast" style={{ marginTop: '1rem' }}>
            {t('start.corrected')} {formatCorrections(preview.corrections)}
          </div>
        )}
        {preview && Object.keys(preview.corrections).length === 0 && (
          <div className="toast ok" style={{ marginTop: '1rem' }}>
            {t('start.accepted')}
          </div>
        )}
        {msg && <div className="toast ok">{msg}</div>}
        {err && <div className="toast error">{err}</div>}
      </div>

      {pendingCorrections && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="start-confirm-title"
        >
          <div className="modal" onClick={(ev) => ev.stopPropagation()}>
            <h2 id="start-confirm-title">{t('start.confirmTitle')}</h2>
            <p className="lead" style={{ marginTop: 0 }}>
              {t('start.confirmLead')}
            </p>
            <div className="toast" style={{ marginBottom: '1rem' }}>
              {formatCorrections(pendingCorrections)}
            </div>
            <div className="row">
              <button type="button" onClick={() => setPendingCorrections(null)} disabled={busy}>
                {t('start.confirmCancel')}
              </button>
              <button
                type="button"
                className="primary"
                onClick={() => void confirmStartDespiteCorrections()}
                disabled={busy}
              >
                {t('start.confirmStart')}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
