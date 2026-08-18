import type { ChannelParams, Measurement } from './api'

export type SeriesPoint = { t: number; v: number | null; i: number | null; c: number | null }

export type ServerChannelSeries = {
  t0: number
  points: SeriesPoint[]
}

type ChannelSeries = {
  t0: number
  points: SeriesPoint[]
}

const seriesByChannel = new Map<number, ChannelSeries>()
const listeners = new Set<() => void>()

let channelsSnap: ChannelParams[] = []
let measurementsSnap: Measurement[] = []
let intervalId: number | null = null
/** Empty live payloads (disconnect race) before accepting an empty snap. */
let emptySnapStreak = 0
const EMPTY_SNAP_STREAK = 3

type PendingSample = { v: number | null; i: number | null; c: number | null }
type MetricKey = 'v' | 'i' | 'c'
type MetricPending = { value: number | null; confirms: number }
type PendingState = Partial<Record<MetricKey, MetricPending>>
const pendingByChannel = new Map<number, PendingState>()
/** After Stop, do not start a new series until the channel is seen idle. */
const holdOffChannels = new Set<number>()
const readoutHold = new Map<number, PendingSample>()
const readoutPending = new Map<number, PendingState>()

const GLITCH_V_ABS = 0.15 // V
const GLITCH_V_REL = 0.04
const GLITCH_V_FLOOR = 0.05
const GLITCH_I_ABS = 60 // mA
const GLITCH_I_REL = 0.15
const GLITCH_I_FLOOR = 10
const GLITCH_C_ABS = 20 // mAh
const GLITCH_C_REL = 0.03
const GLITCH_C_FLOOR = 5
/** Confirms before accepting a non-collapse abrupt step (ramps, stage changes). */
const CONFIRM_DEFAULT = 3
/** Absolute capacity above this is treated as wire garbage. */
const CAPACITY_ABSURD = 15000
/** Scrub collapse/spike runs up to this many seconds between two stable neighbors. */
const SCRUB_RUN_MAX = 20
/** Trickle/top-off is often 50–100 mA; 120 mA hid those plateaus from collapse-hold. */
const STABLE_I_MA = 20

function isIdle(c: ChannelParams | undefined): boolean {
  if (!c) return true
  return Boolean(c.idle) || c.stage_name === 'Leerlauf'
}

function notify(): void {
  for (const listener of listeners) {
    try {
      listener()
    } catch {
      /* one bad subscriber must not stop other charts */
    }
  }
}

function dropLegacySessionKeys(): void {
  if (typeof sessionStorage === 'undefined') return
  try {
    for (const key of [
      'alc-live-series-v1',
      'alc-live-series-v2',
      'alc-live-series-v3',
      'alc-live-series-v4',
      'alc-live-series-v5',
      'alc-live-series-v6',
    ]) {
      sessionStorage.removeItem(key)
    }
  } catch {
    /* private mode */
  }
}

dropLegacySessionKeys()

function clearChannel(channel: number, silent = false): void {
  pendingByChannel.delete(channel)
  if (!seriesByChannel.has(channel)) return
  seriesByChannel.delete(channel)
  if (!silent) notify()
}

export function clearSeries(channel: number, holdOff = false): void {
  if (holdOff) holdOffChannels.add(channel)
  else holdOffChannels.delete(channel)
  readoutHold.delete(channel)
  readoutPending.delete(channel)
  clearChannel(channel)
}

export function clearAllSeries(): void {
  pendingByChannel.clear()
  holdOffChannels.clear()
  readoutHold.clear()
  readoutPending.clear()
  if (seriesByChannel.size === 0) return
  seriesByChannel.clear()
  notify()
}

/** Replace local charts from dashboard-process RAM (host/origin independent). */
export function replaceFromServer(channels: Record<string, ServerChannelSeries> | null | undefined): void {
  pendingByChannel.clear()
  seriesByChannel.clear()
  if (channels && typeof channels === 'object') {
    for (const [key, value] of Object.entries(channels)) {
      const ch = Number(key)
      if (!Number.isFinite(ch) || !value?.points || !Array.isArray(value.points)) continue
      if (holdOffChannels.has(ch)) continue
      const points = holdCollapses(scrubPoints(value.points.filter((p) => p && typeof p.t === 'number')))
      if (points.length === 0) continue
      seriesByChannel.set(ch, {
        t0: typeof value.t0 === 'number' ? value.t0 : Date.now(),
        points,
      })
    }
  }
  notify()
}

