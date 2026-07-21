import type { ChannelParams, Measurement } from './api'

export type SeriesPoint = { t: number; v: number | null; i: number | null; c: number | null }

type ChannelSeries = {
  t0: number
  points: SeriesPoint[]
}

/** Bumped when filter semantics change so old glitchy series are discarded. */
const SESSION_KEY = 'alc-live-series-v3'
/** ~3 h at 1 Hz — beyond this the chart uses a sliding X window. */
const MAX_POINTS = 10800

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
type PendingState = { sample: PendingSample; confirms: number }
const pendingByChannel = new Map<number, PendingState>()

const GLITCH_V_ABS = 0.2 // V in one second
const GLITCH_I_ABS = 80 // mA in one second
const GLITCH_C_ABS = 25 // mAh in one second
/** Need this many matching abrupt samples before accepting a step (kills 1–2 tick needles). */
const CONFIRM_NEEDED = 2
/** Absolute capacity above this is treated as wire garbage. */
const CAPACITY_ABSURD = 15000

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
    sessionStorage.removeItem('alc-live-series-v1')
    sessionStorage.removeItem('alc-live-series-v2')
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return
    const payload = JSON.parse(raw) as SessionPayload
    if (!payload?.channels || typeof payload.channels !== 'object') return
    for (const [key, value] of Object.entries(payload.channels)) {
      const ch = Number(key)
      if (!Number.isFinite(ch) || !value?.points || !Array.isArray(value.points)) continue
      const points = scrubPoints(
        value.points.filter((p) => p && typeof p.t === 'number').slice(-MAX_POINTS),
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
  return pts ? [...pts] : []
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

function nearSample(a: PendingSample, b: PendingSample): boolean {
  return !isAbruptSample({ t: 0, v: a.v, i: a.i, c: a.c }, b.v, b.i, b.c)
}

/**
 * Replace isolated spikes where a point differs from both neighbors (post-hoc scrub).
 */
export function scrubPoints(points: SeriesPoint[]): SeriesPoint[] {
  if (points.length < 3) return points
  const out = points.map((p) => ({ ...p }))
  for (let i = 1; i < out.length - 1; i++) {
    const prev = out[i - 1]
    const cur = out[i]
    const next = out[i + 1]
    if (nearSample(prev, next) && isAbruptSample(prev, cur.v, cur.i, cur.c)) {
      out[i] = { t: cur.t, v: prev.v, i: prev.i, c: prev.c }
    }
  }
  return out
}

/**
 * Hold abrupt samples until CONFIRM_NEEDED matching ticks (filters 1–2s needles on all channels).
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

  const pending = pendingByChannel.get(channel)
  if (pending) {
    if (nearSample(pending.sample, raw)) {
      const confirms = pending.confirms + 1
      if (confirms >= CONFIRM_NEEDED) {
        pendingByChannel.delete(channel)
        return raw
      }
      pendingByChannel.set(channel, { sample: raw, confirms })
      return { v: prev.v, i: prev.i, c: prev.c }
    }
    if (nearSample(prev, raw)) {
      // Pending was a short glitch; resume stable path
      pendingByChannel.delete(channel)
      return raw
    }
    // New distinct jump: restart pending from raw, keep holding previous stable
    pendingByChannel.set(channel, { sample: raw, confirms: 1 })
    return { v: prev.v, i: prev.i, c: prev.c }
  }

  if (isAbruptSample(prev, raw.v, raw.i, raw.c)) {
    pendingByChannel.set(channel, { sample: raw, confirms: 1 })
    return { v: prev.v, i: prev.i, c: prev.c }
  }

  return raw
}

function appendPoint(series: ChannelSeries, now: number, sample: PendingSample): void {
  series.points = [
    ...series.points,
    {
      t: (now - series.t0) / 1000,
      v: sample.v,
      i: sample.i,
      c: sample.c,
    },
  ].slice(-MAX_POINTS)
  // Keep stored history free of sandwich spikes
  if (series.points.length >= 3) {
    const n = series.points.length
    const scrubbed = scrubPoints(series.points.slice(-5))
    series.points = [...series.points.slice(0, Math.max(0, n - 5)), ...scrubbed].slice(-MAX_POINTS)
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
