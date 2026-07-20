import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useCapabilities } from '../capabilities'
import { useLocale } from '../locale'
import { clearSeries } from '../liveSeries'

const SLOT_MANUAL = 0x28

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

function applyPreset(entry: Record<string, unknown>, prev: Form): Form {
  return {
    ...prev,
    battery_slot: Number(entry.slot),
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

export function StartProcess() {
  const navigate = useNavigate()
  const [sp] = useSearchParams()
  const { t } = useLocale()
  const { capabilities, batteryTypes, programs } = useCapabilities()
  const [meta, setMeta] = useState<{ battery_types: Record<string, string>; programs: Record<string, string> } | null>(null)
  const [presets, setPresets] = useState<Record<string, unknown>[]>([])
  const [form, setForm] = useState<Form>({ ...defaultForm, channel: Number(sp.get('ch') || 0) })
  const [preview, setPreview] = useState<{
    device: Record<string, unknown>
    corrections: Record<string, { requested: unknown; device: unknown }>
  } | null>(null)
  const [err, setErr] = useState('')
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

  const set = (k: keyof Form, v: number | boolean) => setForm((f) => ({ ...f, [k]: v }))

  const setChannel = (ch: number) => {
    setForm((f) => ({
      ...f,
      channel: ch,
      activator: capabilities.activator && activatorCh != null && ch === activatorCh ? f.activator : false,
    }))
  }

  const selectPreset = (slot: number) => {
    if (slot === SLOT_MANUAL) {
      set('battery_slot', SLOT_MANUAL)
      return
    }
    const entry = presets.find((e) => Number(e.slot) === slot)
    if (entry) {
      setForm((f) => applyPreset(entry, f))
    } else {
      set('battery_slot', slot)
    }
  }

  const correctedKeys = useMemo(() => new Set(Object.keys(preview?.corrections || {})), [preview])
  const fullPct = toPercent(form.full_factor)
  const fullOver = fullPct > 100
  const payload = () => ({
    ...form,
    full_factor: capabilities.full_factor ? form.full_factor : 250,
  })

  const doPreview = async () => {
    setErr('')
    try {
      const res = await api.preview(payload())
      setPreview({ device: res.device, corrections: res.corrections })
    } catch (e) {
      setErr(String((e as Error).message || e))
    }
  }

  const doStart = async () => {
    setErr('')
    setBusy(true)
    try {
      if (!preview) {
        const res = await api.preview(payload())
        setPreview({ device: res.device, corrections: res.corrections })
      }
      clearSeries(form.channel)
      await api.start(payload())
      navigate('/')
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
                value={form.battery_slot >= SLOT_MANUAL ? SLOT_MANUAL : form.battery_slot}
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
        </section>

        <section className="start-section">
          <h2 className="start-section-title">{t('start.sectionParams')}</h2>
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
              {t('start.capacity')}
              <input
                className={correctedKeys.has('capacity_mAh') ? 'corrected' : ''}
                type="number"
                value={form.capacity_mAh}
                onChange={(e) => set('capacity_mAh', Number(e.target.value))}
              />
            </label>
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
            {t('start.corrected')}{' '}
            {Object.entries(preview.corrections)
              .map(([k, v]) => `${k}: ${v.requested} → ${v.device}`)
              .join(', ')}
          </div>
        )}
        {preview && Object.keys(preview.corrections).length === 0 && (
          <div className="toast ok" style={{ marginTop: '1rem' }}>
            {t('start.accepted')}
          </div>
        )}
        {err && <div className="toast error">{err}</div>}
      </div>
    </>
  )
}
