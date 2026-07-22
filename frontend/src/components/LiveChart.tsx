import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import { useLocale } from '../locale'

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
  if (!Number.isFinite(max)) return [0, MIN_X_SPAN]
  const dataMin = Number.isFinite(min) ? min : 0
  // Full history from process start → pin X at 0
  if (dataMin <= 0.5) {
    return [0, Math.max(max, MIN_X_SPAN)]
  }
  // Offset history (e.g. restored session) → keep full visible span
  const span = Math.max(max - dataMin, MIN_X_SPAN)
  return [dataMin, dataMin + span]
}

/**
 * Absolute Y scale: always pin 0 (never zoom into a band that hides zero).
 * Negative values (e.g. discharge current) keep 0 in the span.
 */
function absoluteRange(min: number, max: number, fallbackMax: number, padRatio = 0.08): [number, number] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, fallbackMax]
  let lo = Math.min(0, min)
  let hi = Math.max(0, max)
  if (hi === lo) return [0, fallbackMax]
  const pad = Math.max((hi - lo) * padRatio, Number.EPSILON)
  if (lo >= 0) {
    // Positive-only: floor hard at 0
    lo = 0
    hi += pad
  } else if (hi <= 0) {
    hi = 0
    lo -= pad
  } else {
    lo -= pad
    hi += pad
  }
  if (hi - lo < fallbackMax * 0.05) {
    if (lo >= 0) hi = Math.max(hi, fallbackMax)
    else if (hi <= 0) lo = Math.min(lo, -fallbackMax)
  }
  return [lo, hi]
}

function vRange(_u: uPlot, min: number, max: number): [number, number] {
  return absoluteRange(min, max, 10)
}

function iRange(_u: uPlot, min: number, max: number): [number, number] {
  return absoluteRange(min, max, 100)
}

function cRange(_u: uPlot, min: number, max: number): [number, number] {
  return absoluteRange(min, max, 100)
}

function toUiData(pts: ChartPoint[]): uPlot.AlignedData {
  return [pts.map((p) => p.t), pts.map((p) => p.v ?? null), pts.map((p) => p.i ?? null)]
}

function toCapData(pts: ChartPoint[]): uPlot.AlignedData {
  return [pts.map((p) => p.t), pts.map((p) => p.c ?? null)]
}

function fmtTime(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return String(Math.round(v))
}

function fmtU(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toFixed(v >= 10 ? 1 : 2)
}

function fmtI(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toFixed(0)
}

function fmtC(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toFixed(v >= 100 ? 0 : 1)
}

