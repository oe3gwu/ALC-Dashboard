import type { ChannelParams, Measurement } from './api'

export type SeriesPoint = { t: number; v: number | null; i: number | null; c: number | null }

type ChannelSeries = {
  t0: number
  points: SeriesPoint[]
}

const SESSION_KEY = 'alc-live-series-v1'
/** ~1 h at 1 Hz — beyond this the chart uses a sliding X window. */
const MAX_POINTS = 3600

type SessionPayload = {
  channels: Record<string, ChannelSeries>
}

const seriesByChannel = new Map<number, ChannelSeries>()
const listeners = new Set<() => void>()

let channelsSnap: ChannelParams[] = []
let measurementsSnap: Measurement[] = []
let intervalId: number | null = null
let hydrated = false
/** Last known idle flag per channel — used to reset series on idle→running. */
const prevIdleByChannel = new Map<number, boolean>()
/** Consecutive idle observations before clearing a running series (guards against glitches). */
const idleStreakByChannel = new Map<number, number>()
const IDLE_CLEAR_STREAK = 2

function isIdle(c: ChannelParams | undefined): boolean {
  if (!c) return true
  return Boolean(c.idle) || c.stage_name === 'Leerlauf'
}

function notify(): void {
  for (const listener of listeners) listener()
}

function persistToSession(): void {
  if (typeof sessionStorage === 'undefined') return
  try {
    const channels: Record<string, ChannelSeries> = {}
    for (const [ch, series] of seriesByChannel) {
      if (series.points.length === 0) continue
      channels[String(ch)] = series
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
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return
    const payload = JSON.parse(raw) as SessionPayload
    if (!payload?.channels || typeof payload.channels !== 'object') return
    for (const [key, value] of Object.entries(payload.channels)) {
      const ch = Number(key)
      if (!Number.isFinite(ch) || !value?.points || !Array.isArray(value.points)) continue
      const points = value.points
        .filter((p) => p && typeof p.t === 'number')
        .slice(-MAX_POINTS)
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
  if (seriesByChannel.size === 0) return
  seriesByChannel.clear()
  persistToSession()
  notify()
}

export function getSeries(channel: number): SeriesPoint[] {
  return seriesByChannel.get(channel)?.points ?? []
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

/** One-sample wire glitch: voltage collapses while current spikes (or vice versa). */
function isGlitchSample(
  prev: SeriesPoint,
  v: number | null,
  i: number | null,
): boolean {
  const pv = prev.v
  const pi = prev.i
  if (pv == null || v == null) return false
  // U was healthy (>2 V) and collapses to near 0 in one tick
  const voltageCollapse = pv > 2 && v < 0.5
  if (!voltageCollapse) return false
  // …while I jumps from near-zero / missing to a large charge-like value
  const prevI = pi ?? 0
  const curI = i ?? 0
  if (Math.abs(prevI) < 100 && Math.abs(curI) > 500) return true
  // …or U collapses alone with no plausible gradual change
  if (Math.abs(pv - v) > 5) return true
  return false
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

  for (const chParams of channelsSnap) {
    const ch = chParams.channel
    if (isIdle(chParams)) {
      if (seriesByChannel.has(ch)) {
        seriesByChannel.delete(ch)
        changed = true
      }
      continue
    }

    const m = measurementsSnap.find((x) => x.channel === ch)
    let series = seriesByChannel.get(ch)
    if (!series) {
      series = { t0: now, points: [] }
      seriesByChannel.set(ch, series)
    }

    let v = m?.voltage_V ?? null
    let i = m?.current_mA ?? null
    let c = m?.capacity_mAh ?? null

    // Drop single-sample glitches (e.g. U→0 + I spike during Pause/Warten) that
    // flash too briefly for the numeric readout but stay visible on the chart.
    const prev = series.points.length > 0 ? series.points[series.points.length - 1] : null
    if (prev && isGlitchSample(prev, v, i)) {
      v = prev.v
      i = prev.i
      c = prev.c
    }

    series.points = [
      ...series.points,
      {
        t: (now - series.t0) / 1000,
        v,
        i,
        c,
      },
    ].slice(-MAX_POINTS)
    changed = true
  }

  // Drop series for channels no longer present in snapshot (e.g. fewer channels)
  const known = new Set(channelsSnap.map((c) => c.channel))
  for (const ch of [...seriesByChannel.keys()]) {
    if (!known.has(ch)) {
      seriesByChannel.delete(ch)
      changed = true
    }
  }

  if (changed) {
    persistToSession()
    notify()
  }

  if (!anyRunning() && intervalId != null) {
    window.clearInterval(intervalId)
    intervalId = null
  }
}

/** Feed latest live channels/measurements; samples once per second while any channel is running. */
export function updateLiveSnapshot(channels: ChannelParams[], measurements: Measurement[]): void {
  // Trust list order as channel index — device wire may echo a wrong channel byte.
  channelsSnap = channels.map((c, idx) => ({ ...c, channel: idx }))
  measurementsSnap =
    measurements.length === channelsSnap.length
      ? measurements.map((m, idx) => ({ ...m, channel: idx }))
      : measurements

  let cleared = false
  for (const c of channelsSnap) {
    const ch = c.channel
    const idle = isIdle(c)
    const wasIdle = prevIdleByChannel.has(ch) ? prevIdleByChannel.get(ch)! : idle

    if (idle) {
      const streak = (idleStreakByChannel.get(ch) ?? 0) + 1
      idleStreakByChannel.set(ch, streak)
      if (streak >= IDLE_CLEAR_STREAK && seriesByChannel.has(ch)) {
        seriesByChannel.delete(ch)
        cleared = true
      }
    } else {
      idleStreakByChannel.set(ch, 0)
      // New process: idle → running. Skip first sighting so F5 hydrate stays.
      if (prevIdleByChannel.has(ch) && wasIdle && seriesByChannel.has(ch)) {
        seriesByChannel.delete(ch)
        cleared = true
      }
    }
    prevIdleByChannel.set(ch, idle)
  }
  if (cleared) {
    persistToSession()
    notify()
  }

  syncTimer()
}
