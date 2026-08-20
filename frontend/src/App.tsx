import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { LiveProvider } from './live'
import { BatteryDatabase } from './pages/BatteryDatabase'
import { ChannelDetail } from './pages/ChannelDetail'
import { ChemistryParams } from './pages/ChemistryParams'
import { Dashboard } from './pages/Dashboard'
import { DataLogger } from './pages/DataLogger'
import { DeviceInfo } from './pages/DeviceInfo'
import { FirmwareUpdate } from './pages/FirmwareUpdate'
import { Help } from './pages/Help'
import { Legal } from './pages/Legal'
import { Settings } from './pages/Settings'
import { StartProcess } from './pages/StartProcess'
import { CapabilitiesProvider } from './capabilities'
import { LocaleProvider } from './locale'
import { ThemeProvider } from './theme'

export default function App() {
  return (
    <ThemeProvider>
      <LocaleProvider>
        <CapabilitiesProvider>
          <LiveProvider>
            <BrowserRouter>
              <Routes>
                <Route element={<Layout />}>
                  <Route index element={<Dashboard />} />
                  <Route path="connection" element={<Navigate to="/settings" replace />} />
                  <Route path="start" element={<StartProcess />} />
                  <Route path="channel/:id" element={<ChannelDetail />} />
                  <Route path="batteries" element={<BatteryDatabase />} />
                  <Route path="chemistry" element={<ChemistryParams />} />
                  <Route path="logger" element={<DataLogger />} />
                  <Route path="device" element={<DeviceInfo />} />
                  <Route path="firmware" element={<FirmwareUpdate />} />
                  <Route path="settings" element={<Settings />} />
                  <Route path="help" element={<Help />} />
                  <Route path="legal" element={<Legal />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
              </Routes>
            </BrowserRouter>
          </LiveProvider>
        </CapabilitiesProvider>
      </LocaleProvider>
    </ThemeProvider>
  )
}
