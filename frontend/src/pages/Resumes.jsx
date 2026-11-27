import { useEffect, useState } from 'react'
import Icon from '../components/common/Icon.jsx'
import {
  getCandidateProfile,
  confirmResumeProfile,
  getResume,
  getResumes,
  retryResumeExtraction,
  saveCandidateProfile,
  uploadResume,
} from '../services/api.js'

function formatFileSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function commaSeparated(value) {
  return value.split(/[,\n]/).map((item) => item.trim()).filter(Boolean)
}

function normalizedText(value) {
  return String(value ?? '')
    .normalize('NFKC')
    .replace(/\s+/g, ' ')
    .trim()
    .toLocaleLowerCase()
}

function valueText(value) {
  return typeof value === 'string' ? value : value?.value ?? ''
}

function uniqueEvidence(items = [], omitText = '') {
  const seen = new Set()
  const omitted = normalizedText(omitText)
  return items.filter((item) => {
    const snippet = typeof item === 'string' ? item : item?.snippet
    const key = normalizedText(snippet)
    if (!key || key === omitted || (omitted && omitted.includes(key)) || seen.has(key)) return false
    seen.add(key)
    return true
  }).map((item) => ({
    snippet: typeof item === 'string' ? item : item.snippet,
  }))
}

function uniqueSkills(items = []) {
  const seen = new Set()
  const seenEvidence = new Set()
  return items.reduce((result, item) => {
    const name = item.name || valueText(item.value)
    const key = normalizedText(name)
    if (!key || seen.has(key)) return result
    seen.add(key)
    const evidence = uniqueEvidence(item.evidence, name).filter((entry) => {
      const evidenceKey = normalizedText(entry.snippet)
      if (seenEvidence.has(evidenceKey)) return false
      seenEvidence.add(evidenceKey)
      return true
    })
    result.push({
      ...item,
      name,
      evidence,
    })
    return result
  }, [])
}

function displayResumeFacts(resume) {
  const extraction = resume?.extracted_data
  if (!extraction) return null
  const profile = resume.is_confirmed ? resume.review_profile : null
  if (!profile) {
    return {
      full_name: extraction.full_name,
      email: extraction.email,
      phone: extraction.phone,
      total_experience_years: extraction.total_experience_years,
      skills: uniqueSkills(extraction.skills.map((skill) => ({ ...skill, source: 'resume' }))),
      education: extraction.education.map((item) => ({ ...item, source: 'resume' })),
      work_experience: extraction.work_experience.map((item) => ({ ...item, source: 'resume' })),
      projects: extraction.projects.map((item) => ({ ...item, source: 'resume' })),
      certifications: extraction.certifications.map((item) => ({ ...item, source: 'resume' })),
      achievements: extraction.achievements.map((item) => ({ ...item, source: 'resume' })),
    }
  }

  const manualSkills = (profile.manual_skills || []).map((name) => ({
    name,
    source: 'manual',
    evidence: [],
  }))
  return {
    full_name: profile.full_name,
    email: profile.email,
    phone: profile.phone,
    total_experience_years: profile.experience_years,
    skills: uniqueSkills([
      ...(profile.skills || []).map((skill) => ({
        ...skill,
        name: skill.value,
      })),
      ...manualSkills,
    ]),
    education: (profile.education || []).map((item) => ({
      ...item,
      source: item.source,
    })),
    work_experience: (profile.work_experience || []).map((item) => ({
      ...item,
      technologies: uniqueSkills(item.technologies),
    })),
    projects: (profile.projects || []).map((item) => ({
      ...item,
      technologies: uniqueSkills(item.technologies),
    })),
    certifications: profile.certifications || [],
    achievements: profile.achievements || [],
  }
}

function extractionStatusLabel(resume) {
  if (resume.is_confirmed) return 'Confirmed'
  if (resume.extraction_status === 'needs_review') return 'Ready for review'
  if (resume.extraction_status === 'failed') {
    return resume.retryable ? 'Retryable failure' : 'Permanent failure'
  }
  return resume.extraction_status.replaceAll('_', ' ')
}

