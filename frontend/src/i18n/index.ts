import { de, type MessageKey } from './de'
import { en } from './en'

export type { MessageKey }
export type Locale = 'de' | 'en'

const catalogs: Record<Locale, Record<MessageKey, string>> = { de, en }

export type Vars = Record<string, string | number | undefined | null>

export function translate(locale: Locale, key: MessageKey, vars?: Vars): string {
  let s = catalogs[locale][key] ?? catalogs.de[key] ?? key
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replaceAll(`{${k}}`, v == null ? '' : String(v))
    }
  }
  return s
}

/** Backend stage_name (German) → message key */
const STAGE_KEYS: Record<string, MessageKey> = {
  Leerlauf: 'stage.idle',
  'Pause/Warten': 'stage.pause',
  Entladen: 'stage.discharge',
  Laden: 'stage.charge',
  Erhaltungsladung: 'stage.trickle',
  'Entladen beendet': 'stage.dischargeDone',
  Notabschaltung: 'stage.emergency',
}

export function translateStage(locale: Locale, stageName: string | undefined | null): string {
  if (!stageName) return '—'
  const key = STAGE_KEYS[stageName]
  return key ? translate(locale, key) : stageName
}
