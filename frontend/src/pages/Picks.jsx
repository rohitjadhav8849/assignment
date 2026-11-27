import { useEffect, useRef, useState } from 'react'
import EmptyState from '../components/common/EmptyState.jsx'
import Icon from '../components/common/Icon.jsx'
import { getJobPicks, getJobRetrieval } from '../services/api.js'

function formatLabel(value) {
  return value.replaceAll('_', ' ')
}

const retrievalModes = [
  {
    id: 'original',
    label: 'Original Picks',
    scoreLabel: 'Candidate Match Score',
    description: 'Ranked from your saved profile with a transparent, deterministic score.',
  },
  {
    id: 'bm25',
    label: 'BM25',
    scoreLabel: 'BM25 Score',
    description: 'Keyword retrieval ranks jobs by matching words in your profile-derived query.',
  },
  {
    id: 'semantic',
    label: 'Semantic',
    scoreLabel: 'Semantic Similarity',
    description: 'Semantic retrieval ranks jobs by meaning, even when wording differs.',
  },
  {
    id: 'hybrid',
    label: 'Hybrid',
    scoreLabel: 'RRF Score',
    description: 'Hybrid retrieval combines keyword and semantic ranks using reciprocal rank fusion.',
  },
]

const sideNotes = {
  original: {
    eyebrow: 'HOW YOUR SCORE WORKS',
    title: 'Fit over volume.',
    body: 'Scores compare your saved skills and preferences to each listing. They are explainable signals, not a probability of being hired.',
  },
  bm25: {
    eyebrow: 'KEYWORD RETRIEVAL',
    title: 'Match the terms.',
    body: 'BM25 ranks jobs by keyword relevance to your profile-derived query. Its scores use a different scale from the other modes.',
  },
  semantic: {
    eyebrow: 'SEMANTIC RETRIEVAL',
    title: 'Match the meaning.',
    body: 'Semantic similarity compares your profile-derived query with job text. Its scores are not directly comparable to other modes.',
  },
  hybrid: {
    eyebrow: 'HYBRID RETRIEVAL',
    title: 'Combine the ranks.',
    body: 'RRF combines each job’s keyword and semantic rank positions. It does not combine their raw scores.',
  },
}

