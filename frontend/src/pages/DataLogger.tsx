import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { useCapabilities } from '../capabilities'
import { LiveChart } from '../components/LiveChart'
import { useLocale } from '../locale'

export function DataLogger() {
  const { t } = useLocale()
  const { capabilities } = useCapabilities()
  const [channel, setChannel] = useState(0)
  const channelList = Array.from({ length: capabilities.channel_count }, (_, i) => i)
  const [sessions, setSessions] = useState<Record<string, unknown>[]>([])
  const [session, setSession] = useState<Record<string, unknown> | null>(null)
  const [sessionId, setSessionId] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const loadList = async () => {
    const res = await api.archive()
    setSessions(res.sessions)
  }

  useEffect(() => {
    loadList().catch((e) => setErr(String(e.message || e)))
  }, [])

  const points = useMemo(() => {
    const samples =
      (session?.samples as {
        voltage_V: number | null
        current_mA: number | null
        capacity_mAh?: number | null
      }[]) || []
    return samples.map((s, i) => ({
      t: i * 5,
      v: s.voltage_V,
      i: s.current_mA,
      c: s.capacity_mAh ?? null,
    }))
  }, [session])

  const download = async () => {
    setBusy(true)
    setErr('')
    setMsg('')
    try {
      const res = await api.readLogger(channel)
      setSession(res.logger)
      setSessionId(String(res.archive?.id || ''))
      const archived = res.archive ? t('log.archivedAs', { id: String(res.archive.id) }) : ''
      setMsg(t('log.readOk', { n: channel + 1 }) + archived)
      await loadList()
    } catch (e) {
      setErr(String((e as Error).message || e))
    } finally {
      setBusy(false)
    }
  }

  const openSession = async (id: string) => {
    const data = await api.archiveSession(id)
    setSession(data)
    setSessionId(id)
  }

  const deleteSession = async (id: string) => {
    setErr('')
    setMsg('')
    try {
      await api.deleteArchive(id)
      if (sessionId === id) {
        setSession(null)
        setSessionId('')
      }
      setMsg(t('log.deleted'))
      await loadList()
    } catch (e) {
      setErr(String((e as Error).message || e))
    }
  }

  const deleteAllSessions = async () => {
    setErr('')
    setMsg('')
    try {
      const res = await api.deleteAllArchive()
      setSession(null)
      setSessionId('')
      setMsg(t('log.deletedAll', { n: res.deleted }))
      await loadList()
    } catch (e) {
      setErr(String((e as Error).message || e))
    }
  }

  return (
    <>
      <h1>{t('log.title')}</h1>
      <p className="lead">{t('log.lead')}</p>

      <div className="panel row">
        <label className="field" style={{ minWidth: 140 }}>
          {t('log.channel')}
          <select value={channel} onChange={(e) => setChannel(Number(e.target.value))}>
            {channelList.map((n) => (
              <option key={n} value={n}>
                {t('common.channelN', { n: n + 1 })}
              </option>
            ))}
          </select>
        </label>
        <button className="primary" disabled={busy} onClick={download}>
          {busy ? t('log.reading') : t('log.readDevice')}
        </button>
        <button className="danger" onClick={() => api.clearLogger(channel).then(() => setMsg(t('log.cleared')))}>
          {t('log.clear')}
        </button>
      </div>

      {msg && <div className="toast ok">{msg}</div>}
      {err && <div className="toast error">{err}</div>}

      {session && (
        <div className="panel stack">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              {t('common.channelN', { n: (Number(session.channel) || 0) + 1 })} ·{' '}
              {String((session.header as { program_name?: string })?.program_name || '')} ·{' '}
              {String(session.sample_count || 0)} {t('log.samples')}
            </div>
            <div className="row">
              {sessionId && (
                <>
                  <a className="btn" href={`/api/archive/${sessionId}/export/csv`}>
                    CSV
                  </a>
                  <a className="btn" href={`/api/archive/${sessionId}/export/json`}>
                    JSON
                  </a>
                  <a
                    className="btn primary"
                    href={`/api/archive/${sessionId}/export/pdf`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    PDF
                  </a>
                </>
              )}
            </div>
          </div>
          <div className="detail-charts">
            <LiveChart points={points} title={t('log.chartTitle')} height={180} seriesMode="ui" />
            <LiveChart points={points} title={t('log.chartTitleCap')} height={180} seriesMode="cap" />
          </div>
        </div>
      )}

      <div className="panel">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>{t('log.archive')}</h2>
          <button className="danger" disabled={!sessions.length} onClick={deleteAllSessions}>
            {t('log.deleteAll')}
          </button>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>{t('log.colId')}</th>
              <th>{t('log.colChannel')}</th>
              <th>{t('log.colSamples')}</th>
              <th>{t('log.colSaved')}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={String(s.id)}>
                <td className="mono">{String(s.id)}</td>
                <td>{Number(s.channel) + 1}</td>
                <td>{String(s.sample_count)}</td>
                <td>{String(s.saved_at || '')}</td>
                <td className="row">
                  <button onClick={() => openSession(String(s.id))}>{t('common.open')}</button>
                  <a
                    className="btn"
                    href={`/api/archive/${s.id}/export/pdf`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    PDF
                  </a>
                  <a className="btn" href={`/api/archive/${s.id}/export/csv`}>
                    CSV
                  </a>
                  <button className="danger" onClick={() => deleteSession(String(s.id))}>
                    {t('log.delete')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
