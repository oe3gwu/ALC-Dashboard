/** Named UI palettes. Light/dark mode is orthogonal (see theme.tsx). */

export type ThemePackId = 'elv' | 'scch' | 'dracula'

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
}

/** Built-in packs. “ELV” AdminLTE; “SCCH” Password-Pusher lime; “Dracula” / Alucard. */
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
    id: 'dracula',
    label: 'Dracula',
    logoSrc: '/jerrec-logo.png',
    logoAlt: 'Dracula',
    defaultMode: 'dark',
  },
]

export const DEFAULT_THEME_PACK: ThemePackId = 'elv'

export function isThemePackId(v: string | null | undefined): v is ThemePackId {
  return v === 'elv' || v === 'scch' || v === 'dracula'
}

/** Map legacy pack ids from older builds. */
export function normalizeThemePackId(v: string | null | undefined): ThemePackId | null {
  if (v === 'jerrec') return 'dracula'
  if (isThemePackId(v)) return v
  return null
}

export function getThemePack(id: ThemePackId): ThemePack {
  return THEME_PACKS.find((p) => p.id === id) ?? THEME_PACKS[0]
}
