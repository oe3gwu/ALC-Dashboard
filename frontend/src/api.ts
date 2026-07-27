export type ChannelParams = {
  channel: number
  battery_slot: number
  battery_type: number
  battery_type_name: string
  cells: number
  discharge_mA: number
  charge_mA: number
  capacity_mAh: number
  program: number
  program_name: string
  forming_mA: number
  pause_s: number
  flags: number
  full_factor: number
  logger_samples: number
  stage: number
  stage_name: string
  activator: boolean
  idle: boolean
}

export type Measurement = {
  channel: number
  voltage_V: number | null
  current_mA: number | null
  capacity_mAh: number | null
}

export type ConnectionStatus = {
  connected: boolean
  port: string | null
  simulator?: boolean
  mock?: boolean
  device_model?: string
  device_label?: string
  status_label?: string | null
  channel_count?: number
  last_error?: string | null
  /** Real serial TX pulses (monotone); only when hardware connected */
  tx_seq?: number
  /** Real serial RX pulses (monotone); only when hardware connected */
  rx_seq?: number
}

export type LivePayload = {
  type?: string
  channels: ChannelParams[]
  measurements: Measurement[]
  temperatures: Record<string, number | null>
  connection?: ConnectionStatus
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = await res.json()
      detail = j.detail || JSON.stringify(j)
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  if (res.status === 204) return undefined as T
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return res as unknown as T
}

type NdjsonMsg = Record<string, unknown> & { type: string; message?: string }

async function readNdjsonStream(url: string, init?: RequestInit, onProgress?: (msg: NdjsonMsg) => void): Promise<NdjsonMsg> {
  const res = await fetch(url, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = await res.json()
      detail = j.detail || JSON.stringify(j)
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  if (!res.body) throw new Error('Kein Stream-Body')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: NdjsonMsg | null = null
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      const msg = JSON.parse(trimmed) as NdjsonMsg
      if (msg.type === 'progress') {
        onProgress?.(msg)
      } else if (msg.type === 'done') {
        result = msg
      } else if (msg.type === 'error') {
        throw new Error(String(msg.message || 'Stream fehlgeschlagen'))
      }
    }
  }
  if (!result) throw new Error('Stream ohne Ergebnis')
  return result
}

