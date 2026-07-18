import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, liveSocket, type ChannelParams, type LivePayload, type Measurement } from './api'

type LiveCtx = {
  channels: ChannelParams[]
  measurements: Measurement[]
  temperatures: Record<string, number | null>
  connection: LivePayload['connection']
  refresh: () => Promise<void>
}

const Ctx = createContext<LiveCtx | null>(null)

export function LiveProvider({ children }: { children: ReactNode }) {
  const [channels, setChannels] = useState<ChannelParams[]>([])
  const [measurements, setMeasurements] = useState<Measurement[]>([])
  const [temperatures, setTemperatures] = useState<Record<string, number | null>>({})
  const [connection, setConnection] = useState<LivePayload['connection']>()

  const apply = (data: LivePayload) => {
    if (data.channels) setChannels(data.channels)
    if (data.measurements) setMeasurements(data.measurements)
    if (data.temperatures) setTemperatures(data.temperatures)
    if (data.connection) setConnection(data.connection)
  }

  const refresh = async () => {
    try {
      const data = await api.live()
      apply(data)
      const c = await api.connection()
      setConnection(c)
    } catch {
      /* offline */
    }
  }

  useEffect(() => {
    let closed = false
    let ws: WebSocket | null = null
    let retry: ReturnType<typeof setTimeout> | undefined

    const drop = () => {
      if (retry) {
        clearTimeout(retry)
        retry = undefined
      }
      if (ws) {
        ws.onclose = null
        ws.onmessage = null
        ws.onerror = null
        try {
          ws.close()
        } catch {
          /* ignore */
        }
        ws = null
      }
    }

    const connect = () => {
      if (closed) return
      drop()
      ws = liveSocket((data) => {
        if (!closed) apply(data)
      })
      ws.onclose = () => {
        if (closed) return
        retry = setTimeout(connect, 1500)
      }
    }

    const onPageHide = () => {
      closed = true
      drop()
    }

    refresh()
    connect()
    window.addEventListener('pagehide', onPageHide)
    return () => {
      closed = true
      window.removeEventListener('pagehide', onPageHide)
      drop()
    }
  }, [])

  const value = useMemo(
    () => ({ channels, measurements, temperatures, connection, refresh }),
    [channels, measurements, temperatures, connection],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useLive() {
  const v = useContext(Ctx)
  if (!v) throw new Error('LiveProvider fehlt')
  return v
}
