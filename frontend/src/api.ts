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
  ports: () => req<{ ports: { device: string; description: string; vid: string | null; pid: string | null }[] }>('/api/ports'),
  connection: () => req<ConnectionStatus>('/api/connection'),
  connect: (body: { port?: string | null; simulator?: boolean | null; mock?: boolean | null }) =>
    req('/api/connection/connect', { method: 'POST', body: JSON.stringify(body) }),
  disconnect: () => req('/api/connection/disconnect', { method: 'POST' }),
  live: () => req<LivePayload>('/api/live'),
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
  importBatteryDbFromDevice: () =>
    req<{ entries: Record<string, unknown>[]; imported: number; total: number; errors: { slot: number; error: string }[] }>(
      '/api/battery-db/import-from-device',
      { method: 'POST' },
    ),
  exportBatteryDbToDevice: () =>
    req<{ written: number; total: number; errors: { slot: number; error: string }[] }>('/api/battery-db/export-to-device', {
      method: 'POST',
    }),
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
