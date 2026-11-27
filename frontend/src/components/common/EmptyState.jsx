import Icon from './Icon.jsx'

export default function EmptyState({
  icon = 'spark',
  eyebrow,
  title,
  description,
  children,
}) {
  return (
    <section className="empty-state" aria-label={title}>
      <span className="empty-state__icon">
        <Icon name={icon} size={22} />
      </span>
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h2>{title}</h2>
      <p className="empty-state__description">{description}</p>
      {children && <div className="empty-state__actions">{children}</div>}
    </section>
  )
}
