import type { ChannelParams, Measurement } from './api'

export type SeriesPoint = { t: number; v: number | null; i: number | null; c: number | null }

type ChannelSeries = {
  t0: number
  points: SeriesPoint[]
}

/** Bumped when filter semantics change so old glitchy series are discarded. */
const SESSION_KEY = 'alc-live-series-v6'

type SessionPayload = {
  channels: Record<string, ChannelSeries>
}

const seriesByChannel = new Map<number, ChannelSeries>()
const listeners = new Set<() => void>()

let channelsSnap: ChannelParams[] = []
let measurementsSnap: Measurement[] = []
let intervalId: number | null = null
let hydrated = false
/** Consecutive idle observations before clearing a running series (guards against glitches). */
const idleStreakByChannel = new Map<number, number>()
const IDLE_CLEAR_STREAK = 2
/** Empty live payloads (disconnect race) before accepting wipe. */
let emptySnapStreak = 0
const EMPTY_SNAP_STREAK = 3

type PendingSample = { v: number | null; i: number | null; c: number | null }
type MetricKey = 'v' | 'i' | 'c'
type MetricPending = { value: number | null; confirms: number }
type PendingState = Partial<Record<MetricKey, MetricPending>>
const pendingByChannel = new Map<number, PendingState>()

const GLITCH_V_ABS = 0.15 // V in one second
const GLITCH_I_ABS = 60 // mA in one second
const GLITCH_C_ABS = 20 // mAh in one second
/** Confirms before accepting a non-collapse abrupt step (ramps, stage changes). */
const CONFIRM_DEFAULT = 3
/** Absolute capacity above this is treated as wire garbage. */
const CAPACITY_ABSURD = 15000
/** Scrub collapse/spike runs up to this many seconds between two stable neighbors. */
const SCRUB_RUN_MAX = 20

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

function persistToSession(): void {
  if (typeof sessionStorage === 'undefined') return
  try {
    const channels: Record<string, ChannelSeries> = {}
    for (const [ch, series] of seriesByChannel) {
      if (series.points.length === 0) continue
      channels[String(ch)] = { t0: series.t0, points: scrubPoints(series.points) }
    }
    if (Object.keys(channels).length === 0) {
      sessionStorage.removeItem(SESSION_KEY)
      return
    }
    const payload: SessionPayload = { channels }
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(payload))
  } catch {
    /* quota / private mode */
  }
}

function hydrateFromSession(): void {
  if (hydrated || typeof sessionStorage === 'undefined') return
  hydrated = true
  try {
    // Drop legacy keys that still contain needle spikes
    for (const legacy of [
      'alc-live-series-v1',
      'alc-live-series-v2',
      'alc-live-series-v3',
      'alc-live-series-v4',
      'alc-live-series-v5',
    ]) {
      sessionStorage.removeItem(legacy)
    }
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return
    const payload = JSON.parse(raw) as SessionPayload
    if (!payload?.channels || typeof payload.channels !== 'object') return
    for (const [key, value] of Object.entries(payload.channels)) {
      const ch = Number(key)
      if (!Number.isFinite(ch) || !value?.points || !Array.isArray(value.points)) continue
      const points = scrubPoints(
        value.points.filter((p) => p && typeof p.t === 'number'),
      )
      if (points.length === 0) continue
      seriesByChannel.set(ch, {
        t0: typeof value.t0 === 'number' ? value.t0 : Date.now(),
        points,
      })
    }
  } catch {
    /* ignore corrupt session */
  }
}

hydrateFromSession()

function clearChannel(channel: number, silent = false): void {
  pendingByChannel.delete(channel)
  if (!seriesByChannel.has(channel)) return
  seriesByChannel.delete(channel)
  if (!silent) {
    persistToSession()
    notify()
  }
}

export function clearSeries(channel: number): void {
  clearChannel(channel)
}

export function clearAllSeries(): void {
  pendingByChannel.clear()
  if (seriesByChannel.size === 0) return
  seriesByChannel.clear()
  persistToSession()
  notify()
}

export function getSeries(channel: number): SeriesPoint[] {
  const pts = seriesByChannel.get(channel)?.points
  return pts ? scrubPoints(pts) : []
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
  absThresh: number,
): boolean {
  if (prev == null || next == null) {
    return (prev == null) !== (next == null)
  }
  return Math.abs(prev - next) >= absThresh
}

function threshFor(key: MetricKey): number {
  if (key === 'v') return GLITCH_V_ABS
  if (key === 'i') return GLITCH_I_ABS
  return GLITCH_C_ABS
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
    metricAbrupt(prev.v, v, GLITCH_V_ABS) ||
    metricAbrupt(prev.i, i, GLITCH_I_ABS) ||
    metricAbrupt(prev.c, c, GLITCH_C_ABS)
  )
}

