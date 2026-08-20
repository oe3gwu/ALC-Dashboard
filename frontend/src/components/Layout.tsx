import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useCapabilities } from '../capabilities'
import { useLive } from '../live'
import { useLocale } from '../locale'
import { useTheme } from '../theme'
import type { MessageKey } from '../i18n'

const links: { to: string; key: MessageKey; feature?: 'battery_db' | 'chemistry_params' | 'logger' | 'firmware_guided' }[] = [
  { to: '/', key: 'nav.channels' },
  { to: '/start', key: 'nav.start' },
  { to: '/batteries', key: 'nav.batteries', feature: 'battery_db' },
  { to: '/chemistry', key: 'nav.chemistry', feature: 'chemistry_params' },
  { to: '/logger', key: 'nav.logger', feature: 'logger' },
  { to: '/device', key: 'nav.device' },
  { to: '/firmware', key: 'nav.firmware', feature: 'firmware_guided' },
  { to: '/settings', key: 'nav.settings' },
  { to: '/help', key: 'nav.help' },
]

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9Zm0-5.25a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0V3a.75.75 0 0 1 .75-.75Zm0 16.5a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0V19.5a.75.75 0 0 1 .75-.75ZM3.75 12a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 0 1.5H4.5A.75.75 0 0 1 3.75 12Zm14.25 0a.75.75 0 0 1 .75-.75H20.25a.75.75 0 0 1 0 1.5H18.75a.75.75 0 0 1-.75-.75ZM6.22 6.22a.75.75 0 0 1 1.06 0l1.06 1.06a.75.75 0 1 1-1.06 1.06L6.22 7.28a.75.75 0 0 1 0-1.06Zm9.44 9.44a.75.75 0 0 1 1.06 0l1.06 1.06a.75.75 0 1 1-1.06 1.06l-1.06-1.06a.75.75 0 0 1 0-1.06ZM17.78 6.22a.75.75 0 0 1 0 1.06l-1.06 1.06a.75.75 0 1 1-1.06-1.06l1.06-1.06a.75.75 0 0 1 1.06 0ZM7.28 15.66a.75.75 0 0 1 0 1.06L6.22 17.78a.75.75 0 0 1-1.06-1.06l1.06-1.06a.75.75 0 0 1 1.06 0Z" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
    </svg>
  )
}

function fmtTemp(n: number | null | undefined) {
  if (n === null || n === undefined) return '—'
  return `${n.toFixed(1)} °C`
}

function useSerialLedPulse(seq: number) {
  const [on, setOn] = useState(false)
  const prev = useRef(seq)
  useEffect(() => {
    if (seq === prev.current) return
    prev.current = seq
    setOn(true)
    const t = window.setTimeout(() => setOn(false), 280)
    return () => window.clearTimeout(t)
  }, [seq])
  return on
}