export function getSeries(channel: number): SeriesPoint[] {
  const pts = seriesByChannel.get(channel)?.points
  return pts ? holdCollapses(scrubPoints(pts)) : []
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function anyRunning(): boolean {
  return channelsSnap.some((c) => !isIdle(c))
}

function metricAbrupt(
  prev: number | null | undefined,
  next: number | null | undefined,
  key: MetricKey,
): boolean {
  if (prev == null || next == null) {
    return (prev == null) !== (next == null)
  }
  return Math.abs(prev - next) >= threshFor(key, prev)
}

function threshFor(key: MetricKey, ref?: number | null): number {
  const abs = key === 'v' ? GLITCH_V_ABS : key === 'i' ? GLITCH_I_ABS : GLITCH_C_ABS
  const rel = key === 'v' ? GLITCH_V_REL : key === 'i' ? GLITCH_I_REL : GLITCH_C_REL
  const floor = key === 'v' ? GLITCH_V_FLOOR : key === 'i' ? GLITCH_I_FLOOR : GLITCH_C_FLOOR
  if (ref == null || !Number.isFinite(ref)) return abs
  return Math.max(floor, Math.min(abs, rel * Math.abs(ref)))
}

function sanitizeRaw(raw: PendingSample): PendingSample {
  let { v, i, c } = raw
  if (c != null && (c < 0 || c > CAPACITY_ABSURD)) c = null
  if (i != null && Math.abs(i) > 20000) i = null
  if (v != null && (v < -1 || v > 80)) v = null
  return { v, i, c }
}

/** True if U, I, or C jumped harder than a plausible 1 Hz process step. */
export function isAbruptSample(
  prev: SeriesPoint,
  v: number | null,
  i: number | null,
  c: number | null,
): boolean {
  return (
    metricAbrupt(prev.v, v, 'v') ||
    metricAbrupt(prev.i, i, 'i') ||
    metricAbrupt(prev.c, c, 'c')
  )
}

function nearMetric(a: number | null | undefined, b: number | null | undefined, key: MetricKey): boolean {
  return !metricAbrupt(a, b, key)
}

/** Near-zero / missing reading for a metric (the needle tip). */
export function isCollapsedValue(value: number | null | undefined, key: MetricKey): boolean {
  if (value == null) return true
  if (key === 'i') return Math.abs(value) < 40
  if (key === 'c') return value < 5
  return value < 0.25
}

/** Previously healthy level that should not snap to the axis. */
export function isStableValue(value: number | null | undefined, key: MetricKey): boolean {
  if (value == null) return false
  if (key === 'i') return Math.abs(value) >= STABLE_I_MA
  if (key === 'c') return value >= 30
  return value >= 1.2
}

/**
 * Stable → ~0/null collapse (U/I/C needles). Never accept into the series while running.
 */
export function isMetricCollapse(
  key: MetricKey,
  prev: number | null | undefined,
  next: number | null | undefined,
): boolean {
  return isStableValue(prev, key) && isCollapsedValue(next, key)
}

export function isCurrentCollapse(prevI: number | null | undefined, nextI: number | null | undefined): boolean {
  return isMetricCollapse('i', prevI, nextI)
}

export function isCapacityCollapse(prevC: number | null | undefined, nextC: number | null | undefined): boolean {
  return isMetricCollapse('c', prevC, nextC)
}

/**
 * Replace collapse/spike runs where both neighbors sit on the same plateau.
 * Never spreads collapsed zeros into good data (left must not be collapsed).
 */
export function scrubPoints(points: SeriesPoint[]): SeriesPoint[] {
  if (points.length < 3) return points
  const out = points.map((p) => ({ ...p }))
  const keys: MetricKey[] = ['v', 'i', 'c']

  for (const key of keys) {
    for (let j = 1; j < out.length - 1; j++) {
      if (nearMetric(out[j - 1][key], out[j + 1][key], key) && metricAbrupt(out[j - 1][key], out[j][key], key)) {
        out[j] = { ...out[j], [key]: out[j - 1][key] }
      }
    }

    let i = 1
    while (i < out.length - 1) {
      if (isCollapsedValue(out[i - 1][key], key)) {
        i += 1
        continue
      }
      if (!metricAbrupt(out[i - 1][key], out[i][key], key)) {
        i += 1
        continue
      }

      const runStart = i
      while (i < out.length && metricAbrupt(out[runStart - 1][key], out[i][key], key)) {
        i += 1
      }
      const runLen = i - runStart
      if (runLen < 1 || runLen > SCRUB_RUN_MAX || i >= out.length) continue

      const left = out[runStart - 1][key]
      const right = out[i][key]
      if (isCollapsedValue(left, key) || !nearMetric(left, right, key)) continue

      // Prefer filling collapses; also patch brief non-collapse spikes between plateaus.
      let fill = true
      const collapseRun = Array.from({ length: runLen }, (_, j) =>
        isCollapsedValue(out[runStart + j][key], key),
      ).every(Boolean)
      if (!collapseRun) {
        // Non-collapse spike: every point must be abrupt vs both neighbors' plateau.
        for (let j = 0; j < runLen; j++) {
          if (!metricAbrupt(left, out[runStart + j][key], key)) {
            fill = false
            break
          }
        }
      }
      if (!fill) continue

      for (let j = 0; j < runLen; j++) {
        const t = (j + 1) / (runLen + 1)
        const interpolated =
          left != null && right != null ? left + (right - left) * t : left
        out[runStart + j] = { ...out[runStart + j], [key]: interpolated }
      }
    }
  }
  return out
}

/** Stable → ~0/null keeps the last healthy level (including trailing needles). */
export function holdCollapses(points: SeriesPoint[]): SeriesPoint[] {
  if (points.length < 2) return points
  const out = points.map((p) => ({ ...p }))
  const keys: MetricKey[] = ['v', 'i', 'c']
  for (let i = 1; i < out.length; i++) {
    for (const key of keys) {
      if (isMetricCollapse(key, out[i - 1][key], out[i][key])) {
        out[i] = { ...out[i], [key]: out[i - 1][key] }
      }
    }
  }
  return out
}

function resolveMetric(
  pending: PendingState,
  key: MetricKey,
  prev: number | null,
  raw: number | null,
): number | null {
  // Collapses (stable → ~0/null) are never written while the channel is running.
  if (isMetricCollapse(key, prev, raw)) {
    pending[key] = { value: raw, confirms: (pending[key]?.confirms ?? 0) + 1 }
    return prev
  }

  const slot = pending[key]
  if (slot) {
    if (isMetricCollapse(key, prev, slot.value)) {
      // Pending collapse: resume only when raw is back near the stable prev.
      if (nearMetric(prev, raw, key)) {
        delete pending[key]
        return raw
      }
      pending[key] = { value: raw, confirms: slot.confirms + 1 }
      return prev
    }

    if (nearMetric(slot.value, raw, key)) {
      const confirms = slot.confirms + 1
      if (confirms >= CONFIRM_DEFAULT) {
        delete pending[key]
        return raw
      }
      pending[key] = { value: raw, confirms }
      return prev
    }
    if (nearMetric(prev, raw, key)) {
      delete pending[key]
      return raw
    }
    pending[key] = { value: raw, confirms: 1 }
    return prev
  }

  if (metricAbrupt(prev, raw, key)) {
    pending[key] = { value: raw, confirms: 1 }
    return prev
  }

  return raw
}

function resolveSampleWith(
  pendingMap: Map<number, PendingState>,
  channel: number,
  prev: PendingSample | SeriesPoint | null,
  incoming: PendingSample,
): PendingSample {
  const raw = sanitizeRaw(incoming)
  if (!prev) {
    pendingMap.delete(channel)
    return raw
  }

  let pending = pendingMap.get(channel)
  if (!pending) {
    pending = {}
    pendingMap.set(channel, pending)
  }

  const sample: PendingSample = {
    v: resolveMetric(pending, 'v', prev.v, raw.v),
    i: resolveMetric(pending, 'i', prev.i, raw.i),
    c: resolveMetric(pending, 'c', prev.c, raw.c),
  }

  if (Object.keys(pending).length === 0) {
    pendingMap.delete(channel)
  }

  return sample
}

/**
 * Hold abrupt metrics until enough matching ticks (filters multi-second needles).
 * Metrics are independent so a current glitch does not freeze voltage/capacity.
 */
function resolveSample(
  channel: number,
  prev: SeriesPoint | null,
  incoming: PendingSample,
): PendingSample {
  return resolveSampleWith(pendingByChannel, channel, prev, incoming)
}

/** Smooth live U/I/C readouts with the same hold/scrub rules as the chart. */
export function smoothLiveMeasurements(
  channels: ChannelParams[],
  measurements: Measurement[],
): Measurement[] {
  const chList = channels.map((c, idx) => ({ ...c, channel: idx }))
  const measList =
    measurements.length === chList.length
      ? measurements.map((m, idx) => ({ ...m, channel: idx }))
      : measurements

  return measList.map((m) => {
    const ch = m.channel
    const c = chList.find((x) => x.channel === ch)
    if (isIdle(c)) {
      readoutHold.delete(ch)
      readoutPending.delete(ch)
      return m
    }
    const incoming = { v: m.voltage_V ?? null, i: m.current_mA ?? null, c: m.capacity_mAh ?? null }
    const prev = readoutHold.get(ch) ?? null
    const sample = resolveSampleWith(readoutPending, ch, prev, incoming)
    readoutHold.set(ch, sample)
    return {
      ...m,
      voltage_V: sample.v,
      current_mA: sample.i,
      capacity_mAh: sample.c,
    }
  })
}

function appendPoint(series: ChannelSeries, now: number, sample: PendingSample): void {
  series.points.push({
    t: (now - series.t0) / 1000,
    v: sample.v,
    i: sample.i,
    c: sample.c,
  })
  // Keep stored history free of sandwich spikes (wider window than before)
  if (series.points.length >= 3) {
    const n = series.points.length
    const window = Math.min(n, SCRUB_RUN_MAX * 2 + 3)
    const scrubbed = holdCollapses(scrubPoints(series.points.slice(-window)))
    series.points = [...series.points.slice(0, Math.max(0, n - window)), ...scrubbed]
  }
}

function syncTimer(): void {
  if (typeof window === 'undefined') return
  const running = anyRunning()
  if (running && intervalId == null) {
    sampleTick()
    intervalId = window.setInterval(sampleTick, 1000)
  } else if (!running && intervalId != null) {
    window.clearInterval(intervalId)
    intervalId = null
  }
}

function sampleTick(): void {
  let changed = false
  const now = Date.now()

  if (channelsSnap.length === 0) {
    return
  }

  for (const chParams of channelsSnap) {
    const ch = chParams.channel
    if (isIdle(chParams)) {
      holdOffChannels.delete(ch)
      continue
    }
    if (holdOffChannels.has(ch)) continue

    const m = measurementsSnap.find((x) => x.channel === ch)
    let series = seriesByChannel.get(ch)
    if (!series) {
      series = { t0: now, points: [] }
      seriesByChannel.set(ch, series)
    }

    const raw = {
      v: m?.voltage_V ?? null,
      i: m?.current_mA ?? null,
      c: m?.capacity_mAh ?? null,
    }
    const prev = series.points.length > 0 ? series.points[series.points.length - 1] : null
    const sample = resolveSample(ch, prev, raw)
    appendPoint(series, now, sample)
    changed = true
  }

  if (changed) notify()

  if (!anyRunning() && intervalId != null) {
    window.clearInterval(intervalId)
    intervalId = null
  }
}

/** Feed latest live channels/measurements; samples once per second while any channel is running. */
export function updateLiveSnapshot(channels: ChannelParams[], measurements: Measurement[]): void {
  if (channels.length === 0) {
    emptySnapStreak += 1
    if (emptySnapStreak < EMPTY_SNAP_STREAK) {
      syncTimer()
      return
    }
  } else {
    emptySnapStreak = 0
  }

  channelsSnap = channels.map((c, idx) => ({ ...c, channel: idx }))
  measurementsSnap =
    measurements.length === channelsSnap.length
      ? measurements.map((m, idx) => ({ ...m, channel: idx }))
      : measurements

  syncTimer()
}