export function LiveChart({
  points,
  title,
  height = DEFAULT_HEIGHT,
  compact = false,
  seriesMode = 'ui',
  allowZoom = false,
  scaleReset = 0,
  onZoomLockChange,
}: {
  points: ChartPoint[]
  title?: string
  height?: number
  compact?: boolean
  seriesMode?: SeriesMode
  /** Drag-zoom (detail charts only). Overview stays live-auto. */
  allowZoom?: boolean
  /** Increment to unlock zoom and resume auto scales (refresh button). */
  scaleReset?: number
  /** Fired when user zooms in/out of live auto-scale. */
  onZoomLockChange?: (locked: boolean) => void
}) {
  const { t, locale } = useLocale()
  const el = useRef<HTMLDivElement>(null)
  const plot = useRef<uPlot | null>(null)
  const pointsRef = useRef(points)
  const ensurePlotRef = useRef<(width?: number) => void>(() => {})
  const retryRaf = useRef<number | null>(null)
  /** Keep user zoom across live setData(); cleared via scaleReset. */
  const zoomLockRef = useRef(false)
  const onZoomLockChangeRef = useRef(onZoomLockChange)
  onZoomLockChangeRef.current = onZoomLockChange
  pointsRef.current = points

  const setZoomLock = (locked: boolean) => {
    if (zoomLockRef.current === locked) return
    zoomLockRef.current = locked
    onZoomLockChangeRef.current?.(locked)
  }

  useEffect(() => {
    const node = el.current
    if (!node) return

    const labelT = t('chart.seriesTime')
    const labelU = t('chart.seriesU')
    const labelI = t('chart.seriesI')
    const labelC = t('chart.seriesC')

    const syncData = (u: uPlot) => {
      const pts = pointsRef.current
      // false = do not reset scales (preserves drag-zoom while live data arrives)
      u.setData(seriesMode === 'cap' ? toCapData(pts) : toUiData(pts), !zoomLockRef.current)
    }

    const zoomHooks: uPlot.Hooks.Arrays | undefined = allowZoom
      ? {
          setSelect: [
            (u) => {
              if (u.select.width > 0 || u.select.height > 0) {
                setZoomLock(true)
              }
            },
          ],
        }
      : undefined

    const cursorOpts: uPlot.Cursor = allowZoom
      ? { show: true, drag: { x: true, y: true, setScale: true } }
      : { show: true, drag: { x: false, y: false, setScale: false } }

    const plotHeight = () => {
      if (compact) {
        const h = Math.floor(node.clientHeight || uiPx(height))
        return Math.max(uiPx(90), h)
      }
      return uiPx(height)
    }

    const scheduleRetry = () => {
      if (retryRaf.current != null) return
      retryRaf.current = requestAnimationFrame(() => {
        retryRaf.current = null
        ensurePlotRef.current(Math.floor(node.clientWidth))
      })
    }

    const ensurePlot = (width = Math.floor(node.clientWidth)) => {
      if (width < uiPx(MIN_WIDTH)) {
        scheduleRetry()
        return
      }
      const h = plotHeight()
      const axisSm = uiPx(compact ? 36 : 48)
      const axisMd = uiPx(compact ? 44 : 58)
      if (plot.current) {
        plot.current.setSize({ width, height: h })
        syncData(plot.current)
        return
      }

      const opts: uPlot.Options =
        seriesMode === 'cap'
          ? {
              width,
              height: h,
              title: compact ? undefined : title,
              legend: { show: !compact },
              cursor: cursorOpts,
              hooks: zoomHooks,
              series: [
                { label: labelT, value: (_u, v) => fmtTime(v) },
                { label: labelC, stroke: COLOR_C, width: compact ? 1.5 : 2, value: (_u, v) => fmtC(v) },
              ],
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
              cursor: cursorOpts,
              hooks: zoomHooks,
              series: [
                { label: labelT, value: (_u, v) => fmtTime(v) },
                { label: labelU, stroke: COLOR_U, width: compact ? 1.5 : 2, value: (_u, v) => fmtU(v) },
                {
                  label: labelI,
                  stroke: COLOR_I,
                  width: compact ? 1.25 : 1.5,
                  scale: 'i',
                  value: (_u, v) => fmtI(v),
                },
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

      zoomLockRef.current = false
      onZoomLockChangeRef.current?.(false)
      plot.current = new uPlot(opts, seriesMode === 'cap' ? [[], []] : [[], [], []], node)
      syncData(plot.current)
    }

    ensurePlotRef.current = ensurePlot

    // Locale/label change must rebuild the plot
    if (plot.current) {
      plot.current.destroy()
      plot.current = null
    }
    zoomLockRef.current = false
    onZoomLockChangeRef.current?.(false)

    let lastFs = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
    const ro = new ResizeObserver((entries) => {
      const width = Math.floor(entries[0]?.contentRect.width ?? node.clientWidth)
      const fs = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
      if (plot.current && Math.abs(fs - lastFs) > 0.2) {
        plot.current.destroy()
        plot.current = null
        zoomLockRef.current = false
        onZoomLockChangeRef.current?.(false)
        lastFs = fs
      }
      ensurePlot(width)
    })
    ro.observe(node)

    requestAnimationFrame(() => ensurePlot(Math.floor(node.clientWidth)))

    return () => {
      ro.disconnect()
      if (retryRaf.current != null) {
        cancelAnimationFrame(retryRaf.current)
        retryRaf.current = null
      }
      ensurePlotRef.current = () => {}
      plot.current?.destroy()
      plot.current = null
      zoomLockRef.current = false
      onZoomLockChangeRef.current?.(false)
    }
  }, [title, height, compact, seriesMode, locale, t, allowZoom])

  useEffect(() => {
    if (!plot.current) {
      ensurePlotRef.current()
      return
    }
    plot.current.setData(
      seriesMode === 'cap' ? toCapData(points) : toUiData(points),
      !zoomLockRef.current,
    )
  }, [points, seriesMode])

  useEffect(() => {
    if (scaleReset <= 0) return
    setZoomLock(false)
    if (!plot.current) return
    plot.current.setData(
      seriesMode === 'cap' ? toCapData(pointsRef.current) : toUiData(pointsRef.current),
      true,
    )
  }, [scaleReset, seriesMode])

  return (
    <div
      className={`chart-wrap${compact ? ' chart-wrap-compact' : ''}`}
      ref={el}
      style={compact ? undefined : { height: 'auto', minHeight: `${height / 16 + 4.5}rem` }}
    />
  )
}
