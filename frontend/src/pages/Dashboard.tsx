import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { ChartModeToggle, ChartPanel } from '../components/ChartPanel'
import type { SeriesMode } from '../components/LiveChart'
import { useChannelSeries } from '../hooks/useChannelSeries'
import { useCapabilities } from '../capabilities'
import { useLive } from '../live'
import { useLocale } from '../locale'
import { stageBadgeClass } from '../stageBadge'

function fmt(n: number | null | undefined, digits = 3) {
  if (n === null || n === undefined) return '—'
  return n.toFixed(digits)
}

function ChannelCard({ ch }: { ch: number }) {
  const { channels, measurements } = useLive()
  const { t, stage } = useLocale()
  const c = channels.find((x) => x.channel === ch)
  const m = measurements.find((x) => x.channel === ch)
  const points = useChannelSeries(ch)
  const running = c && c.stage_name !== 'Leerlauf'
  const [chartMode, setChartMode] = useState<SeriesMode>('ui')

  return (
    <article className={`channel channel-compact${running ? ' channel-running' : ''}`}>
      <header>
        <h2>{t('common.channelN', { n: ch + 1 })}</h2>
        <span className={`badge ${stageBadgeClass(c?.stage_name)}`}>{stage(c?.stage_name)}</span>
      </header>
      <div className="channel-meta">
        {c?.program_name || t('dash.noProgram')} · {c?.battery_type_name || '—'} · {c?.cells ?? '—'}{' '}
        {t('dash.cellsSuffix')}
      </div>
      <div className="metrics">
        <div className="metric">
          <label>{t('common.voltage')}</label>
          <strong>{fmt(m?.voltage_V)} V</strong>
        </div>
        <div className="metric">
          <label>{t('common.current')}</label>
          <strong>{fmt(m?.current_mA, 1)} mA</strong>
        </div>
        <div className="metric">
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
        <button className="danger" disabled={!running} onClick={() => api.activity(ch, true)}>
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

export function Dashboard() {
  const { connection } = useLive()
  const { capabilities } = useCapabilities()
  const { t } = useLocale()
  const channels = Array.from({ length: capabilities.channel_count }, (_, i) => i)

  return (
    <div className="page-channels">
      <div className="page-channels-head">
        <h1>{t('dash.title')}</h1>
        <Link className="btn primary" to="/start">
          {t('dash.startProcess')}
        </Link>
      </div>

      {!connection?.connected && (
        <div className="toast">
          {t('dash.notConnected')} <Link to="/settings">{t('dash.toSettings')}</Link> {t('dash.orSimulator')}
        </div>
      )}

      <div className="grid-2 grid-channels">
        {channels.map((ch) => (
          <ChannelCard key={ch} ch={ch} />
        ))}
      </div>
    </div>
  )
}