function nearMetric(a: number | null | undefined, b: number | null | undefined, key: MetricKey): boolean {
  return !metricAbrupt(a, b, threshFor(key))
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
  if (key === 'i') return Math.abs(value) >= 120
  if (key === 'c') return value >= 30
  return value >= 1.2
}

/**
 * Stable → ~0/null collapse (U/I/C needles). Never accept into the series while running;
 * idle clear removes the chart when the process actually ends.
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
 * Replace collapse/spike runs where both neighbors are a stable plateau.
 * Never spreads collapsed zeros into good data (left must be stable).
 */
export function scrubPoints(points: SeriesPoint[]): SeriesPoint[] {
  if (points.length < 3) return points
  const out = points.map((p) => ({ ...p }))
  const keys: MetricKey[] = ['v', 'i', 'c']

  for (const key of keys) {
    let i = 1
    while (i < out.length - 1) {
      if (!isStableValue(out[i - 1][key], key)) {
        i += 1
        continue
      }
      if (!metricAbrupt(out[i - 1][key], out[i][key], threshFor(key))) {
        i += 1
        continue
      }

      const runStart = i
      while (i < out.length && metricAbrupt(out[runStart - 1][key], out[i][key], threshFor(key))) {
        i += 1
      }
      const runLen = i - runStart
      if (runLen < 1 || runLen > SCRUB_RUN_MAX || i >= out.length) continue

      const left = out[runStart - 1][key]
      const right = out[i][key]
      if (!isStableValue(left, key) || !nearMetric(left, right, key)) continue

      // Prefer filling collapses; also patch brief non-collapse spikes between plateaus.
      let fill = true
      const collapseRun = Array.from({ length: runLen }, (_, j) =>
        isCollapsedValue(out[runStart + j][key], key),
      ).every(Boolean)
      if (!collapseRun) {
        // Non-collapse spike: every point must be abrupt vs both neighbors' plateau.
        for (let j = 0; j < runLen; j++) {
          if (!metricAbrupt(left, out[runStart + j][key], threshFor(key))) {
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

  if (metricAbrupt(prev, raw, threshFor(key))) {
    pending[key] = { value: raw, confirms: 1 }
    return prev
  }

  return raw
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
  const raw = sanitizeRaw(incoming)
  if (!prev) {
    pendingByChannel.delete(channel)
    return raw
  }

  let pending = pendingByChannel.get(channel)
  if (!pending) {
    pending = {}
    pendingByChannel.set(channel, pending)
  }

  const sample: PendingSample = {
    v: resolveMetric(pending, 'v', prev.v, raw.v),
    i: resolveMetric(pending, 'i', prev.i, raw.i),
    c: resolveMetric(pending, 'c', prev.c, raw.c),
  }

  if (Object.keys(pending).length === 0) {
    pendingByChannel.delete(channel)
  }

  return sample
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
    const scrubbed = scrubPoints(series.points.slice(-window))
    series.points = [...series.points.slice(0, Math.max(0, n - window)), ...scrubbed]
  }
}

function syncTimer(): void {
  if (typeof window === 'undefined') return
  const running = anyRunning() || seriesByChannel.size > 0
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
    for (const [ch, series] of seriesByChannel) {
      const m = measurementsSnap.find((x) => x.channel === ch)
      const prev = series.points.at(-1) ?? null
      const raw = {
        v: m?.voltage_V ?? prev?.v ?? null,
        i: m?.current_mA ?? prev?.i ?? null,
        c: m?.capacity_mAh ?? prev?.c ?? null,
      }
      const sample = resolveSample(ch, prev, raw)
      appendPoint(series, now, sample)
      changed = true
    }
    if (changed) {
      persistToSession()
      notify()
    }
    return
  }

  for (const chParams of channelsSnap) {
    const ch = chParams.channel
    if (isIdle(chParams)) continue

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

  const known = new Set(channelsSnap.map((c) => c.channel))
  for (const ch of [...seriesByChannel.keys()]) {
    if (!known.has(ch)) {
      pendingByChannel.delete(ch)
      seriesByChannel.delete(ch)
      changed = true
    }
  }

  if (changed) {
    persistToSession()
    notify()
  }

  if (!anyRunning() && seriesByChannel.size === 0 && intervalId != null) {
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

  let cleared = false
  for (const c of channelsSnap) {
    const ch = c.channel
    const idle = isIdle(c)

    if (idle) {
      const streak = (idleStreakByChannel.get(ch) ?? 0) + 1
      idleStreakByChannel.set(ch, streak)
      if (streak >= IDLE_CLEAR_STREAK && seriesByChannel.has(ch)) {
        pendingByChannel.delete(ch)
        seriesByChannel.delete(ch)
        cleared = true
      }
    } else {
      idleStreakByChannel.set(ch, 0)
    }
  }
  if (cleared) {
    persistToSession()
    notify()
  }

  syncTimer()
}
