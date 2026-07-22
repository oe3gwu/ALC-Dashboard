import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { useCapabilities } from '../capabilities'
import { LiveChart } from '../components/LiveChart'
import { useChannelSeries } from '../hooks/useChannelSeries'
import { useLive } from '../live'
import { useLocale } from '../locale'

export function ChannelDetail() {
  const { id } = useParams()
  const ch = Number(id || 0)
  const { channels, measurements, refresh } = useLive()
  const { capabilities } = useCapabilities()
  const { t, stage } = useLocale()
  const c = channels.find((x) => x.channel === ch)
  const m = measurements.find((x) => x.channel === ch)
  const points = useChannelSeries(ch)
  const channelList = Array.from({ length: capabilities.channel_count }, (_, i) => i)
  const running = Boolean(c && !c.idle && c.stage_name !== 'Leerlauf')
  const [scaleReset, setScaleReset] = useState(0)
  const [zoomUi, setZoomUi] = useState(false)
  const [zoomCap, setZoomCap] = useState(false)
  const zoomed = zoomUi || zoomCap

  const onStop = async () => {
    await api.activity(ch, true)
    await refresh()
  }

  const onResumeLive = () => {
    setScaleReset((n) => n + 1)
    setZoomUi(false)
    setZoomCap(false)
  }

  return (
    <div className="page-detail">
      <h1>{t('common.channelN', { n: ch + 1 })}</h1>
      <p className="lead">
        {stage(c?.stage_name)} · {c?.battery_type_name || '—'}
        {c && !c.idle && c.program_name ? ` · ${c.program_name}` : ''}
      </p>
      <div className="row page-detail-actions">
        <Link className="btn" to="/">
          {t('detail.allChannels')}
        </Link>
        {channelList.map((n) => (
          <Link key={n} className="btn" to={`/channel/${n}`}>
            {t('common.channelN', { n: n + 1 })}
          </Link>
        ))}
        <Link className="btn primary" to={`/start?ch=${ch}`}>
          {t('detail.startProcess')}
        </Link>
        <button className="danger" onClick={() => void onStop()}>
          {t('common.stop')}
        </button>
        <button
          type="button"
          className="btn detail-chart-refresh"
          disabled={!running || !zoomed}
          title={t('detail.resetZoomTitle')}
          aria-label={t('detail.resetZoomTitle')}
          onClick={onResumeLive}
        >
          {t('detail.resetZoom')}
        </button>
      </div>
      <div className="panel page-detail-panel">
        <div className="metrics page-detail-metrics">
          <div className="metric metric-u">
            <label>{t('common.voltage')}</label>
            <strong>{m?.voltage_V?.toFixed(3) ?? '—'} V</strong>
          </div>
          <div className="metric metric-i">
            <label>{t('common.current')}</label>
            <strong>{m?.current_mA?.toFixed(1) ?? '—'} mA</strong>
          </div>
          <div className="metric metric-c">
            <label>{t('common.capacity')}</label>
            <strong>{m?.capacity_mAh?.toFixed(1) ?? '—'} mAh</strong>
          </div>
        </div>
        <div className="detail-charts">
          <LiveChart
            key={`ui-${ch}`}
            points={points}
            title={t('chart.titleUi', { n: ch + 1 })}
            height={180}
            seriesMode="ui"
            allowZoom
            scaleReset={scaleReset}
            onZoomLockChange={setZoomUi}
          />
          <LiveChart
            key={`cap-${ch}`}
            points={points}
            title={t('chart.titleCap', { n: ch + 1 })}
            height={180}
            seriesMode="cap"
            allowZoom
            scaleReset={scaleReset}
            onZoomLockChange={setZoomCap}
          />
        </div>
      </div>
    </div>
  )
}
