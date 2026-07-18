import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useLocale } from '../locale'

export function BatteryDatabase() {
  const { t } = useLocale()
  const [entries, setEntries] = useState<Record<string, unknown>[]>([])
  const [edit, setEdit] = useState<Record<string, unknown> | null>(null)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = async () => {
    const res = await api.batteryDb()
    setEntries(res.entries)
  }

  useEffect(() => {
    load().catch((e) => setErr(String(e.message || e)))
  }, [])

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

  const editFields = [
    ['name', 'bat.fieldName'],
    ['battery_type', 'bat.fieldType'],
    ['cells', 'bat.fieldCells'],
    ['capacity_mAh', 'bat.fieldCapacity'],
    ['charge_mA', 'bat.fieldCharge'],
    ['discharge_mA', 'bat.fieldDischarge'],
    ['pause_s', 'bat.fieldPause'],
  ] as const

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
                <td>{String(e.battery_type_name || e.battery_type)}</td>
                <td className="mono">{String(e.cells)}</td>
                <td className="mono">{String(e.capacity_mAh)}</td>
                <td className="mono">{String(e.charge_mA)}</td>
                <td className="mono">{String(e.discharge_mA)}</td>
                <td>
                  <button disabled={busy} onClick={() => setEdit({ ...e })}>
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
              {editFields.map(([k, labelKey]) => (
                <label className="field" key={k}>
                  {t(labelKey)}
                  <input
                    value={String(edit[k] ?? '')}
                    maxLength={k === 'name' ? 9 : undefined}
                    onChange={(ev) =>
                      setEdit({
                        ...edit,
                        [k]: k === 'name' ? ev.target.value : Number(ev.target.value),
                      })
                    }
                  />
                </label>
              ))}
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
