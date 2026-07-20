import { useEffect, useState } from 'react'
import { getSeries, subscribe, type SeriesPoint } from '../liveSeries'

export type { SeriesPoint }

/** Live U/I/C series for one channel from the shared RAM store (survives SPA nav + F5 while running). */
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
