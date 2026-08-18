/** Named UI palettes. Light/dark mode is orthogonal except dark-only packs. */

export type ThemePackId = 'elv' | 'scch' | 'jerrec'

export type ThemeMode = 'dark' | 'light'

export type ThemePack = {
  id: ThemePackId
  /** Display name in Settings (not translated — brand/product names). */
  label: string
  /** Optional brand logo in the header (public URL). */
  logoSrc?: string
  logoAlt?: string
  /** Preferred mode when selecting this pack. */
  defaultMode: ThemeMode
  /** If true, light mode is unavailable for this pack. */
  darkOnly?: boolean
}

/** Built-in packs. “ELV” AdminLTE; “SCCH” Password-Pusher lime; “Jerrec” dark-only. */
export const THEME_PACKS: readonly ThemePack[] = [
  {
    id: 'elv',
    label: 'ELV',
    logoSrc: '/elv-logo.png',
    logoAlt: 'ELV',
    defaultMode: 'light',
  },
  {
    id: 'scch',
    label: 'SCCH',
    logoSrc: '/scch-logo.png',
    logoAlt: 'SCCH',
    defaultMode: 'light',
  },
  {
    id: 'jerrec',
    label: 'Jerrec',
    logoSrc: '/jerrec-logo.png',
    logoAlt: 'Jerrec',
    defaultMode: 'dark',
    darkOnly: true,
  },
]

export const DEFAULT_THEME_PACK: ThemePackId = 'elv'

export function isThemePackId(v: string | null | undefined): v is ThemePackId {
  return v === 'elv' || v === 'scch' || v === 'jerrec'
}

/** Map legacy pack ids from older builds. */
export function normalizeThemePackId(v: string | null | undefined): ThemePackId | null {
  if (v === 'dracula') return 'jerrec'
  if (isThemePackId(v)) return v
  return null
}

export function getThemePack(id: ThemePackId): ThemePack {
  return THEME_PACKS.find((p) => p.id === id) ?? THEME_PACKS[0]
}

export function packIsDarkOnly(id: ThemePackId): boolean {
  return Boolean(getThemePack(id).darkOnly)
}
