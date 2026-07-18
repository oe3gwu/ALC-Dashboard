import { useEffect, useState } from 'react'
import { api } from '../api'
import { useCapabilities } from '../capabilities'
import { useLocale } from '../locale'

type Guide = {
  safety: string
  steps: string[]
  notes: string[]
  filename_hint: string
  tool_hint: string
  device_model?: string
  device_label?: string
  supported?: boolean
}

export function FirmwareUpdate() {
  const { t } = useLocale()
  const { deviceModel, capabilities } = useCapabilities()
  const [guide, setGuide] = useState<Guide | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    setGuide(null)
    setErr('')
    api
      .firmwareGuide()
      .then(setGuide)
      .catch((e) => setErr(String((e as Error).message || e)))
  }, [deviceModel])

  if (err) {
    return (
      <div className="fw-page">
        <h1>{t('fw.title')}</h1>
        <div className="toast error">{err}</div>
      </div>
    )
  }

  if (!guide) {
    return (
      <div className="fw-page">
        <h1>{t('fw.title')}</h1>
        <p className="lead">{t('common.loading')}</p>
      </div>
    )
  }

  const label = guide.device_label || deviceModel
  const supported = capabilities.firmware_guided && guide.supported !== false

  return (
    <div className="fw-page">
      <header className="fw-header">
        <h1>{t('fw.title')}</h1>
        {label && <p className="fw-device">{label}</p>}
        <p className="lead">{t('fw.lead')}</p>
      </header>

      <div className="toast error" role="alert">
        {t('fw.noFlash')}
      </div>

      {!supported ? (
        <div className="toast" role="status">
          {t('fw.notSupported')}
        </div>
      ) : (
        <>
          {guide.safety && (
            <div className="toast" role="status">
              {guide.safety}
            </div>
          )}

          <section className="panel fw-section">
            <h2>{t('fw.sectionFile')}</h2>
            <p className="fw-mono">{guide.filename_hint}</p>
          </section>

          <section className="panel fw-section">
            <h2>{t('fw.sectionSteps')}</h2>
            <ol className="fw-steps">
              {guide.steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
          </section>

          <section className="panel fw-section">
            <h2>{t('fw.sectionTool')}</h2>
            <p className="fw-body">{guide.tool_hint}</p>
          </section>

          {guide.notes.length > 0 && (
            <section className="panel fw-section">
              <h2>{t('fw.sectionNotes')}</h2>
              <ul className="fw-notes">
                {guide.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  )
}
