import Icon from '../components/common/Icon.jsx'

const columns = [
  { title: 'Saved', tone: 'lavender' },
  { title: 'Ready to apply', tone: 'blue' },
  { title: 'Applied', tone: 'amber' },
  { title: 'Interview', tone: 'mint' },
  { title: 'Offer', tone: 'green' },
  { title: 'Closed', tone: 'gray' },
]

export default function Tracker() {
  return (
    <div className="tracker-page">
      <div className="page-lead page-lead--compact">
        <div>
          <p className="eyebrow">YOUR JOB SEARCH, AT A GLANCE</p>
          <h2>One calm place to keep things moving.</h2>
          <p>Your board is ready. Job tracking will be connected in a later phase.</p>
        </div>
        <span className="lead-mark lead-mark--warm"><Icon name="tracker" size={21} /></span>
      </div>
      <section className="tracker-board" aria-label="Job application stages">
        {columns.map((column) => (
          <section className="tracker-column" key={column.title} aria-label={column.title}>
            <div className="tracker-column__heading">
              <span className={`tracker-dot tracker-dot--${column.tone}`} />
              <h3>{column.title}</h3>
              <span className="tracker-count">0</span>
            </div>
            <div className="tracker-column__empty">
              <span className="tracker-column__mark">—</span>
              <p>No roles here yet</p>
            </div>
          </section>
        ))}
      </section>
      <p className="tracker-caption">
        <Icon name="check" size={15} /> Your board will be ready when job tracking is enabled.
      </p>
    </div>
  )
}
