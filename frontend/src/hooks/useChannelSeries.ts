import { useEffect, useState } from 'react'
import { getSeries, subscribe, type SeriesPoint } from '../liveSeries'

export type { SeriesPoint }

/** Live U/I/C series hydrated from dashboard-process RAM (up to 6 h). */
export function useChannelSeries(channel: number): SeriesPoint[] {
  const [points, setPoints] = useState<SeriesPoint[]>(() => getSeries(channel))

  useEffect(() => {
    setPoints(getSeries(channel))
    return subscribe(() => {
      setPoints(getSeries(channel))
    })
  }, [channel])

  return points
}
