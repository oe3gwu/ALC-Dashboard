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
      <p className="lead">{t('dev.lead')}</p>
      {err && <div className="toast error">{err}</div>}
      <div className="panel stack">
        {info ? (
          <>
            <div>
              {t('dev.device')} <strong>{String(info.device_label ?? '—')}</strong>
            </div>
            <div>
              {t('dev.port')}{' '}
              <strong>
                {isSim ? String(info.status_label || t('dev.simulator')) : String(info.port ?? '—')}
              </strong>
            </div>
            <div>
              {t('dev.serial')} <strong>{String(info.serial_number ?? '—')}</strong>
            </div>
            <div>
              {t('dev.firmware')} <strong>{String(info.firmware ?? '—')}</strong>
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