function Section({ title, children }) {
  return (
    <section className="resume-facts-section">
      <h4>{title}</h4>
      {children}
    </section>
  )
}

function sourceLabel(source) {
  return source === 'manual' ? 'Manually added' : 'From resume'
}

function EvidenceSnippets({ items, omitText = '' }) {
  return uniqueEvidence(items, omitText).map((item) => (
    <blockquote key={item.snippet}>{item.snippet}</blockquote>
  ))
}

function TechnologyChips({ items = [] }) {
  const technologies = uniqueSkills(items)
  if (!technologies.length) return null
  return (
    <div className="resume-tech-list" aria-label="Project technologies">
      {technologies.map((item) => (
        <span
          className="resume-tech-chip"
          key={normalizedText(item.name)}
          title={item.evidence[0]?.snippet ? `Resume evidence: ${item.evidence[0].snippet}` : undefined}
        >
          {item.name}
        </span>
      ))}
    </div>
  )
}

export default function Resumes() {
  const [resumes, setResumes] = useState([])
  const [activeResume, setActiveResume] = useState(null)
  const [reviewJson, setReviewJson] = useState('')
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [candidate, setCandidate] = useState(null)
  const [manualProfile, setManualProfile] = useState({
    full_name: '',
    skills: '',
    experience_years: '',
    preferred_roles: '',
  })
  const [manualLoading, setManualLoading] = useState(true)
  const [manualSaving, setManualSaving] = useState(false)
  const [manualError, setManualError] = useState('')
  const [manualNotice, setManualNotice] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    getResumes()
      .then((items) => {
        if (active) setResumes(items)
      })
      .catch((requestError) => {
        if (active) setError(requestError.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [attempt])

  useEffect(() => {
    let active = true
    getCandidateProfile()
      .then((profile) => {
        if (!active) return
        setCandidate(profile)
        setManualProfile({
          full_name: profile.full_name || '',
          skills: (profile.skills || []).join(', '),
          experience_years: profile.experience_years == null
            ? ''
            : String(profile.experience_years),
          preferred_roles: (profile.preferred_roles || []).join(', '),
        })
      })
      .catch((requestError) => {
        if (active) setManualError(requestError.message)
      })
      .finally(() => {
        if (active) setManualLoading(false)
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!activeResume || !['queued', 'processing'].includes(activeResume.extraction_status)) {
      return undefined
    }

    let cancelled = false
    let timer
    async function pollResume() {
      try {
        const [latest, items] = await Promise.all([
          getResume(activeResume.id),
          getResumes(),
        ])
        if (cancelled) return
        setActiveResume(latest)
        setResumes(items)
        if (latest.extraction_status === 'needs_review') {
          setReviewJson(
            latest.review_profile
              ? JSON.stringify(latest.review_profile, null, 2)
              : '',
          )
        }
        if (['queued', 'processing'].includes(latest.extraction_status)) {
          timer = setTimeout(pollResume, 2000)
        }
      } catch (requestError) {
        if (cancelled) return
        setError(requestError.message)
        timer = setTimeout(pollResume, 4000)
      }
    }

    timer = setTimeout(pollResume, 1500)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [activeResume?.id, activeResume?.extraction_status])

  function updateManualField(event) {
    const { name, value } = event.target
    setManualProfile((current) => ({ ...current, [name]: value }))
  }

  async function saveManualCandidateProfile(event) {
    event.preventDefault()
    if (!candidate) return
    setManualSaving(true)
    setManualError('')
    setManualNotice('')
    try {
      const saved = await saveCandidateProfile({
        ...candidate,
        full_name: manualProfile.full_name.trim() || 'Candidate',
        skills: commaSeparated(manualProfile.skills),
        experience_years: manualProfile.experience_years === ''
          ? null
          : Number(manualProfile.experience_years),
        preferred_roles: commaSeparated(manualProfile.preferred_roles),
        profile_source: 'manual',
      })
      setCandidate(saved)
      setManualProfile({
        full_name: saved.full_name,
        skills: saved.skills.join(', '),
        experience_years: saved.experience_years == null
          ? ''
          : String(saved.experience_years),
        preferred_roles: saved.preferred_roles.join(', '),
      })
      setManualNotice('Manual profile saved. Search preferences were preserved.')
    } catch (requestError) {
      setManualError(requestError.message)
    } finally {
      setManualSaving(false)
    }
  }

  async function selectResume(resumeId) {
    setError('')
    setNotice('')
    try {
      const resume = await getResume(resumeId)
      setActiveResume(resume)
      setReviewJson(
        resume.review_profile
          ? JSON.stringify(resume.review_profile, null, 2)
          : '',
      )
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  async function refreshResumes(selectedId) {
    const items = await getResumes()
    setResumes(items)
    if (selectedId != null) await selectResume(selectedId)
  }

  async function handleUpload(event) {
    const selected = event.target.files?.[0]
    event.target.value = ''
    if (!selected) return
    setUploading(true)
    setError('')
    setNotice('')
    try {
      const uploaded = await uploadResume(selected)
      setActiveResume(uploaded)
      setReviewJson(
        uploaded.review_profile
          ? JSON.stringify(uploaded.review_profile, null, 2)
          : '',
      )
      await refreshResumes(uploaded.id)
      setNotice(uploaded.message || 'Resume uploaded.')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setUploading(false)
    }
  }

  async function handleRetry() {
    if (!activeResume) return
    setUploading(true)
    setError('')
    setNotice('')
    try {
      const retried = await retryResumeExtraction(activeResume.id)
      setActiveResume(retried)
      setReviewJson(
        retried.review_profile
          ? JSON.stringify(retried.review_profile, null, 2)
          : '',
      )
      await refreshResumes(retried.id)
      setNotice(retried.message || 'Resume reprocessed.')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setUploading(false)
    }
  }

  async function handleConfirm(event) {
    event.preventDefault()
    if (!activeResume) return
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const profile = JSON.parse(reviewJson)
      const confirmed = await confirmResumeProfile(activeResume.id, profile)
      setActiveResume(confirmed)
      setReviewJson(JSON.stringify(confirmed.review_profile, null, 2))
      await refreshResumes(confirmed.id)
      setNotice(confirmed.message || 'Candidate profile confirmed.')
    } catch (requestError) {
      setError(
        requestError instanceof SyntaxError
          ? 'Review data must be valid JSON before it can be confirmed.'
          : requestError.message,
      )
    } finally {
      setSaving(false)
    }
  }

  const extraction = activeResume?.extracted_data
  const report = activeResume?.validation_report
  const displayFacts = displayResumeFacts(activeResume)

  return (
    <div className="page-grid">
      <section className="page-main">
        <div className="page-lead">
          <div>
            <p className="eyebrow">YOUR CAREER STORY</p>
            <h2>Turn your resume into a profile you can verify.</h2>
            <p>Resume facts are extracted with source evidence and only affect matching after you confirm them.</p>
          </div>
          <span className="lead-mark"><Icon name="resume" size={21} /></span>
        </div>
        <section className="surface-card resume-card resume-card--has-file">
          <div className="resume-upload-row">
            <div>
              <p className="eyebrow">PRIVATE RESUME LIBRARY</p>
              <h3>Upload a PDF resume</h3>
              <p>PDF only · maximum 10 MB. Files are stored outside public web assets.</p>
            </div>
            <label className="button button--primary resume-upload-button">
              <Icon name="upload" size={16} /> {uploading ? 'Processing…' : 'Choose PDF'}
              <input
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleUpload}
                disabled={uploading}
                aria-label="Upload a PDF resume"
              />
            </label>
          </div>
          {loading && <p role="status">Loading your resume versions…</p>}
          {!loading && resumes.length === 0 && (
            <p className="resume-empty-note">No resume versions uploaded yet.</p>
          )}
          {resumes.length > 0 && (
            <div className="resume-version-list" aria-label="Resume versions">
              {resumes.map((resume) => (
                <button
                  className={`resume-version${activeResume?.id === resume.id ? ' is-selected' : ''}`}
                  key={resume.id}
                  type="button"
                  onClick={() => selectResume(resume.id)}
                >
                  <span className="resume-version__icon"><Icon name="resume" size={17} /></span>
                  <span className="resume-version__copy">
                    <strong>{resume.original_filename}</strong>
                    <small>{formatFileSize(resume.size_bytes)} · {formatDate(resume.uploaded_at)}</small>
                  </span>
                  <span className={`resume-status resume-status--${resume.extraction_status}`}>
                    {extractionStatusLabel(resume)}
                  </span>
                </button>
              ))}
            </div>
          )}
          {error && <p className="form-notice form-notice--error" role="alert">{error}</p>}
          {notice && <p className="form-notice" role="status">{notice}</p>}
        </section>
        <form className="surface-card manual-profile-form" onSubmit={saveManualCandidateProfile}>
          <div>
            <p className="eyebrow">MANUAL PROFILE OPTION</p>
            <h3>Enter your profile without a resume</h3>
            <p>
              Use this fallback if you do not want to upload a resume or extraction
              is unavailable. Saving switches matching to manually entered facts
              and preserves Your Search preferences.
            </p>
          </div>
          <div className="manual-profile-fields">
            <label className="field">
              <span className="field__label">Name</span>
              <input
                className="text-field"
                name="full_name"
                value={manualProfile.full_name}
                onChange={updateManualField}
                maxLength={120}
                placeholder="Your name"
              />
            </label>
            <label className="field">
              <span className="field__label">Skills</span>
              <textarea
                name="skills"
                value={manualProfile.skills}
                onChange={updateManualField}
                rows={2}
                placeholder="Python, SQL, React"
              />
              <span className="field__hint">Separate skills with commas.</span>
            </label>
            <label className="field">
              <span className="field__label">Experience in years</span>
              <input
                className="text-field"
                name="experience_years"
                type="number"
                min="0"
                max="60"
                step="0.5"
                value={manualProfile.experience_years}
                onChange={updateManualField}
                placeholder="Optional"
              />
            </label>
            <label className="field">
              <span className="field__label">Preferred roles</span>
              <textarea
                name="preferred_roles"
                value={manualProfile.preferred_roles}
                onChange={updateManualField}
                rows={2}
                placeholder="Backend Engineer, Data Engineer"
              />
              <span className="field__hint">Separate roles with commas.</span>
            </label>
          </div>
          {manualError && <p className="form-notice form-notice--error" role="alert">{manualError}</p>}
          {manualNotice && <p className="form-notice" role="status">{manualNotice}</p>}
          <button
            className="button button--primary"
            type="submit"
            disabled={manualLoading || manualSaving || !candidate}
          >
            {manualLoading ? 'Loading profile…' : manualSaving ? 'Saving profile…' : 'Save manual profile'}
            <Icon name="check" size={16} />
          </button>
        </form>
        {activeResume && (
          <section className="resume-review-stack">
            <div className="surface-card resume-status-card">
              <div>
                <p className="eyebrow">EXTRACTION STATUS</p>
                <h3>{activeResume.original_filename}</h3>
                <p>{activeResume.message}</p>
                {activeResume.extraction_status === 'failed' && (
                  <div className="resume-extraction-error" role="alert">
                    <strong>
                      {activeResume.retryable ? 'Retryable failure' : 'Permanent failure'}
                    </strong>
                    <p>{activeResume.diagnostic || 'Resume extraction could not be completed.'}</p>
                    <small>
                      {activeResume.failure_category || activeResume.extraction_error || 'unknown'}
                      {activeResume.http_status ? ` · HTTP ${activeResume.http_status}` : ''}
                      {` · ${activeResume.attempts} attempt(s)`}
                    </small>
                  </div>
                )}
              </div>
              {activeResume.extraction_status === 'failed' && activeResume.retryable && (
                <button className="button button--quiet" type="button" onClick={handleRetry} disabled={uploading}>
                  Retry extraction
                </button>
              )}
            </div>

            {report && (
              <div className="surface-card resume-validation">
                <strong>Evidence check</strong>
                <span>
                  {report.supported_claim_count} of {report.claim_count} extracted claims have a source snippet found in the PDF.
                </span>
                {report.unsupported_claim_count > 0 && (
                  <p role="alert">
                    {report.unsupported_claim_count} claim(s) need review. Resume-sourced claims without matching evidence cannot be confirmed.
                  </p>
                )}
              </div>
            )}

            {displayFacts && (
              <div className="surface-card resume-facts">
                <p className="eyebrow">
                  {activeResume.is_confirmed
                    ? 'CANDIDATE-CONFIRMED PROFILE'
                    : 'AUTOMATICALLY EXTRACTED · NOT YET CONFIRMED'}
                </p>
                <p className="resume-facts__note">
                  Each fact is labeled as resume-extracted or manually added.
                </p>
                <Section title="Candidate details">
                  {[
                    ['Name', displayFacts.full_name],
                    ['Email', displayFacts.email],
                    ['Phone', displayFacts.phone],
                    ['Experience', displayFacts.total_experience_years],
                  ].map(([label, fact]) => {
                    const value = valueText(fact)
                    return (
                      <article className="resume-fact" key={label}>
                        <strong>{label}: {value || 'Not detected'}</strong>
                        <small>{value ? sourceLabel(fact?.source) : 'Add during review if applicable'}</small>
                        <EvidenceSnippets items={fact?.evidence} />
                      </article>
                    )
                  })}
                </Section>
                <Section title="Skills">
                  {displayFacts.skills.length
                    ? <ul className="resume-skill-list">
                      {displayFacts.skills.map((skill) => (
                        <li className="resume-skill-item" key={normalizedText(skill.name)}>
                          <strong>{skill.name}</strong>
                          {skill.category && <small>{skill.category.replaceAll('_', ' ')}</small>}
                          <small className="resume-fact__source">{sourceLabel(skill.source)}</small>
                          <EvidenceSnippets items={skill.evidence} />
                        </li>
                      ))}
                    </ul>
                    : <p>No skills were extracted.</p>}
                </Section>
                <Section title="Education">
                  {displayFacts.education.length
                    ? displayFacts.education.map((item, index) => {
                      const degree = valueText(item.degree)
                      const field = valueText(item.field_of_study)
                      const institution = valueText(item.institution)
                      const dates = [valueText(item.start_date), valueText(item.end_date)].filter(Boolean).join(' – ')
                      return (
                      <article className="resume-fact" key={`${institution}-${index}`}>
                        <strong>{[degree, field].filter(Boolean).join(' · ') || 'Education entry'}</strong>
                        {institution && <span>{institution}</span>}
                        {dates && <small>{dates}</small>}
                        <small className="resume-fact__source">{sourceLabel(item.source)}</small>
                        <EvidenceSnippets items={item.evidence} omitText={[degree, field, institution].filter(Boolean).join(' ')} />
                      </article>
                    )})
                    : <p>No education details were extracted.</p>}
                </Section>
                <Section title="Work experience & internships">
                  {displayFacts.work_experience.length
                    ? displayFacts.work_experience.map((item, index) => {
                      const title = valueText(item.title)
                      const company = valueText(item.company)
                      const description = valueText(item.description)
                      const dates = [valueText(item.start_date), valueText(item.end_date)].filter(Boolean).join(' – ')
                      return (
                      <article className="resume-fact" key={`${title}-${company}-${index}`}>
                        <strong>{title}{company ? ` · ${company}` : ''}</strong>
                        <small>{item.experience_type}{dates ? ` · ${dates}` : ''}</small>
                        <small className="resume-fact__source">{sourceLabel(item.source)}</small>
                        {description && <p>{description}</p>}
                        <TechnologyChips items={item.technologies} />
                        <EvidenceSnippets items={item.evidence} omitText={description} />
                      </article>
                    )})
                    : <p>No work experience or internships were extracted.</p>}
                </Section>
                <Section title="Projects">
                  {displayFacts.projects.length
                    ? displayFacts.projects.map((item, index) => {
                      const name = valueText(item.name)
                      const description = valueText(item.description)
                      return (
                      <article className="resume-fact" key={`${name}-${index}`}>
                        <strong>{name || 'Project'}</strong>
                        <small className="resume-fact__source">{sourceLabel(item.source)}</small>
                        {description && <p>{description}</p>}
                        <TechnologyChips items={item.technologies} />
                        <EvidenceSnippets items={item.evidence} omitText={description} />
                      </article>
                    )})
                    : <p>No projects were extracted.</p>}
                </Section>
                <Section title="Certifications & achievements">
                  {displayFacts.certifications.map((item, index) => {
                    const name = valueText(item.name)
                    const issuer = valueText(item.issuer)
                    const date = valueText(item.date)
                    return (
                    <article className="resume-fact" key={`cert-${name}-${index}`}>
                      <strong>{name || 'Certification'}</strong>
                      {(issuer || date) && <small>{[issuer, date].filter(Boolean).join(' · ')}</small>}
                      <small className="resume-fact__source">{sourceLabel(item.source)}</small>
                      <EvidenceSnippets items={item.evidence} omitText={name} />
                    </article>
                  )})}
                  {displayFacts.achievements.map((item, index) => {
                    const title = valueText(item.title)
                    const description = valueText(item.description)
                    return (
                    <article className="resume-fact" key={`achievement-${title}-${index}`}>
                      <strong>{title || 'Achievement'}</strong>
                      <small className="resume-fact__source">{sourceLabel(item.source)}</small>
                      {description && <p>{description}</p>}
                      <EvidenceSnippets items={item.evidence} omitText={description} />
                    </article>
                  )})}
                  {!displayFacts.certifications.length && !displayFacts.achievements.length
                    && <p>No certifications or achievements were extracted.</p>}
                </Section>
              </div>
            )}

            {activeResume.extraction_status === 'needs_review' && (
              <form className="surface-card resume-review-form" onSubmit={handleConfirm}>
                <p className="eyebrow">CANDIDATE REVIEW</p>
                <h3>Review and confirm the candidate profile</h3>
                <p>Confirm the displayed facts as-is, or open the advanced editor to make structured changes.</p>
                <details className="resume-advanced-editor">
                  <summary>Advanced profile editor (JSON)</summary>
                  <p>
                    Keep supported resume facts marked <code>&quot;source&quot;: &quot;resume&quot;</code>
                    with their verbatim evidence. Mark facts you add as manual.
                  </p>
                  <label className="field">
                    <span className="field__label">Candidate-confirmed profile JSON</span>
                    <textarea
                      className="resume-json-editor"
                      value={reviewJson}
                      onChange={(event) => setReviewJson(event.target.value)}
                      rows={20}
                      spellCheck="false"
                    />
                  </label>
                </details>
                <button className="button button--primary" type="submit" disabled={saving}>
                  {saving ? 'Saving confirmation…' : 'Confirm profile'}
                  <Icon name="check" size={16} />
                </button>
              </form>
            )}
          </section>
        )}
      </section>
      <aside className="side-note-card side-note-card--resume">
        <span className="side-note-card__icon"><Icon name="check" size={18} /></span>
        <p className="eyebrow">A NOTE ON PRIVACY</p>
        <h3>Private local storage.</h3>
        <p>
          Files and extracted text stay in local backend storage and are parsed
          with deterministic rules. OCR is not supported; this local prototype
          does not include sign-in or user-level access control.
        </p>
      </aside>
    </div>
  )
}