export function Layout() {
  const { connection, temperatures, backendOnline } = useLive()
  const { capabilities, devices, deviceModel } = useCapabilities()
  const { theme, toggle: toggleTheme, themePack, packs } = useTheme()
  const { locale, toggle: toggleLocale, t } = useLocale()
  const packMeta = packs.find((p) => p.id === themePack) ?? packs[0]
  const brandLogo = packMeta.logoSrc || '/elv-logo.png'
  const brandAlt = packMeta.logoAlt || packMeta.label

  const connected = Boolean(connection?.connected)
  const isSim = Boolean(connection?.simulator ?? connection?.mock)
  const lastError = (connection?.last_error || '').trim()
  const hasError = Boolean(lastError) && !connected
  const liveHw = connected && !isSim
  const txOn = useSerialLedPulse(liveHw ? (connection?.tx_seq ?? 0) : 0)
  const rxOn = useSerialLedPulse(liveHw ? (connection?.rx_seq ?? 0) : 0)
  const profileLabel =
    connection?.device_label ||
    devices.find((d) => d.id === (connection?.device_model || deviceModel))?.label ||
    t('sidebar.simulator')
  // Always show charger model name; port as second line when on hardware
  const statusLabel = connection?.status_label || profileLabel

  let statusDotClass = ''
  if (hasError) {
    statusDotClass = 'error'
  } else if (liveHw) {
    if (rxOn) statusDotClass = 'pulse-rx'
    else if (txOn) statusDotClass = 'pulse-tx'
    else statusDotClass = 'hw' // muted green idle; flashes red/green on RX/TX
  } else if (connected && isSim) {
    statusDotClass = 'sim'
  }

  return (
    <div className="app">
      <div className="brand-bar">
        <img className="brand-logo" src={brandLogo} alt={brandAlt} />
        <strong>ALC Dashboard</strong>
      </div>
      <header className="topbar">
        <NavLink
          to="/legal"
          className={({ isActive }) => (isActive ? 'topbar-legal active' : 'topbar-legal')}
        >
          {t('nav.legal')}
        </NavLink>
        <button
          type="button"
          className="lang-switch"
          data-locale={locale}
          onClick={toggleLocale}
          aria-label={locale === 'de' ? t('lang.toEn') : t('lang.toDe')}
        >
          <span className="lang-switch-track">
            <span className="lang-switch-label lang-switch-de">DE</span>
            <span className="lang-switch-label lang-switch-en">EN</span>
            <span className="lang-switch-knob" />
          </span>
        </button>
        {packMeta.darkOnly ? null : (
          <button
            type="button"
            className="theme-switch"
            data-theme={theme}
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? t('theme.toLight') : t('theme.toDark')}
          >
            <span className="theme-switch-track">
              <span className="theme-switch-icon theme-switch-sun">
                <SunIcon />
              </span>
              <span className="theme-switch-icon theme-switch-moon">
                <MoonIcon />
              </span>
              <span className="theme-switch-knob" />
            </span>
          </button>
        )}
      </header>
      <aside className="sidebar">
        <div className="sidebar-box">
          <div className="sidebar-box-title">{t('sidebar.status')}</div>
          <div className="sidebar-box-row">
            <span
              className={`status-dot${statusDotClass ? ` ${statusDotClass}` : ''}`}
              title={liveHw ? 'RX / TX' : undefined}
            />
            <span className="sidebar-status-text">{statusLabel}</span>
          </div>
          {liveHw && connection?.port ? (
            <div className="sidebar-status-port mono">{connection.port}</div>
          ) : null}
          {hasError ? (
            <span className="sidebar-mode-badge error" title={lastError}>
              {t('sidebar.modeError')}
            </span>
          ) : !connected ? (
            <span className="sidebar-mode-badge offline">{t('sidebar.offline')}</span>
          ) : isSim ? (
            <span className="sidebar-mode-badge">{t('sidebar.modeSim')}</span>
          ) : (
            <span className="sidebar-mode-badge connected">{t('sidebar.modeConnected')}</span>
          )}
        </div>

        <div className="sidebar-box">
          <div className="sidebar-box-title">{t('sidebar.temps')}</div>
          <dl className="sidebar-stats">
            <div>
              <dt>{t('sidebar.heatsink')}</dt>
              <dd className="mono">{fmtTemp(temperatures.heatsink_C)}</dd>
            </div>
            <div>
              <dt>{t('sidebar.psu')}</dt>
              <dd className="mono">{fmtTemp(temperatures.psu_C)}</dd>
            </div>
            <div>
              <dt>{t('sidebar.battery')}</dt>
              <dd className="mono">{fmtTemp(temperatures.battery_C)}</dd>
            </div>
          </dl>
        </div>

        <nav className="nav">
          {links.map(({ to, key, feature }) => {
            const enabled = !feature || Boolean(capabilities[feature])
            if (!enabled) {
              return (
                <span key={to} className="nav-disabled" title={t('nav.unavailable')}>
                  {t(key)}
                </span>
              )
            }
            return (
              <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => (isActive ? 'active' : undefined)}>
                {t(key)}
              </NavLink>
            )
          })}
        </nav>

        <footer className="sidebar-credit">
          <span>{t('sidebar.creditAuthor')}</span>
          <span>{t('sidebar.creditLicense')}</span>
          <span>{t('sidebar.creditAi')}</span>
        </footer>
      </aside>
      <main className="main">
        <Outlet />
      </main>

      {!backendOnline && (
        <div className="live-lost-backdrop" role="alert" aria-live="assertive">
          <div className="live-lost-dialog">
            <div className="live-lost-title">{t('live.connectionLost')}</div>
            <p className="live-lost-hint">{t('live.connectionLostHint')}</p>
          </div>
        </div>
      )}
    </div>
  )
}
