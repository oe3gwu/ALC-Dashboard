import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { useCapabilities } from '../capabilities'
import { useLocale } from '../locale'

export function BatteryDatabase() {
  const { t } = useLocale()
  const { capabilities, batteryTypes } = useCapabilities()
  const [entries, setEntries] = useState<Record<string, unknown>[]>([])
  const [edit, setEdit] = useState<Record<string, unknown> | null>(null)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const typeOptions = useMemo(() => {
    const allowed = new Set(capabilities.battery_type_ids.map(String))
    const entriesList = Object.entries(batteryTypes).filter(([k]) => k !== '255' && (allowed.size === 0 || allowed.has(k)))
    entriesList.sort((a, b) => Number(a[0]) - Number(b[0]))
    return entriesList
  }, [batteryTypes, capabilities.battery_type_ids])

  const load = async () => {
    const res = await api.batteryDb()
    setEntries(res.entries)
  }

  useEffect(() => {
    load().catch((e) => setErr(String(e.message || e)))
  }, [])

  const setEditNum = (k: string, raw: string) => {
    if (!edit) return
    const n = Number(raw)
    setEdit({ ...edit, [k]: Number.isFinite(n) ? n : 0 })
  }

  const save = async () => {
    if (!edit) return
    setErr('')
    try {
      await api.putBattery(Number(edit.slot), edit)
      setMsg(t('bat.savedLocal', { n: Number(edit.slot) + 1 }))
      setEdit(null)
      await load()
    } catch (e) {
      setErr(String((e as Error).message || e))
    }
  }

  const importFromDevice = async () => {
    setErr('')
    setMsg('')
    setBusy(true)
    try {
      const res = await api.importBatteryDbFromDevice()
      setEntries(res.entries)
      const errNote = res.errors?.length ? t('bat.errorsNote', { n: res.errors.length }) : ''
      setMsg(t('bat.imported', { imported: res.imported, total: res.total, errors: errNote }))
    } catch (e) {
      setErr(String((e as Error).message || e))
    } finally {
      setBusy(false)
    }
  }

  const exportToDevice = async () => {
    if (!window.confirm(t('bat.confirmExport'))) {
      return
    }
    setErr('')
    setMsg('')
    setBusy(true)
    try {
      const res = await api.exportBatteryDbToDevice()
      const errNote = res.errors?.length ? t('bat.errorsNote', { n: res.errors.length }) : ''
      setMsg(t('bat.exported', { written: res.written, total: res.total, errors: errNote }))
    } catch (e) {
      setErr(String((e as Error).message || e))
    } finally {
      setBusy(false)
    }
  }

  const downloadJson = async () => {
    setErr('')
    try {
      const blob = await api.downloadBatteryDbFile()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'battery-db.json'
      a.click()
      URL.revokeObjectURL(url)
      setMsg(t('bat.jsonDownloaded'))
    } catch (e) {
      setErr(String((e as Error).message || e))
    }
  }

  const onFileChosen = async (file: File | undefined) => {
    if (!file) return
    setErr('')
    setBusy(true)
    try {
      const res = await api.uploadBatteryDbFile(file)
      setEntries(res.entries)
      setMsg(t('bat.jsonLoaded'))
    } catch (e) {
      setErr(String((e as Error).message || e))
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const openEdit = (e: Record<string, unknown>) => {
    const bt = Number(e.battery_type)
    const allowed = typeOptions.some(([k]) => Number(k) === bt)
    setEdit({
      ...e,
      battery_type: allowed ? bt : Number(typeOptions[0]?.[0] ?? 1),
    })
  }

  return (
    <>
      <h1>{t('bat.title')}</h1>
      <p className="lead">{t('bat.lead')}</p>
      {msg && <div className="toast ok">{msg}</div>}
      {err && <div className="toast error">{err}</div>}

      <div className="row" style={{ marginBottom: '1rem', flexWrap: 'wrap' }}>
        <button className="primary" disabled={busy} onClick={importFromDevice}>
          {t('bat.importAlc')}
        </button>
        <button disabled={busy} onClick={exportToDevice}>
          {t('bat.exportAlc')}
        </button>
        <button disabled={busy} onClick={downloadJson}>
          {t('bat.saveJson')}
        </button>
        <button disabled={busy} onClick={() => fileRef.current?.click()}>
          {t('bat.loadJson')}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          hidden
          onChange={(e) => onFileChosen(e.target.files?.[0])}
        />
        {busy && <span style={{ color: 'var(--muted)' }}>{t('bat.syncing')}</span>}
      </div>

      <div className="panel" style={{ overflow: 'auto' }}>
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>{t('bat.colName')}</th>
              <th>{t('bat.colType')}</th>
              <th>{t('bat.colCells')}</th>
              <th>{t('bat.colCapacity')}</th>
              <th>{t('bat.colICharge')}</th>
              <th>{t('bat.colIDischarge')}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={String(e.slot)}>
                <td className="mono">{Number(e.slot) + 1}</td>
                <td>{String(e.name || '—')}</td>
                <td>{String(e.battery_type_name || batteryTypes[String(e.battery_type)] || e.battery_type)}</td>
                <td className="mono">{String(e.cells)}</td>
                <td className="mono">{String(e.capacity_mAh)}</td>
                <td className="mono">{String(e.charge_mA)}</td>
                <td className="mono">{String(e.discharge_mA)}</td>
                <td>
                  <button disabled={busy} onClick={() => openEdit(e)}>
                    {t('common.edit')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {edit && (
        <div className="modal-backdrop" onClick={() => setEdit(null)}>
          <div className="modal" onClick={(ev) => ev.stopPropagation()}>
            <h2>{t('bat.slot', { n: Number(edit.slot) + 1 })}</h2>
            <div className="form-grid">
              <label className="field">
                {t('bat.fieldName')}
                <input
                  value={String(edit.name ?? '')}
                  maxLength={9}
                  onChange={(ev) => setEdit({ ...edit, name: ev.target.value })}
                />
              </label>
              <label className="field">
                {t('bat.fieldType')}
                <select
                  value={String(edit.battery_type ?? '')}
                  onChange={(ev) => setEditNum('battery_type', ev.target.value)}
                >
                  {typeOptions.map(([k, label]) => (
                    <option key={k} value={k}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                {t('bat.fieldCells')}
                <input
                  type="number"
                  min={1}
                  value={String(edit.cells ?? '')}
                  onChange={(ev) => setEditNum('cells', ev.target.value)}
                />
              </label>
              <label className="field">
                {t('bat.fieldCapacity')}
                <input
                  type="number"
                  min={0}
                  value={String(edit.capacity_mAh ?? '')}
                  onChange={(ev) => setEditNum('capacity_mAh', ev.target.value)}
                />
              </label>
              <label className="field">
                {t('bat.fieldCharge')}
                <input
                  type="number"
                  min={0}
                  value={String(edit.charge_mA ?? '')}
                  onChange={(ev) => setEditNum('charge_mA', ev.target.value)}
                />
              </label>
              <label className="field">
                {t('bat.fieldDischarge')}
                <input
                  type="number"
                  min={0}
                  value={String(edit.discharge_mA ?? '')}
                  onChange={(ev) => setEditNum('discharge_mA', ev.target.value)}
                />
              </label>
              <label className="field">
                {t('bat.fieldPause')}
                <input
                  type="number"
                  min={0}
                  value={String(edit.pause_s ?? '')}
                  onChange={(ev) => setEditNum('pause_s', ev.target.value)}
                />
              </label>
            </div>
            <div className="row" style={{ marginTop: '1rem' }}>
              <button className="primary" onClick={save}>
                {t('common.save')}
              </button>
              <button onClick={() => setEdit(null)}>{t('common.cancel')}</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
