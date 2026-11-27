import { useEffect, useState } from 'react'
import Icon from '../components/common/Icon.jsx'
import { getJobDetails } from '../services/api.js'

function salaryLabel(job) {
  if (!job.salary_min && !job.salary_max) return 'Salary not listed'
  const currency = job.salary_currency || 'USD'
  const format = (value) => new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(value)
  if (job.salary_min && job.salary_max) {
    return `${format(job.salary_min)} – ${format(job.salary_max)} / year`
  }
  return `${format(job.salary_min || job.salary_max)} / year`
}

export default function JobDetails({ jobId, onOpenJob, onNavigate }) {
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    getJobDetails(jobId, { signal: controller.signal })
      .then(setJob)
      .catch((requestError) => {
        if (requestError.name !== 'AbortError') setError(requestError.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [jobId, attempt])

  if (loading) {
    return (
      <div className="surface-card discovery-state" role="status">
        <span className="loading-spinner" />
        <p>Loading role details…</p>
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="surface-card discovery-state discovery-state--error" role="alert">
        <span className="empty-state__icon"><Icon name="search" size={21} /></span>
        <h2>We couldn’t load this role.</h2>
        <p>{error || 'The requested job could not be found.'}</p>
        <div className="empty-state__actions">
          <button className="button button--primary" type="button" onClick={() => setAttempt((n) => n + 1)}>
            Try again
          </button>
          <button className="button button--quiet" type="button" onClick={() => onNavigate('picks')}>
            Back to Picks
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="job-detail-page">
      <button className="text-link job-detail-back" type="button" onClick={() => onNavigate('picks')}>
        <span aria-hidden="true">←</span> Back to Picks
      </button>
      <div className="job-detail-grid">
        <main className="job-detail-main">
          <section className="surface-card job-detail-hero">
            <div className="job-card__topline">
              <span className="job-card__category">{job.category}</span>
              <span className="synthetic-tag">{job.data_source}</span>
            </div>
            <h2>{job.title}</h2>
            <p className="job-detail-company">{job.company}</p>
            <div className="job-card__metadata">
              <span><Icon name="pin" size={14} /> {job.location}</span>
              <span>{job.work_mode}</span>
              <span>{job.employment_type}</span>
            </div>
            <p className="job-detail-salary">{salaryLabel(job)}</p>
            <div className="job-detail-score">
              <div className="match-score match-score--large">
                <strong>{job.match.score}</strong><span>%</span>
                <small>profile fit</small>
              </div>
              <p>
                Deterministic compatibility score based on your saved profile.
                This is not a hiring probability.
              </p>
            </div>
          </section>

          <section className="surface-card detail-section">
            <p className="eyebrow">ABOUT THE ROLE</p>
            <p className="job-detail-description">{job.description}</p>
            <h3>What you’ll work on</h3>
            <ul className="detail-list">
              {job.responsibilities.map((responsibility) => (
                <li key={responsibility}>{responsibility}</li>
              ))}
            </ul>
          </section>

          <section className="surface-card detail-section">
            <p className="eyebrow">SKILLS & EXPERIENCE</p>
            <div className="detail-skill-group">
              <h3>Required skills</h3>
              <div className="detail-chip-list">
                {job.required_skills.map((skill) => {
                  const matched = job.match.matched_skills.some(
                    (item) => item.toLowerCase() === skill.toLowerCase(),
                  )
                  return (
                    <span className={`detail-skill${matched ? ' detail-skill--matched' : ' detail-skill--missing'}`} key={skill}>
                      {matched && <Icon name="check" size={13} />}{skill}
                    </span>
                  )
                })}
              </div>
              {job.match.missing_required_skills.length > 0 && (
                <p className="detail-hint">
                  Missing from the manually entered profile: {job.match.missing_required_skills.join(', ')}
                </p>
              )}
            </div>
            <div className="detail-skill-group">
              <h3>Preferred skills</h3>
              <div className="detail-chip-list">
                {job.preferred_skills.map((skill) => {
                  const matched = job.match.matched_skills.some(
                    (item) => item.toLowerCase() === skill.toLowerCase(),
                  )
                  return (
                    <span className={`detail-skill${matched ? ' detail-skill--matched' : ''}`} key={skill}>
                      {matched && <Icon name="check" size={13} />}{skill}
                    </span>
                  )
                })}
              </div>
            </div>
            <p className="detail-experience">
              Experience requested: {job.min_experience_years}+ years
              {job.max_experience_years ? ` (up to ${job.max_experience_years} listed)` : ''}
            </p>
          </section>

          <section className="surface-card detail-section">
            <p className="eyebrow">WHY THIS MATCH</p>
            <h3>Score breakdown</h3>
            <p className="detail-hint">
              Configurable weighted average of each applicable criterion.
              Criteria without candidate preferences are excluded.
            </p>
            {job.match.score_breakdown.length === 0 ? (
              <p className="detail-hint">
                Add skills or preferences to your candidate profile to calculate
                an applicable score breakdown.
              </p>
            ) : (
              <div className="breakdown-list">
                {job.match.score_breakdown.map((item) => (
                <div className="breakdown-item" key={item.key}>
                  <div className="breakdown-item__heading">
                    <span>
                      {item.label}
                      <small>{(item.weight * 100).toLocaleString(undefined, { maximumFractionDigits: 1 })}% weight</small>
                    </span>
                    <strong>
                      {item.score}%
                      <small>+{item.contribution.toFixed(1)} pts</small>
                    </strong>
                  </div>
                  <div className="breakdown-track">
                    <span style={{ width: `${item.score}%` }} />
                  </div>
                  <p>{item.evidence.length ? item.evidence.join(' · ') : 'No direct preference overlap'}</p>
                </div>
                ))}
              </div>
            )}
            <div className="profile-evidence">
              <span className="profile-evidence__icon"><Icon name="resume" size={16} /></span>
              <div>
                <strong>Profile evidence</strong>
                <p>{job.evidence_notice}</p>
                {job.profile_evidence.length > 0 && (
                  <ul className="detail-list detail-list--compact">
                    {job.profile_evidence.map((evidence) => <li key={evidence}>{evidence}</li>)}
                  </ul>
                )}
              </div>
            </div>
          </section>

          <section className="surface-card detail-section">
            <p className="eyebrow">RELATED OPPORTUNITIES</p>
            <h3>Similar roles</h3>
            {job.similar_jobs.length === 0 ? (
              <p className="detail-hint">No similar listings are available yet.</p>
            ) : (
              <div className="similar-jobs">
                {job.similar_jobs.map((similar) => (
                  <button className="similar-job" key={similar.id} type="button" onClick={() => onOpenJob(similar.id)}>
                    <span>
                      <strong>{similar.title}</strong>
                      <small>{similar.company} · {similar.location}</small>
                    </span>
                    <Icon name="arrow" size={15} />
                  </button>
                ))}
              </div>
            )}
          </section>
        </main>

        <aside className="side-note-card job-detail-aside">
          <p className="eyebrow">MATCH SUMMARY</p>
          <div className="match-score match-score--large">
            <strong>{job.match.score}</strong><span>%</span>
            <small>profile fit</small>
          </div>
          <ul className="detail-reasons">
            {job.match.reasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
          <div className="side-note-card__rule" />
          <p className="eyebrow">MATCHING PREFERENCES</p>
          {job.match.matching_preferences.length ? (
            <div className="detail-chip-list">
              {job.match.matching_preferences.map((preference) => (
                <span className="skill-chip" key={preference}>{preference}</span>
              ))}
            </div>
          ) : (
            <p>No saved role, location, or work preferences overlap.</p>
          )}
          <p className="detail-hint">
            Scores explain profile overlap only. They are not hiring probabilities.
          </p>
        </aside>
      </div>
    </div>
  )
}
