import type { ChannelParams, Measurement } from './api'

export type SeriesPoint = { t: number; v: number | null; i: number | null; c: number | null }

type ChannelSeries = {
  t0: number
  points: SeriesPoint[]
}

const SESSION_KEY = 'alc-live-series-v1'
const MAX_POINTS = 240

type SessionPayload = {
  channels: Record<string, ChannelSeries>
}

const seriesByChannel = new Map<number, ChannelSeries>()
const listeners = new Set<() => void>()

let channelsSnap: ChannelParams[] = []
let measurementsSnap: Measurement[] = []
let intervalId: number | null = null
let hydrated = false

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

    series.points = [
      ...series.points,
      {
        t: (now - series.t0) / 1000,
        v: m?.voltage_V ?? null,
        i: m?.current_mA ?? null,
        c: m?.capacity_mAh ?? null,
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
  channelsSnap = channels
  measurementsSnap = measurements

  // Clear idle channels immediately (stop / finished)
  let cleared = false
  for (const c of channels) {
    if (isIdle(c) && seriesByChannel.has(c.channel)) {
      seriesByChannel.delete(c.channel)
      cleared = true
    }
  }
  if (cleared) {
    persistToSession()
    notify()
  }

  syncTimer()
}
