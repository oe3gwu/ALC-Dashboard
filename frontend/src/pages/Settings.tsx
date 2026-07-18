import { useEffect, useState } from 'react'
import { api } from '../api'
import { useCapabilities } from '../capabilities'
import { useLive } from '../live'
import { useLocale } from '../locale'

export function Settings() {
  const { t } = useLocale()
  const { devices, deviceModel, refresh: refreshCaps } = useCapabilities()
  const { refresh: refreshLive } = useLive()
  const [model, setModel] = useState(deviceModel)
  const [serial, setSerial] = useState('')
  const [simulator, setSimulator] = useState(true)
  const [poll, setPoll] = useState(1.5)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [ports, setPorts] = useState<{ device: string; description: string; vid: string | null; pid: string | null }[]>([])

  const portSet = Boolean(serial.trim())

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

  const save = async () => {
    setErr('')
    setMsg('')
    const sim = portSet ? false : simulator
    try {
      await api.updateConfig({
        device_model: model,
        serial_port: sim ? '' : serial.trim(),
        simulator: sim,
        poll_interval: poll,
      })
      if (sim) setSerial('')
      setSimulator(sim)
      setMsg(t('set.saved'))
      await refreshCaps()
      await refreshLive()
    } catch (e) {
      setErr(String((e as Error).message || e))
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

  return (
    <>
      <h1>{t('set.title')}</h1>
      <p className="lead">{t('set.lead')}</p>
      <div className="panel form-grid">
        <label className="field">
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
      <div className="row">
        <button className="primary" onClick={save}>
          {t('common.save')}
        </button>
        <button type="button" onClick={disconnect}>
          {t('set.disconnect')}
        </button>
      </div>
      {msg && <div className="toast ok">{msg}</div>}
      {err && <div className="toast error">{err}</div>}
    </>
  )
}
