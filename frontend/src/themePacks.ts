/** Named UI palettes. Light/dark mode is orthogonal (see theme.tsx). */

export type ThemePackId = 'elv' | 'scch'

export type ThemePack = {
  id: ThemePackId
  /** Display name in Settings (not translated — brand/product names). */
  label: string
  /** Optional brand logo in the header (public URL). */
  logoSrc?: string
  logoAlt?: string
}

/** Built-in packs. “ELV” is the AdminLTE-inspired default; “SCCH” uses lime accents. */
export const THEME_PACKS: readonly ThemePack[] = [
  {
    id: 'elv',
    label: 'ELV',
    logoSrc: '/elv-logo.png',
    logoAlt: 'ELV',
  },
  {
    id: 'scch',
    label: 'SCCH',
    logoSrc: '/scch-logo.png',
    logoAlt: 'SCCH',
  },
]

export const DEFAULT_THEME_PACK: ThemePackId = 'elv'

export function isThemePackId(v: string | null | undefined): v is ThemePackId {
  return v === 'elv' || v === 'scch'
}

export function getThemePack(id: ThemePackId): ThemePack {
  return THEME_PACKS.find((p) => p.id === id) ?? THEME_PACKS[0]
}
