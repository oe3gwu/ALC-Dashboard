import { useEffect, useState } from 'react'
import { api } from '../api'
import { useCapabilities } from '../capabilities'
import { useLive } from '../live'
import { useLocale } from '../locale'
import { useTheme } from '../theme'
import type { ThemeMode } from '../theme'
import type { ThemePackId } from '../themePacks'
import type { MessageKey } from '../i18n'

type DeviceSetup = {
  illumination: number
  contrast: number
  alarm_beep: boolean
  button_beep: boolean
}

/** Wire values offered in UI (ELV 0=off, 1=always-on omitted, 2..6 = timers). */
const ILLUM_WIRE = [0, 2, 3, 4, 5, 6] as const

const ILLUM_MODE_KEYS: MessageKey[] = [
  'set.illumOff',
  'set.illum1m',
  'set.illum5m',
  'set.illum10m',
  'set.illum30m',
  'set.illum60m',
]

const DEFAULT_SETUP: DeviceSetup = {
  illumination: 2, // 1 Min.
  contrast: 8,
  alarm_beep: false,
  button_beep: false,
}

function clamp(n: number, lo: number, hi: number): number {
  if (!Number.isFinite(n)) return lo
  return Math.max(lo, Math.min(hi, Math.round(n)))
}

/** Map device wire value → slider index; legacy always-on (1) → Aus. */
function illumWireToIndex(wire: number): number {
  const w = clamp(wire, 0, 6)
  const idx = ILLUM_WIRE.indexOf(w as (typeof ILLUM_WIRE)[number])
  return idx >= 0 ? idx : 0
}

function illumIndexToWire(index: number): number {
  return ILLUM_WIRE[clamp(index, 0, ILLUM_WIRE.length - 1)]
}

function normalizeIllumWire(wire: number): number {
  return illumIndexToWire(illumWireToIndex(wire))
}