function JobCard({ job, mode, scoreLabel, onOpenJob }) {
  const isOriginal = mode === 'original'
  const match = job.match
  const score = isOriginal ? match?.score : job.score
  const scoreText = isOriginal ? score : Number(score).toFixed(3)

  return (
    <article className="job-card">
      {(job.category || job.data_source) && (
        <div className="job-card__topline">
          {job.category && <span className="job-card__category">{job.category}</span>}
          {job.data_source && <span className="synthetic-tag">{job.data_source}</span>}
        </div>
      )}
      <div className="job-card__heading">
        <div>
          <h3>{job.title}</h3>
          <p className="job-card__company">{job.company}</p>
        </div>
        <div
          className={`match-score${isOriginal ? '' : ' match-score--retrieval'}`}
          aria-label={`${scoreLabel}: ${scoreText}${isOriginal ? ' percent' : ''}`}
        >
          <strong>{scoreText}</strong>
          {isOriginal && <span>%</span>}
          <small>{scoreLabel}</small>
        </div>
      </div>
      {(job.location || job.work_mode || job.employment_type) && (
        <div className="job-card__metadata">
          {job.location && <span><Icon name="pin" size={14} /> {job.location}</span>}
          {job.work_mode && <span>{job.work_mode}</span>}
          {job.employment_type && <span>{job.employment_type}</span>}
        </div>
      )}
      {match && (
        <>
          <div className="job-card__skills">
            {match.matched_skills.length > 0
              ? match.matched_skills.slice(0, 4).map((skill) => (
                <span className="skill-chip" key={skill}>{skill}</span>
              ))
              : <span className="job-card__no-skills">No profile skill overlap yet</span>}
          </div>
          <ul className="job-card__reasons">
            {match.reasons.slice(0, 2).map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
        </>
      )}
      <div className="job-card__footer">
        <span className="job-card__score-note">
          {isOriginal
            ? match.score_breakdown.slice(0, 3).map((item) => formatLabel(item.key)).join(' · ')
            : 'Only comparable within this mode'}
        </span>
        <button className="text-link" type="button" onClick={() => onOpenJob(job.id)}>
          View role <Icon name="arrow" size={15} />
        </button>
      </div>
    </article>
  )
}

export default function Picks({ onNavigate, onOpenJob }) {
  const [mode, setMode] = useState('original')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const requestSequence = useRef(0)
  const activeMode = retrievalModes.find((item) => item.id === mode) || retrievalModes[0]
  const sideNote = sideNotes[mode]

  useEffect(() => {
    const controller = new AbortController()
    const requestId = ++requestSequence.current
    setLoading(true)
    setError('')
    const loadResults = mode === 'original'
      ? getJobPicks({ signal: controller.signal })
      : getJobRetrieval(mode, { signal: controller.signal })

    loadResults
      .then((response) => {
        if (requestSequence.current === requestId) setResult(response)
      })
      .catch((requestError) => {
        if (!controller.signal.aborted && requestSequence.current === requestId) {
          setError(requestError.message)
        }
      })
      .finally(() => {
        if (requestSequence.current === requestId) setLoading(false)
      })
    return () => {
      controller.abort()
      if (requestSequence.current === requestId) requestSequence.current += 1
    }
  }, [mode, attempt])

  function changeMode(nextMode) {
    if (nextMode === mode) return
    setMode(nextMode)
    setResult(null)
    setError('')
    setLoading(true)
  }

  return (
    <div className="page-grid">
      <section className="page-main">
        <div className="page-lead">
          <div>
            <p className="eyebrow">A SHORTLIST, MADE FOR YOU</p>
            <h2>Good-fit roles, without the noise.</h2>
            <p>{activeMode.description}</p>
            <div className="retrieval-mode-switcher" role="group" aria-label="Job ranking mode">
              {retrievalModes.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  aria-pressed={mode === item.id}
                  className={mode === item.id ? 'is-selected' : ''}
                  onClick={() => changeMode(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <span className="lead-mark"><Icon name="spark" size={22} /></span>
        </div>

        {loading && (
          <div className="surface-card discovery-state" role="status">
            <span className="loading-spinner" />
            <p>{mode === 'original' ? 'Finding roles that fit your preferences…' : `Searching with ${activeMode.label}…`}</p>
          </div>
        )}

        {!loading && error && (
          <div className="surface-card discovery-state discovery-state--error" role="alert">
            <span className="empty-state__icon"><Icon name="search" size={21} /></span>
            <h2>We couldn’t load {mode === 'original' ? 'your picks' : `${activeMode.label} results`}.</h2>
            <p>{error}</p>
            <button className="button button--primary" type="button" onClick={() => setAttempt((n) => n + 1)}>
              Try again
            </button>
          </div>
        )}

        {!loading && !error && result && !result.profile_configured && (
          <div className="surface-card picks-empty">
            <EmptyState
              icon="spark"
              eyebrow="YOUR PICKS"
              title="Your next opportunity starts with you"
              description="Add your skills, experience and preferences to see ranked recommendations."
            >
              <button className="button button--primary" type="button" onClick={() => onNavigate('search')}>
                Set up your profile <Icon name="arrow" size={16} />
              </button>
            </EmptyState>
          </div>
        )}

        {!loading && !error && result?.profile_configured && result.jobs.length === 0 && (
          <div className="surface-card picks-empty">
            <EmptyState
              icon="search"
              eyebrow={mode === 'original'
                ? 'NO LISTINGS YET'
                : result.query_available === false
                  ? 'SEARCH QUERY EMPTY'
                  : 'NO MATCHING JOBS'}
              title={mode === 'original'
                ? 'Your profile is ready'
                : result.query_available === false
                  ? 'Add details to your profile'
                  : 'No matching jobs found'}
              description={mode === 'original'
                ? 'No jobs are in the database yet. Start PostgreSQL and run the synthetic demo job seed command to populate Picks.'
                : result.query_available === false
                  ? 'Add skills, roles, projects or experience to build a retrieval query.'
                  : 'No jobs were returned for this retrieval mode.'}
            />
          </div>
        )}

        {!loading && !error && result?.jobs.length > 0 && (
          <div className="job-results">
            <div className="job-results__summary">
              <span>{mode === 'original' ? `${result.total} synthetic demo roles` : `${result.total} retrieved roles`}</span>
              <span>{mode === 'original'
                ? 'Sorted by Candidate Match Score · not hiring probability'
                : `Sorted by ${activeMode.scoreLabel} · not comparable across modes`}</span>
            </div>
            {result.jobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                mode={mode}
                scoreLabel={activeMode.scoreLabel}
                onOpenJob={onOpenJob}
              />
            ))}
          </div>
        )}
      </section>

      <aside className="side-note-card">
        <span className="side-note-card__icon"><Icon name="spark" size={18} /></span>
        <p className="eyebrow">{sideNote.eyebrow}</p>
        <h3>{sideNote.title}</h3>
        <p>{sideNote.body}</p>
        <div className="side-note-card__rule" />
        <button className="text-link" type="button" onClick={() => onNavigate('search')}>
          Update your profile <Icon name="arrow" size={15} />
        </button>
        <span className="quiet-label">ALL LISTINGS ARE SYNTHETIC DEMO DATA</span>
      </aside>
    </div>
  )
}
