import { useEffect, useState } from 'react'
import { api } from '../api'
import { useLive } from '../live'
import { useLocale } from '../locale'

export function DeviceInfo() {
  const { t } = useLocale()
  const { connection } = useLive()
  const [info, setInfo] = useState<Record<string, unknown> | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    setErr('')
    api
      .deviceInfo()
      .then(setInfo)
      .catch((e) => {
        setInfo(null)
        setErr(String(e.message || e))
      })
  }, [connection?.device_model, connection?.simulator, connection?.port, connection?.connected])

  const isSim = Boolean(info?.simulator || info?.mock)

  return (
    <>
      <h1>{t('dev.title')}</h1>
      {err && <div className="toast error">{err}</div>}
      <div className="panel stack dev-page">
        {info ? (
          <>
            <div className="form-grid">
              <label className="field">
                {t('dev.device')}
                <input type="text" readOnly tabIndex={-1} value={String(info.device_label ?? '—')} />
              </label>
              <label className="field">
                {t('dev.port')}
                <input
                  type="text"
                  readOnly
                  tabIndex={-1}
                  value={isSim ? String(info.status_label || t('dev.simulator')) : String(info.port ?? '—')}
                />
              </label>
              <label className="field">
                {t('dev.serial')}
                <input type="text" readOnly tabIndex={-1} value={String(info.serial_number ?? '—')} />
              </label>
              <label className="field">
                {t('dev.firmware')}
                <input type="text" readOnly tabIndex={-1} value={String(info.firmware ?? '—')} />
              </label>
            </div>
            {info.note && <div className="toast">{String(info.note)}</div>}
            <div className="toast">{t('dev.riNote')}</div>
          </>
        ) : (
          !err && <div>{t('common.loading')}</div>
        )}
      </div>
    </>
  )
}