export function Settings() {
  const { t } = useLocale()
  const { theme, setTheme, themePack, setThemePack, packs } = useTheme()
  const { devices, deviceModel, capabilities, refresh: refreshCaps } = useCapabilities()
  const { refresh: refreshLive } = useLive()
  const [model, setModel] = useState(deviceModel)
  const [serial, setSerial] = useState('')
  const [simulator, setSimulator] = useState(true)
  const [poll, setPoll] = useState(1.5)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [ports, setPorts] = useState<{ device: string; description: string; vid: string | null; pid: string | null }[]>([])
  const [setup, setSetup] = useState<DeviceSetup>({ ...DEFAULT_SETUP })
  const [setupBusy, setSetupBusy] = useState(false)
  const [setupMsg, setSetupMsg] = useState('')
  const [setupErr, setSetupErr] = useState('')

  const portSet = Boolean(serial.trim())
  const showDeviceDisplay = capabilities.chemistry_hj

  useEffect(() => {
    api.meta().then((m) => {
      const c = m.config as {
        serial_port?: string
        simulator?: boolean
        mock?: boolean
        poll_interval?: number
        device_model?: string
      }
      setSerial(c.serial_port || '')
      setSimulator(Boolean(c.simulator ?? c.mock) && !(c.serial_port || '').trim())
      setPoll(Number(c.poll_interval || 1.5))
      setModel(String(c.device_model || m.device_model || 'alc8500_2_expert'))
    })
    api.ports().then((p) => setPorts(p.ports)).catch(() => {})
  }, [])

  useEffect(() => {
    if (portSet && simulator) setSimulator(false)
  }, [portSet, simulator])

  useEffect(() => {
    if (!showDeviceDisplay) return
    api
      .deviceParams()
      .then((res) => {
        setSetup({
          illumination: normalizeIllumWire(Number(res.j.illumination ?? 2)),
          contrast: Number(res.j.contrast ?? 8),
          alarm_beep: Boolean(res.j.alarm_beep),
          button_beep: Boolean(res.j.button_beep),
        })
      })
      .catch(() => {
        /* not connected yet */
      })
  }, [showDeviceDisplay])

  const applyFormConfig = async () => {
    const sim = portSet ? false : simulator
    await api.updateConfig({
      device_model: model,
      serial_port: sim ? '' : serial.trim(),
      simulator: sim,
      poll_interval: poll,
    })
    if (sim) setSerial('')
    setSimulator(sim)
    return sim
  }

  const save = async () => {
    setErr('')
    setMsg('')
    try {
      await applyFormConfig()
      setMsg(t('set.saved'))
      await refreshCaps()
      await refreshLive()
    } catch (e) {
      setErr(String((e as Error).message || e))
      await refreshLive()
    }
  }

  const connect = async () => {
    setErr('')
    setMsg('')
    try {
      const sim = await applyFormConfig()
      const port = sim ? null : serial.trim() || null
      await api.connect({ port, simulator: sim })
      setMsg(t('set.connected'))
      await refreshCaps()
      await refreshLive()
    } catch (e) {
      setErr(String((e as Error).message || e))
      await refreshCaps()
      await refreshLive()
    }
  }

  const disconnect = async () => {
    setErr('')
    setMsg('')
    try {
      await api.disconnect()
      setMsg(t('set.disconnected'))
      await refreshCaps()
      await refreshLive()
    } catch (e) {
      setErr(String((e as Error).message || e))
    }
  }

  const readSetup = async () => {
    setSetupErr('')
    setSetupMsg('')
    setSetupBusy(true)
    try {
      const res = await api.deviceParams()
      setSetup({
        illumination: normalizeIllumWire(Number(res.j.illumination ?? 2)),
        contrast: Number(res.j.contrast ?? 8),
        alarm_beep: Boolean(res.j.alarm_beep),
        button_beep: Boolean(res.j.button_beep),
      })
      setSetupMsg(t('set.setupReadOk'))
    } catch (e) {
      setSetupErr(String((e as Error).message || e))
    } finally {
      setSetupBusy(false)
    }
  }

  const applySetup = async () => {
    setSetupErr('')
    setSetupMsg('')
    setSetupBusy(true)
    try {
      const wantIllum = normalizeIllumWire(setup.illumination)
      const wantContrast = clamp(setup.contrast, 0, 15)
      // Preserve LiFe voltages that share the j frame (placeholders RMW on backend).
      const cur = await api.deviceParams()
      const echoed = (await api.putJ({
        discharge_LiFePO4_mV: cur.j.discharge_LiFePO4_mV,
        charge_LiFePO4_mV: cur.j.charge_LiFePO4_mV,
        maintain_LiFePO4_mV: cur.j.maintain_LiFePO4_mV,
        illumination: wantIllum,
        contrast: wantContrast,
        alarm_beep: setup.alarm_beep,
        button_beep: setup.button_beep,
      })) as {
        illumination?: number
        contrast?: number
        alarm_beep?: boolean
        button_beep?: boolean
      }
      const gotIllum = normalizeIllumWire(Number(echoed.illumination ?? -1))
      if (Number(echoed.illumination) !== wantIllum) {
        setSetupErr(t('set.setupIllumMismatch', { want: wantIllum, got: Number(echoed.illumination) }))
        setSetup({
          illumination: gotIllum,
          contrast: Number(echoed.contrast ?? wantContrast),
          alarm_beep: Boolean(echoed.alarm_beep),
          button_beep: Boolean(echoed.button_beep),
        })
        return
      }
      setSetup({
        illumination: wantIllum,
        contrast: Number(echoed.contrast ?? wantContrast),
        alarm_beep: Boolean(echoed.alarm_beep ?? setup.alarm_beep),
        button_beep: Boolean(echoed.button_beep ?? setup.button_beep),
      })
      setSetupMsg(t('set.setupApplyOk'))
    } catch (e) {
      setSetupErr(String((e as Error).message || e))
    } finally {
      setSetupBusy(false)
    }
  }

  return (
    <>
      <h1>{t('set.title')}</h1>
      <p className="lead">{t('set.lead')}</p>
      <div className="panel">
        <h2>{t('set.connection')}</h2>
        <div className="form-grid">
        <label className="field field-device">
          {t('set.device')}
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {(devices.length ? devices : [{ id: model, label: model, enabled: true, disabled_reason: '' }]).map((d) => (
              <option key={d.id} value={d.id} disabled={!d.enabled}>
                {d.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          {t('set.serialPort')}
          <input
            list="serial-port-suggestions"
            value={serial}
            placeholder={t('set.placeholder')}
            disabled={simulator && !portSet}
            onChange={(e) => setSerial(e.target.value)}
          />
          <datalist id="serial-port-suggestions">
            {ports.map((p) => (
              <option
                key={p.device}
                value={p.device}
                label={`${p.description}${p.vid ? ` (${p.vid}:${p.pid})` : ''}`}
              />
            ))}
          </datalist>
        </label>
        <label className="field">
          {t('set.simulator')}
          <input
            type="checkbox"
            checked={simulator && !portSet}
            disabled={portSet}
            onChange={(e) => {
              const on = e.target.checked
              setSimulator(on)
              if (on) setSerial('')
            }}
          />
          <span className="field-hint">{portSet ? t('set.simulatorNeedsEmptyPort') : t('set.simulatorHint')}</span>
        </label>
        <label className="field">
          {t('set.poll')}
          <input type="number" step="0.1" value={poll} onChange={(e) => setPoll(Number(e.target.value))} />
        </label>
        </div>
        <div className="row panel-actions">
          <button type="button" className="primary" onClick={save}>
            {t('common.save')}
          </button>
          <button type="button" className="primary" onClick={connect}>
            {t('set.connect')}
          </button>
          <button type="button" onClick={disconnect}>
            {t('set.disconnect')}
          </button>
        </div>
      </div>
      {msg && <div className="toast ok">{msg}</div>}
      {err && <div className="toast error">{err}</div>}

      <div className="panel" style={{ marginTop: '1.5rem' }}>
        <h2>{t('set.appearance')}</h2>
        <p className="lead" style={{ marginTop: 0 }}>
          {t('set.appearanceLead')}
        </p>
        <div className="form-grid">
          <label className="field">
            {t('set.themePack')}
            <select
              value={themePack}
              onChange={(e) => setThemePack(e.target.value as ThemePackId)}
            >
              {packs.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
            <span className="field-hint">{t('set.themePackHint')}</span>
          </label>
          <label className="field">
            {t('set.themeMode')}
            <select value={theme} onChange={(e) => setTheme(e.target.value as ThemeMode)}>
              <option value="light">{t('set.themeModeLight')}</option>
              <option value="dark">{t('set.themeModeDark')}</option>
            </select>
            <span className="field-hint">{t('set.themeModeHint')}</span>
          </label>
        </div>
      </div>

      {showDeviceDisplay && (
        <>
          <div className="panel" style={{ marginTop: '1.5rem' }}>
            <h2>{t('set.deviceDisplay')}</h2>
            <p className="lead" style={{ marginTop: 0 }}>
              {t('set.deviceDisplayLead')}
            </p>
            <div className="form-grid">
              <label className="field field-span-2">
                {t('set.illumination')}
                <div className="setup-slider-row">
                  <input
                    type="range"
                    className="setup-slider"
                    min={0}
                    max={ILLUM_WIRE.length - 1}
                    step={1}
                    value={illumWireToIndex(setup.illumination)}
                    onChange={(e) =>
                      setSetup({ ...setup, illumination: illumIndexToWire(Number(e.target.value)) })
                    }
                    aria-valuetext={t(ILLUM_MODE_KEYS[illumWireToIndex(setup.illumination)])}
                  />
                  <span className="setup-slider-value">
                    {t(ILLUM_MODE_KEYS[illumWireToIndex(setup.illumination)])}
                  </span>
                </div>
              </label>
              <label className="field field-span-2">
                {t('set.contrast')}
                <div className="setup-slider-row">
                  <input
                    type="range"
                    className="setup-slider"
                    min={0}
                    max={15}
                    step={1}
                    value={clamp(setup.contrast, 0, 15)}
                    onChange={(e) =>
                      setSetup({ ...setup, contrast: clamp(Number(e.target.value), 0, 15) })
                    }
                  />
                  <span className="setup-slider-value">
                    {clamp(setup.contrast, 0, 15)}{' '}
                    <span className="field-hint">({t('set.contrastHint')})</span>
                  </span>
                </div>
              </label>
              <label className="field">
                {t('set.alarmBeep')}
                <select
                  value={setup.alarm_beep ? 1 : 0}
                  onChange={(e) => setSetup({ ...setup, alarm_beep: e.target.value === '1' })}
                >
                  <option value={0}>{t('common.off')}</option>
                  <option value={1}>{t('common.on')}</option>
                </select>
              </label>
              <label className="field">
                {t('set.buttonBeep')}
                <select
                  value={setup.button_beep ? 1 : 0}
                  onChange={(e) => setSetup({ ...setup, button_beep: e.target.value === '1' })}
                >
                  <option value={0}>{t('common.off')}</option>
                  <option value={1}>{t('common.on')}</option>
                </select>
              </label>
            </div>
            <div className="row panel-actions">
              <button type="button" onClick={() => void readSetup()} disabled={setupBusy}>
                {t('set.readSetup')}
              </button>
              <button type="button" className="primary" onClick={() => void applySetup()} disabled={setupBusy}>
                {t('set.applySetup')}
              </button>
            </div>
          </div>
          {setupMsg && <div className="toast ok">{setupMsg}</div>}
          {setupErr && <div className="toast error">{setupErr}</div>}
        </>
      )}
    </>
  )
}
