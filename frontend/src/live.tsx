import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, liveSocket, type ChannelParams, type LivePayload, type Measurement } from './api'
import { replaceFromServer, smoothLiveMeasurements, updateLiveSnapshot } from './liveSeries'
import { createStageStabilizeState, stabilizeChannels } from './stageStabilize'

type LiveCtx = {
  channels: ChannelParams[]
  measurements: Measurement[]
  temperatures: Record<string, number | null>
  connection: LivePayload['connection']
  /** False when the UI cannot reach the dashboard backend (WS/HTTP). */
  backendOnline: boolean
  refresh: () => Promise<void>
}

const Ctx = createContext<LiveCtx | null>(null)

/** No WS message for this long → HTTP fallback + reconnect attempt. */
const WS_STALE_MS = 5000
const WATCHDOG_MS = 2000
/** Declare backend lost after this long without a successful live payload. */
const BACKEND_OFFLINE_AFTER_MS = 8000

export function LiveProvider({ children }: { children: ReactNode }) {
  const [channels, setChannels] = useState<ChannelParams[]>([])
  const [measurements, setMeasurements] = useState<Measurement[]>([])
  const [temperatures, setTemperatures] = useState<Record<string, number | null>>({})
  const [connection, setConnection] = useState<LivePayload['connection']>()
  const [backendOnline, setBackendOnline] = useState(true)
  const channelsRef = useRef(channels)
  const measurementsRef = useRef(measurements)
  const rawMeasurementsRef = useRef<Measurement[]>([])
  const stageStateRef = useRef(createStageStabilizeState())
  const lastGoodAtRef = useRef(Date.now())

  const markBackendGood = () => {
    lastGoodAtRef.current = Date.now()
    setBackendOnline(true)
  }

  const markBackendLostIfStale = () => {
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
    if (Date.now() - lastGoodAtRef.current >= BACKEND_OFFLINE_AFTER_MS) {
      setBackendOnline(false)
    }
  }

  const apply = (data: LivePayload) => {
    markBackendGood()
    if (data.channels) {
      const stable = stabilizeChannels(stageStateRef.current, data.channels)
      channelsRef.current = stable
      setChannels(stable)
    }
    if (data.measurements) {
      rawMeasurementsRef.current = data.measurements
      const smoothed = smoothLiveMeasurements(channelsRef.current, data.measurements)
      measurementsRef.current = smoothed
      setMeasurements(smoothed)
    }
    if (data.temperatures) setTemperatures(data.temperatures)
    if (data.connection) setConnection(data.connection)
    if (data.channels || data.measurements) {
      updateLiveSnapshot(channelsRef.current, rawMeasurementsRef.current)
    }
  }

  const refresh = async () => {
    try {
      const data = await api.live()
      apply(data)
      const c = await api.connection()
      setConnection(c)
      markBackendGood()
    } catch {
      markBackendLostIfStale()
    }
  }

  const hydrateSeries = async () => {
    try {
      const data = await api.liveSeries()
      replaceFromServer(data.channels)
    } catch {
      /* offline or older backend */
    }
  }

  const refreshRef = useRef(refresh)
  refreshRef.current = refresh
  const applyRef = useRef(apply)
  applyRef.current = apply
  const hydrateSeriesRef = useRef(hydrateSeries)
  hydrateSeriesRef.current = hydrateSeries

  useEffect(() => {
    let unmounted = false
    let ws: WebSocket | null = null
    let retry: ReturnType<typeof setTimeout> | undefined
    let watchdog: ReturnType<typeof setInterval> | undefined
    let lastMsgAt = Date.now()

    const drop = () => {
      if (retry) {
        clearTimeout(retry)
        retry = undefined
      }
      if (ws) {
        ws.onclose = null
        ws.onmessage = null
        ws.onerror = null
        ws.onopen = null
        try {
          ws.close()
        } catch {
          /* ignore */
        }
        ws = null
      }
    }

    const connect = () => {
      if (unmounted) return
      drop()
      ws = liveSocket((data) => {
        lastMsgAt = Date.now()
        if (!unmounted) applyRef.current(data)
      })
      ws.onopen = () => {
        void hydrateSeriesRef.current()
      }
      ws.onclose = () => {
        if (unmounted) return
        markBackendLostIfStale()
        retry = setTimeout(connect, 1500)
      }
    }

    const ensureConnected = () => {
      if (unmounted) return
      if (!ws || ws.readyState === WebSocket.CLOSING || ws.readyState === WebSocket.CLOSED) {
        connect()
      }
    }

    const resumeLive = () => {
      ensureConnected()
      void hydrateSeriesRef.current()
      void refreshRef.current()
      updateLiveSnapshot(channelsRef.current, rawMeasurementsRef.current)
    }

    const onPageHide = () => {
      // Close socket but do NOT mark unmounted (bfcache / tab sleep).
      updateLiveSnapshot(channelsRef.current, rawMeasurementsRef.current)
      drop()
    }

    const onPageShow = () => {
      resumeLive()
    }

    const onVisibility = () => {
      if (document.visibilityState === 'visible') resumeLive()
    }

    void hydrateSeriesRef.current()
    void refreshRef.current()
    connect()
    watchdog = window.setInterval(() => {
      if (unmounted) return
      if (Date.now() - lastMsgAt > WS_STALE_MS) {
        void refreshRef.current()
        ensureConnected()
      }
      markBackendLostIfStale()
    }, WATCHDOG_MS)

    window.addEventListener('pagehide', onPageHide)
    window.addEventListener('pageshow', onPageShow)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      unmounted = true
      window.removeEventListener('pagehide', onPageHide)
      window.removeEventListener('pageshow', onPageShow)
      document.removeEventListener('visibilitychange', onVisibility)
      if (watchdog) clearInterval(watchdog)
      drop()
    }
  }, [])

  const value = useMemo(
    () => ({ channels, measurements, temperatures, connection, backendOnline, refresh }),
    [channels, measurements, temperatures, connection, backendOnline],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useLive() {
  const v = useContext(Ctx)
  if (!v) throw new Error('LiveProvider fehlt')
  return v
}
