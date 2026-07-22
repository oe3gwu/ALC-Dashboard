import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  DEFAULT_THEME_PACK,
  THEME_PACKS,
  isThemePackId,
  type ThemePackId,
} from './themePacks'

export type ThemeMode = 'dark' | 'light'
/** @deprecated Use ThemeMode — kept for existing imports. */
export type Theme = ThemeMode

const MODE_KEY = 'elv-alc-theme'
const PACK_KEY = 'elv-alc-theme-pack'

type ThemeCtx = {
  /** Light / dark within the selected pack. */
  theme: ThemeMode
  setTheme: (t: ThemeMode) => void
  toggle: () => void
  /** Named palette pack (e.g. ELV). */
  themePack: ThemePackId
  setThemePack: (id: ThemePackId) => void
  packs: typeof THEME_PACKS
}

const Ctx = createContext<ThemeCtx | null>(null)

function detectOsTheme(): ThemeMode {
  try {
    if (typeof window !== 'undefined' && window.matchMedia) {
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark'
    }
  } catch {
    /* ignore */
  }
  return 'light'
}

function readStoredMode(): ThemeMode {
  try {
    const v = localStorage.getItem(MODE_KEY)
    if (v === 'light' || v === 'dark') return v
  } catch {
    /* ignore */
  }
  return detectOsTheme()
}

function readStoredPack(): ThemePackId {
  try {
    const v = localStorage.getItem(PACK_KEY)
    if (isThemePackId(v)) return v
  } catch {
    /* ignore */
  }
  return DEFAULT_THEME_PACK
}

function applyAppearance(pack: ThemePackId, mode: ThemeMode) {
  const root = document.documentElement
  root.dataset.themePack = pack
  root.dataset.theme = mode
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>(() => {
    const mode = readStoredMode()
    const pack = readStoredPack()
    applyAppearance(pack, mode)
    return mode
  })
  const [themePack, setThemePackState] = useState<ThemePackId>(() => readStoredPack())

  useEffect(() => {
    applyAppearance(themePack, theme)
    try {
      localStorage.setItem(MODE_KEY, theme)
      localStorage.setItem(PACK_KEY, themePack)
    } catch {
      /* ignore */
    }
  }, [theme, themePack])

  const value = useMemo(
    () => ({
      theme,
      setTheme: setThemeState,
      toggle: () => setThemeState((t) => (t === 'dark' ? 'light' : 'dark')),
      themePack,
      setThemePack: setThemePackState,
      packs: THEME_PACKS,
    }),
    [theme, themePack],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useTheme() {
  const v = useContext(Ctx)
  if (!v) throw new Error('ThemeProvider fehlt')
  return v
}