export const api = {
  meta: () =>
    req<{
      name: string
      device_model?: string
      devices?: unknown[]
      battery_types: Record<string, string>
      programs: Record<string, string>
      capabilities?: Record<string, unknown>
      features: Record<string, unknown>
      config: Record<string, unknown>
    }>('/api/meta'),
  ports: () =>
    req<{
      ports: {
        device: string
        description: string
        vid: string | null
        pid: string | null
        kind?: string
        target?: string | null
        group?: string | null
      }[]
      dialout?: {
        user: string
        group_exists: boolean
        in_group: boolean
        group_members: string[]
      }
    }>('/api/ports'),
  connection: () => req<ConnectionStatus>('/api/connection'),
  connect: (body: { port?: string | null; simulator?: boolean | null; mock?: boolean | null }) =>
    req('/api/connection/connect', { method: 'POST', body: JSON.stringify(body) }),
  disconnect: () => req('/api/connection/disconnect', { method: 'POST' }),
  live: () => req<LivePayload>('/api/live'),
  getChannel: (ch: number) => req<ChannelParams>(`/api/channels/${ch}`),
  setChannel: (ch: number, body: Record<string, unknown>) =>
    req<{ params: ChannelParams; corrections: Record<string, { requested: unknown; device: unknown }> }>(`/api/channels/${ch}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  activity: (ch: number, stop: boolean) =>
    req(`/api/channels/${ch}/activity`, { method: 'POST', body: JSON.stringify({ channel: ch, stop }) }),
  preview: (params: Record<string, unknown>) =>
    req<{ requested: ChannelParams; device: ChannelParams; corrections: Record<string, { requested: unknown; device: unknown }> }>('/api/process/preview', {
      method: 'POST',
      body: JSON.stringify({ params, confirm: false }),
    }),
  start: (params: Record<string, unknown>) =>
    req('/api/process/start', { method: 'POST', body: JSON.stringify({ params, confirm: true }) }),
  batteryDb: () => req<{ entries: Record<string, unknown>[]; source?: string }>('/api/battery-db'),
  putBattery: (slot: number, body: Record<string, unknown>) =>
    req(`/api/battery-db/${slot}`, { method: 'PUT', body: JSON.stringify(body) }),
  resetBattery: (slot: number) => req<Record<string, unknown>>(`/api/battery-db/${slot}`, { method: 'DELETE' }),
  importBatteryDbFromDevice: () =>
    req<{ entries: Record<string, unknown>[]; imported: number; total: number; errors: { slot: number; error: string }[] }>(
      '/api/battery-db/import-from-device',
      { method: 'POST' },
    ),
  importBatteryDbFromDeviceStream: async (
    onProgress?: (p: { done: number; total: number; slot: number; pct: number }) => void,
  ) => {
    const msg = await readNdjsonStream('/api/battery-db/import-from-device/stream', { method: 'POST' }, (p) => {
      onProgress?.({
        done: Number(p.done ?? 0),
        total: Number(p.total ?? 0),
        slot: Number(p.slot ?? 0),
        pct: Number(p.pct ?? 0),
      })
    })
    return {
      entries: (msg.entries as Record<string, unknown>[]) || [],
      imported: Number(msg.imported ?? 0),
      total: Number(msg.total ?? 0),
      errors: (msg.errors as { slot: number; error: string }[]) || [],
    }
  },
  exportBatteryDbToDevice: () =>
    req<{ written: number; total: number; errors: { slot: number; error: string }[] }>('/api/battery-db/export-to-device', {
      method: 'POST',
    }),
  exportBatteryDbToDeviceStream: async (
    onProgress?: (p: { done: number; total: number; slot: number; pct: number }) => void,
  ) => {
    const msg = await readNdjsonStream('/api/battery-db/export-to-device/stream', { method: 'POST' }, (p) => {
      onProgress?.({
        done: Number(p.done ?? 0),
        total: Number(p.total ?? 0),
        slot: Number(p.slot ?? 0),
        pct: Number(p.pct ?? 0),
      })
    })
    return {
      written: Number(msg.written ?? 0),
      total: Number(msg.total ?? 0),
      errors: (msg.errors as { slot: number; error: string }[]) || [],
    }
  },
  downloadBatteryDbFile: async () => {
    const res = await fetch('/api/battery-db/file')
    if (!res.ok) throw new Error('Download fehlgeschlagen')
    return res.blob()
  },
  uploadBatteryDbFile: async (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch('/api/battery-db/file', { method: 'POST', body: fd })
    if (!res.ok) {
      let detail = res.statusText
      try {
        const j = await res.json()
        detail = j.detail || JSON.stringify(j)
      } catch {
        /* ignore */
      }
      throw new Error(detail)
    }
    return res.json() as Promise<{ entries: Record<string, unknown>[] }>
  },
  deviceParams: () => req<{ g: Record<string, number>; h: Record<string, number>; j: Record<string, number | boolean> }>('/api/device/params'),
  putG: (body: Record<string, number>) => req('/api/device/params/g', { method: 'PUT', body: JSON.stringify(body) }),
  putH: (body: Record<string, number>) => req('/api/device/params/h', { method: 'PUT', body: JSON.stringify(body) }),
  putJ: (body: Record<string, unknown>) => req('/api/device/params/j', { method: 'PUT', body: JSON.stringify(body) }),
  restoreDefaults: () => req('/api/device/params/restore', { method: 'POST' }),
  deviceInfo: () => req<Record<string, unknown>>('/api/device/info'),
  readLogger: (ch: number) => req<{ logger: Record<string, unknown>; archive?: Record<string, unknown> }>(`/api/logger/${ch}?save=true`),
  readLoggerStream: async (
    ch: number,
    onProgress?: (p: { block: number; total: number; samples: number; expected: number; pct: number }) => void,
  ) => {
    const msg = await readNdjsonStream(`/api/logger/${ch}/stream?save=true`, undefined, (p) => {
      onProgress?.({
        block: Number(p.block ?? 0),
        total: Number(p.total ?? 0),
        samples: Number(p.samples ?? 0),
        expected: Number(p.expected ?? 0),
        pct: Number(p.pct ?? 0),
      })
    })
    if (!msg.logger) throw new Error('Logger-Stream ohne Ergebnis')
    return {
      logger: msg.logger as Record<string, unknown>,
      archive: msg.archive as Record<string, unknown> | undefined,
    }
  },
  clearLogger: (ch: number) => req(`/api/logger/${ch}`, { method: 'DELETE' }),
  archive: () => req<{ sessions: Record<string, unknown>[] }>('/api/archive'),
  archiveSession: (id: string) => req<Record<string, unknown>>(`/api/archive/${id}`),
  deleteArchive: (id: string) => req<{ ok: boolean; id: string }>(`/api/archive/${id}`, { method: 'DELETE' }),
  deleteAllArchive: () => req<{ ok: boolean; deleted: number }>('/api/archive', { method: 'DELETE' }),
  firmwareGuide: () =>
    req<{
      safety: string
      steps: string[]
      notes: string[]
      filename_hint: string
      tool_hint: string
      device_model?: string
      device_label?: string
      supported?: boolean
    }>('/api/firmware/guide'),
  updateConfig: (body: Record<string, unknown>) => req('/api/config', { method: 'PUT', body: JSON.stringify(body) }),
}

export function liveSocket(onMessage: (data: LivePayload) => void) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/ws/live`)
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data))
    } catch {
      /* ignore */
    }
  }
  return ws
}
