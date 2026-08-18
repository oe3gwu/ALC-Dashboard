import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { ChartModeToggle, ChartPanel } from '../components/ChartPanel'
import type { SeriesMode } from '../components/LiveChart'
import { useChannelSeries } from '../hooks/useChannelSeries'
import { useCapabilities } from '../capabilities'
import { useLive } from '../live'
import { useLocale } from '../locale'
import { clearSeries } from '../liveSeries'
import { stageBadgeClass } from '../stageBadge'

function fmt(n: number | null | undefined, digits = 3) {
  if (n === null || n === undefined) return '—'
  return n.toFixed(digits)
}

function ChannelCard({ ch }: { ch: number }) {
  const { channels, measurements, refresh } = useLive()
  const { t, stage } = useLocale()
  const c = channels.find((x) => x.channel === ch)
  const m = measurements.find((x) => x.channel === ch)
  const points = useChannelSeries(ch)
  const idle = !c || c.stage_name === 'Leerlauf' || c.idle
  const running = Boolean(c) && !idle
  const hasConfig = Boolean(c && c.battery_type !== 0xff && (c.cells ?? 0) > 0)
  const [chartMode, setChartMode] = useState<SeriesMode>('ui')
  const [stopping, setStopping] = useState(false)

  const onStop = async () => {
    setStopping(true)
    try {
      await api.activity(ch, true)
      clearSeries(ch, true)
      await refresh()
    } finally {
      setStopping(false)
    }
  }

  return (
    <article className={`channel channel-compact${running ? ' channel-running' : ''}`}>
      <header>
        <h2>{t('common.channelN', { n: ch + 1 })}</h2>
        <span className={`badge ${stageBadgeClass(c?.stage_name)}`}>{stage(c?.stage_name)}</span>
      </header>
      <div className="channel-meta">
        {running ? (
          <>
            {c?.program_name || t('dash.noProgram')} · {c?.battery_type_name || '—'} · {c?.cells ?? '—'}{' '}
            {t('dash.cellsSuffix')}
          </>
        ) : hasConfig ? (
          <>
            {t('dash.storedConfig')} · {c?.battery_type_name || '—'} · {c?.cells ?? '—'} {t('dash.cellsSuffix')}
          </>
        ) : (
          t('dash.noProgram')
        )}
      </div>
      <div className="metrics">
        <div className="metric metric-u">
          <label>{t('common.voltage')}</label>
          <strong>{fmt(m?.voltage_V)} V</strong>
        </div>
        <div className="metric metric-i">
          <label>{t('common.current')}</label>
          <strong>{fmt(m?.current_mA, 1)} mA</strong>
        </div>
        <div className="metric metric-c">
          <label>{t('common.capacity')}</label>
          <strong>{fmt(m?.capacity_mAh, 1)} mAh</strong>
        </div>
      </div>
      <div className="actions">
        <Link className="btn" to={`/channel/${ch}`}>
          {t('common.detail')}
        </Link>
        <Link className="btn" to={`/start?ch=${ch}`}>
          {t('common.start')}
        </Link>
        <button className="danger" disabled={stopping} onClick={() => void onStop()}>
          {t('common.stop')}
        </button>
        <ChartModeToggle
          mode={chartMode}
          onChange={setChartMode}
          label={t('chart.modeLabel')}
          uiLabel={t('chart.modeUi')}
          capLabel={t('chart.modeCap')}
        />
      </div>
      <ChartPanel points={points} height={128} compact seriesMode={chartMode} />
    </article>
  )
}

/** Delay offline banner so F5 / slow first WS does not flash "Nicht verbunden". */
const OFFLINE_BANNER_DELAY_MS = 3000

export function Dashboard() {
  const { connection } = useLive()
  const { capabilities } = useCapabilities()
  const { t } = useLocale()
  const channels = Array.from({ length: capabilities.channel_count }, (_, i) => i)
  const [showOffline, setShowOffline] = useState(false)
  const [shutdownOpen, setShutdownOpen] = useState(false)
  const [shutdownBusy, setShutdownBusy] = useState(false)
  const [shutdownMsg, setShutdownMsg] = useState('')
  const [shutdownErr, setShutdownErr] = useState('')

  useEffect(() => {
    if (!connection || connection.connected) {
      setShowOffline(false)
      return
    }
    const id = window.setTimeout(() => setShowOffline(true), OFFLINE_BANNER_DELAY_MS)
    return () => window.clearTimeout(id)
  }, [connection])

  const doShutdown = async () => {
    setShutdownErr('')
    setShutdownBusy(true)
    try {
      await api.shutdownHost()
      setShutdownMsg(t('dash.shutdownOk'))
      setShutdownOpen(false)
    } catch (e) {
      setShutdownErr(String((e as Error).message || e))
    } finally {
      setShutdownBusy(false)
    }
  }

  return (
    <div className="page-channels">
      <div className="page-channels-head">
        <h1>{t('dash.title')}</h1>
        <div className="page-channels-head-actions">
          <Link className="btn primary" to="/start">
            {t('dash.startProcess')}
          </Link>
          <button
            type="button"
            className="primary-danger"
            onClick={() => {
              setShutdownErr('')
              setShutdownOpen(true)
            }}
            disabled={shutdownBusy}
          >
            {t('dash.shutdown')}
          </button>
        </div>
      </div>

      {showOffline && (
        <div className="toast">
          {t('dash.notConnected')} <Link to="/settings">{t('dash.toSettings')}</Link> {t('dash.orSimulator')}
        </div>
      )}
      {shutdownMsg && (
        <div className="toast ok" role="status">
          {shutdownMsg}
        </div>
      )}
      {shutdownErr && !shutdownOpen && (
        <div className="toast error" role="alert">
          {shutdownErr}
        </div>
      )}

      <div className="grid-2 grid-channels">
        {channels.map((ch) => (
          <ChannelCard key={ch} ch={ch} />
        ))}
      </div>

      {shutdownOpen && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="shutdown-confirm-title"
          onClick={() => !shutdownBusy && setShutdownOpen(false)}
        >
          <div className="modal" onClick={(ev) => ev.stopPropagation()}>
            <h2 id="shutdown-confirm-title">{t('dash.shutdownTitle')}</h2>
            <p className="lead" style={{ marginTop: 0 }}>
              {t('dash.shutdownLead')}
            </p>
            {shutdownErr && (
              <div className="toast error" role="alert">
                {shutdownErr}
              </div>
            )}
            <div className="row">
              <button type="button" onClick={() => setShutdownOpen(false)} disabled={shutdownBusy}>
                {t('common.cancel')}
              </button>
              <button
                type="button"
                className="primary-danger"
                onClick={() => void doShutdown()}
                disabled={shutdownBusy}
              >
                {t('dash.shutdownConfirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
