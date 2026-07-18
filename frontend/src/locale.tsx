import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { translate, translateStage, type Locale, type MessageKey, type Vars } from './i18n'

const STORAGE_KEY = 'elv-alc-locale'

type LocaleCtx = {
  locale: Locale
  setLocale: (l: Locale) => void
  toggle: () => void
  t: (key: MessageKey, vars?: Vars) => string
  stage: (stageName: string | undefined | null) => string
}

const Ctx = createContext<LocaleCtx | null>(null)

function detectOsLocale(): Locale {
  try {
    const list =
      typeof navigator !== 'undefined'
        ? navigator.languages?.length
          ? navigator.languages
          : navigator.language
            ? [navigator.language]
            : []
        : []
    for (const tag of list) {
      if (String(tag).toLowerCase().startsWith('de')) return 'de'
    }
  } catch {
    /* ignore */
  }
  return 'en'
}

function readStored(): Locale {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'de' || v === 'en') return v
  } catch {
    /* ignore */
  }
  return detectOsLocale()
}

function applyLang(locale: Locale) {
  document.documentElement.lang = locale
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    const initial = readStored()
    applyLang(initial)
    return initial
  })

  useEffect(() => {
    applyLang(locale)
    try {
      localStorage.setItem(STORAGE_KEY, locale)
    } catch {
      /* ignore */
    }
  }, [locale])

  const value = useMemo<LocaleCtx>(
    () => ({
      locale,
      setLocale: setLocaleState,
      toggle: () => setLocaleState((l) => (l === 'de' ? 'en' : 'de')),
      t: (key, vars) => translate(locale, key, vars),
      stage: (name) => translateStage(locale, name),
    }),
    [locale],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useLocale() {
  const v = useContext(Ctx)
  if (!v) throw new Error('LocaleProvider missing')
  return v
}

export function useT() {
  return useLocale().t
}
