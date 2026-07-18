import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

export type ChartPoint = { t: number; v: number | null; i: number | null; c?: number | null }
export type SeriesMode = 'ui' | 'cap'

const DEFAULT_HEIGHT = 280
const MIN_WIDTH = 120
const MIN_X_SPAN = 30 // seconds — avoids dense tick raster with tiny ranges

export const COLOR_U = '#3c8dbc'
export const COLOR_I = '#ec6a0c'
export const COLOR_C = '#00a65a'

/** Scale pixel sizes with root font-size (2K/4K fluid UI). */
function uiPx(px: number): number {
  if (typeof document === 'undefined') return px
  const fs = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
  return Math.round(px * (fs / 16))
}

function xRange(_u: uPlot, min: number, max: number): [number, number] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, MIN_X_SPAN]
  if (max - min < MIN_X_SPAN) return [min, min + MIN_X_SPAN]
  return [min, max]
}

/** Keep voltage axis usable when all samples are identical. */
function vRange(_u: uPlot, min: number, max: number): [number, number] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 10]
  if (min === max) {
    const pad = Math.max(0.5, Math.abs(min) * 0.08)
    return [min - pad, max + pad]
  }
  const pad = (max - min) * 0.08
  return [min - pad, max + pad]
}

/**
 * Current axis: when I≈0 for all points, auto-scale collapses (min=max=0)
 * and uPlot draws the series outside the plot — orange line under the chart.
 */
function iRange(_u: uPlot, min: number, max: number): [number, number] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 100]
  if (min === max) {
    if (Math.abs(min) < 1e-6) return [0, 100]
    const pad = Math.max(10, Math.abs(min) * 0.15)
    return [min - pad, max + pad]
  }
  const span = max - min
  if (span < 10) {
    const lo = Math.min(0, min)
    return [lo, Math.max(lo + 100, max + 10)]
  }
  const pad = span * 0.08
  return [min - pad, max + pad]
}

function cRange(_u: uPlot, min: number, max: number): [number, number] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 100]
  if (min === max) {
    if (Math.abs(min) < 1e-6) return [0, 100]
    const pad = Math.max(5, Math.abs(min) * 0.12)
    return [Math.max(0, min - pad), max + pad]
  }
  const pad = (max - min) * 0.08
  return [Math.max(0, min - pad), max + pad]
}

function toUiData(pts: ChartPoint[]): uPlot.AlignedData {
  return [pts.map((p) => p.t), pts.map((p) => p.v ?? null), pts.map((p) => p.i ?? null)]
}

function toCapData(pts: ChartPoint[]): uPlot.AlignedData {
  return [pts.map((p) => p.t), pts.map((p) => p.c ?? null)]
}

export function LiveChart({
  points,
  title,
  height = DEFAULT_HEIGHT,
  compact = false,
  seriesMode = 'ui',
}: {
  points: ChartPoint[]
  title?: string
  height?: number
  compact?: boolean
  seriesMode?: SeriesMode
}) {
  const el = useRef<HTMLDivElement>(null)
  const plot = useRef<uPlot | null>(null)
  const pointsRef = useRef(points)
  pointsRef.current = points

  useEffect(() => {
    const node = el.current
    if (!node) return

    const syncData = (u: uPlot) => {
      const pts = pointsRef.current
      u.setData(seriesMode === 'cap' ? toCapData(pts) : toUiData(pts))
    }

    const plotHeight = () => {
      if (compact) {
        const h = Math.floor(node.clientHeight || uiPx(height))
        return Math.max(uiPx(90), h)
      }
      return uiPx(height)
    }

    const ensurePlot = (width: number) => {
      if (width < uiPx(MIN_WIDTH)) return
      const h = plotHeight()
      const axisSm = uiPx(compact ? 36 : 48)
      const axisMd = uiPx(compact ? 44 : 58)
      if (plot.current) {
        plot.current.setSize({ width, height: h })
        return
      }

      const opts: uPlot.Options =
        seriesMode === 'cap'
          ? {
              width,
              height: h,
              title: compact ? undefined : title,
              legend: { show: !compact },
              cursor: { show: true },
              series: [{}, { label: 'C (mAh)', stroke: COLOR_C, width: compact ? 1.5 : 2 }],
              axes: [
                {
                  stroke: '#8e989d',
                  grid: { stroke: 'rgba(142, 152, 157, 0.12)', width: 1 },
                  size: axisSm,
                  values: (_u, vals) => vals.map((v) => (Math.abs(v) >= 10 ? v.toFixed(0) : v.toFixed(1))),
                },
                {
                  stroke: COLOR_C,
                  grid: { stroke: 'rgba(142, 152, 157, 0.12)', width: 1 },
                  size: axisMd,
                  values: (_u, vals) => vals.map((v) => v.toFixed(v >= 100 ? 0 : 1)),
                },
              ],
              scales: {
                x: { time: false, range: xRange },
                y: { auto: true, range: cRange },
              },
              padding: compact ? [4, 4, 0, 0] : [8, 8, 0, 0],
            }
          : {
              width,
              height: h,
              title: compact ? undefined : title,
              legend: { show: !compact },
              cursor: { show: true },
              series: [
                {},
                { label: 'U (V)', stroke: COLOR_U, width: compact ? 1.5 : 2 },
                { label: 'I (mA)', stroke: COLOR_I, width: compact ? 1.25 : 1.5, scale: 'i' },
              ],
              axes: [
                {
                  stroke: '#8e989d',
                  grid: { stroke: 'rgba(142, 152, 157, 0.12)', width: 1 },
                  size: axisSm,
                  values: (_u, vals) => vals.map((v) => (Math.abs(v) >= 10 ? v.toFixed(0) : v.toFixed(1))),
                },
                {
                  stroke: COLOR_U,
                  grid: { stroke: 'rgba(142, 152, 157, 0.12)', width: 1 },
                  size: axisMd,
                  values: (_u, vals) => vals.map((v) => v.toFixed(v >= 10 ? 1 : 2)),
                },
                {
                  scale: 'i',
                  side: 1,
                  stroke: COLOR_I,
                  grid: { show: false },
                  size: axisMd,
                  values: (_u, vals) => vals.map((v) => v.toFixed(0)),
                },
              ],
              scales: {
                x: { time: false, range: xRange },
                y: { auto: true, range: vRange },
                i: { auto: true, range: iRange },
              },
              padding: compact ? [4, 4, 0, 0] : [8, 8, 0, 0],
            }

      plot.current = new uPlot(opts, seriesMode === 'cap' ? [[], []] : [[], [], []], node)
      syncData(plot.current)
    }

    let lastFs = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
    const ro = new ResizeObserver((entries) => {
      const width = Math.floor(entries[0]?.contentRect.width ?? node.clientWidth)
      const fs = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
      if (plot.current && Math.abs(fs - lastFs) > 0.2) {
        plot.current.destroy()
        plot.current = null
        lastFs = fs
      }
      ensurePlot(width)
    })
    ro.observe(node)

    requestAnimationFrame(() => ensurePlot(Math.floor(node.clientWidth)))

    return () => {
      ro.disconnect()
      plot.current?.destroy()
      plot.current = null
    }
  }, [title, height, compact, seriesMode])

  useEffect(() => {
    if (!plot.current) return
    plot.current.setData(seriesMode === 'cap' ? toCapData(points) : toUiData(points))
  }, [points, seriesMode])

  return (
    <div
      className={`chart-wrap${compact ? ' chart-wrap-compact' : ''}`}
      ref={el}
      style={compact ? undefined : { height: 'auto', minHeight: `${height / 16 + 4.5}rem` }}
    />
  )
}
