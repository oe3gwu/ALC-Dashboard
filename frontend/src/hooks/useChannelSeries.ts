import { useEffect, useRef, useState } from 'react'
import type { Measurement } from '../api'
import { useLive } from '../live'

export type SeriesPoint = { t: number; v: number | null; i: number | null; c: number | null }

/** Sample live U/I/C for one channel once per second. */
export function useChannelSeries(channel: number): SeriesPoint[] {
  const { measurements } = useLive()
  const m = measurements.find((x) => x.channel === channel)
  const [points, setPoints] = useState<SeriesPoint[]>([])
  const t0 = useRef(Date.now())
  const latest = useRef<Measurement | undefined>(m)
  latest.current = m

  useEffect(() => {
    t0.current = Date.now()
    setPoints([])
  }, [channel])

  useEffect(() => {
    const tick = () => {
      const cur = latest.current
      setPoints((prev) => {
        const next = [
          ...prev,
          {
            t: (Date.now() - t0.current) / 1000,
            v: cur?.voltage_V ?? null,
            i: cur?.current_mA ?? null,
            c: cur?.capacity_mAh ?? null,
          },
        ]
        return next.slice(-240)
      })
    }
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [channel])

  return points
}
