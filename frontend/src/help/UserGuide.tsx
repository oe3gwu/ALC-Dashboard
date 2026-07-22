import { useLocale } from '../locale'
import { getUserGuide, type GuideBlock } from './userGuide'

function Block({ block }: { block: GuideBlock }) {
  if (block.type === 'p') {
    return <p>{block.text}</p>
  }
  if (block.type === 'warn') {
    return (
      <p className="user-guide-warn" role="note">
        {block.text}
      </p>
    )
  }
  if (block.type === 'links') {
    return (
      <ul className="user-guide-links">
        {block.items.map((item) => (
          <li key={item.href}>
            <a href={item.href} target="_blank" rel="noopener noreferrer">
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    )
  }
  const Tag = block.type === 'ol' ? 'ol' : 'ul'
  return (
    <Tag>
      {block.items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </Tag>
  )
}

export function UserGuide() {
  const { locale, t } = useLocale()
  const sections = getUserGuide(locale)

  return (
    <>
      <h1>{t('help.title')}</h1>
      <p className="lead">{t('help.lead')}</p>
      <div className="panel user-guide">
        <div className="user-guide-sections">
          {sections.map((section) => (
            <details
              key={section.id}
              className="user-guide-section"
              open={section.id === 'overview' || section.id === 'safety'}
            >
              <summary>{section.title}</summary>
              <div className="user-guide-body">
                {section.blocks.map((block, i) => (
                  <Block key={`${section.id}-${i}`} block={block} />
                ))}
              </div>
            </details>
          ))}
        </div>
      </div>
    </>
  )
}
