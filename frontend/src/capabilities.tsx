import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from './api'

export type DeviceInfo = {
  id: string
  label: string
  enabled: boolean
  channel_count: number
  protocol: string
  simulator_label: string
  disabled_reason: string
  features: Record<string, unknown>
  battery_type_ids: number[]
  program_ids: number[]
}

export type Capabilities = {
  channel_count: number
  battery_type_ids: number[]
  program_ids: number[]
  logger: boolean
  battery_db: boolean
  chemistry_params: boolean
  chemistry_hj: boolean
  full_factor: boolean
  activator: boolean
  activator_channel: number | null
  ri_usb: boolean
  firmware_guided: boolean
  protocol: string
  simulator_label: string
}

type CapsState = {
  ready: boolean
  deviceModel: string
  devices: DeviceInfo[]
  capabilities: Capabilities
  batteryTypes: Record<string, string>
  programs: Record<string, string>
  refresh: () => Promise<void>
}

const defaultCaps: Capabilities = {
  channel_count: 4,
  battery_type_ids: [],
  program_ids: [],
  logger: true,
  battery_db: true,
  chemistry_params: true,
  chemistry_hj: true,
  full_factor: true,
  activator: true,
  activator_channel: 1,
  ri_usb: false,
  firmware_guided: true,
  protocol: 'alc8500_usb',
  simulator_label: 'Simulator',
}

const CapsCtx = createContext<CapsState>({
  ready: false,
  deviceModel: 'alc8500_2_expert',
  devices: [],
  capabilities: defaultCaps,
  batteryTypes: {},
  programs: {},
  refresh: async () => {},
})

export function CapabilitiesProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const [deviceModel, setDeviceModel] = useState('alc8500_2_expert')
  const [devices, setDevices] = useState<DeviceInfo[]>([])
  const [capabilities, setCapabilities] = useState<Capabilities>(defaultCaps)
  const [batteryTypes, setBatteryTypes] = useState<Record<string, string>>({})
  const [programs, setPrograms] = useState<Record<string, string>>({})

  const refresh = async () => {
    const m = await api.meta()
    setDeviceModel(String(m.device_model || 'alc8500_2_expert'))
    setDevices((m.devices as DeviceInfo[]) || [])
    const c = (m.capabilities || {}) as Partial<Capabilities>
    setCapabilities({ ...defaultCaps, ...c })
    setBatteryTypes((m.battery_types as Record<string, string>) || {})
    setPrograms((m.programs as Record<string, string>) || {})
    setReady(true)
  }

  useEffect(() => {
    refresh().catch(() => setReady(true))
  }, [])

  return (
    <CapsCtx.Provider value={{ ready, deviceModel, devices, capabilities, batteryTypes, programs, refresh }}>
      {children}
    </CapsCtx.Provider>
  )
}

export function useCapabilities() {
  return useContext(CapsCtx)
}
