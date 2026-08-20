import { useLocale } from '../locale'

export function Legal() {
  const { t } = useLocale()
  return (
    <>
      <h1>{t('legal.title')}</h1>
      <p className="muted">{t('legal.intro')}</p>
      <div className="panel legal-page">
        <section className="legal-section">
          <h2>{t('legal.affiliationH')}</h2>
          <p className="legal-lead">{t('legal.affiliationLead')}</p>
          <p>{t('legal.affiliationP1')}</p>
          <p>{t('legal.affiliationP2')}</p>
        </section>
        <section className="legal-section">
          <h2>{t('legal.logoH')}</h2>
          <p>{t('legal.logoP1')}</p>
          <p>{t('legal.logoP2')}</p>
        </section>
        <section className="legal-section">
          <h2>{t('legal.marksH')}</h2>
          <p>{t('legal.marksP')}</p>
        </section>
        <section className="legal-section">
          <h2>{t('legal.recordH')}</h2>
          <p>{t('legal.recordP')}</p>
        </section>
      </div>
    </>
  )
}
