import { LiveChart, type ChartPoint, type SeriesMode } from './LiveChart'

export function ChartPanel({
  points,
  title,
  height,
  compact = false,
  seriesMode = 'ui',
}: {
  points: ChartPoint[]
  title?: string
  height?: number
  compact?: boolean
  seriesMode?: SeriesMode
}) {
  return (
    <div className={`chart-panel${compact ? ' chart-panel-compact' : ''}`}>
      <LiveChart
        key={seriesMode}
        points={points}
        title={title}
        height={height}
        compact={compact}
        seriesMode={seriesMode}
      />
    </div>
  )
}

export function ChartModeToggle({
  mode,
  onChange,
  label,
  uiLabel,
  capLabel,
}: {
  mode: SeriesMode
  onChange: (m: SeriesMode) => void
  label: string
  uiLabel: string
  capLabel: string
}) {
  return (
    <div className="chart-mode-toggle" role="group" aria-label={label}>
      <button type="button" className={mode === 'ui' ? 'active' : undefined} onClick={() => onChange('ui')}>
        {uiLabel}
      </button>
      <button type="button" className={mode === 'cap' ? 'active' : undefined} onClick={() => onChange('cap')}>
        {capLabel}
      </button>
    </div>
  )
}
