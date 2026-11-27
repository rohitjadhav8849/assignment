import { useEffect, useState } from 'react'
import Icon from '../components/common/Icon.jsx'
import { getCandidatePreferences, saveCandidatePreferences } from '../services/api.js'
import { readPreferences } from '../services/preferences.js'

const workModeOptions = ['Remote', 'Hybrid', 'On-site']
const employmentTypeOptions = ['Full-time', 'Part-time', 'Contract', 'Internship']

const emptyPreferences = {
  locations: [],
  work_modes: [],
  employment_types: [],
  salary_min: null,
  salary_max: null,
  salary_currency: 'USD',
}

function preferencesToForm(preferences) {
  return {
    ...preferences,
    locations: (preferences.locations || []).join(', '),
    work_modes: preferences.work_modes || [],
    employment_types: preferences.employment_types || [],
    salary_min: preferences.salary_min == null ? '' : String(preferences.salary_min),
    salary_max: preferences.salary_max == null ? '' : String(preferences.salary_max),
    salary_currency: preferences.salary_currency || 'USD',
  }
}

function formToPreferences(form) {
  const salaryMin = form.salary_min === '' ? null : Number(form.salary_min)
  const salaryMax = form.salary_max === '' ? null : Number(form.salary_max)
  return {
    locations: form.locations.split(/[,\n]/).map((value) => value.trim()).filter(Boolean),
    work_modes: form.work_modes,
    employment_types: form.employment_types,
    salary_min: Number.isFinite(salaryMin) ? salaryMin : null,
    salary_max: Number.isFinite(salaryMax) ? salaryMax : null,
    salary_currency: form.salary_currency.trim().toUpperCase() || 'USD',
  }
}

function fromLegacyPreferences(current) {
  if (current.locations.length || current.employment_types.length) return current
  const legacy = readPreferences()
  if (!legacy) return current
  return {
    ...current,
    locations: legacy.locations.split(/[,\n]/).map((value) => value.trim()).filter(Boolean),
    employment_types: legacy.jobTypes,
  }
}

export default function YourSearch() {
  const [form, setForm] = useState(preferencesToForm(emptyPreferences))
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const [noticeType, setNoticeType] = useState('success')

  useEffect(() => {
    const controller = new AbortController()
    getCandidatePreferences({ signal: controller.signal })
      .then((preferences) => {
        try {
          setForm(preferencesToForm(fromLegacyPreferences(preferences)))
        } catch {
          setForm(preferencesToForm(preferences))
          setNotice('Saved browser preferences could not be read. You can enter them manually.')
          setNoticeType('error')
        }
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setNotice(error.message)
          setNoticeType('error')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [])

  function updateField(event) {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
  }

  function togglePreference(field, value) {
    setForm((current) => ({
      ...current,
      [field]: current[field].includes(value)
        ? current[field].filter((item) => item !== value)
        : [...current[field], value],
    }))
  }

  async function savePreferences(event) {
    event.preventDefault()
    setSaving(true)
    setNotice('')
    try {
      const saved = await saveCandidatePreferences(formToPreferences(form))
      setForm(preferencesToForm(saved))
      setNotice('Your search preferences are saved to PostgreSQL.')
      setNoticeType('success')
    } catch (error) {
      setNotice(error.message)
      setNoticeType('error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="search-page">
      <div className="search-intro">
        <span className="search-intro__icon"><Icon name="search" size={21} /></span>
        <div>
          <p className="eyebrow">YOUR SEARCH STARTS WITH YOU</p>
          <h2>Choose where and how you want to work.</h2>
          <p>
            Your skills and work history come from the candidate-confirmed profile
            in Resumes. Set only your job-search preferences here.
          </p>
        </div>
      </div>

      <form className="surface-card preferences-form" onSubmit={savePreferences}>
        <div className="preferences-form__heading">
          <div>
            <h3>Job-search preferences</h3>
            <p>These preferences stay separate from your confirmed resume profile.</p>
          </div>
          <span className="preferences-form__local">
            <span /> {loading ? 'LOADING PREFERENCES' : 'PREFERENCES'}
          </span>
        </div>

        <div className="preferences-fields">
          <label className="field">
            <span className="field__label">Preferred locations</span>
            <textarea
              name="locations"
              value={form.locations}
              onChange={updateField}
              placeholder="e.g. Seattle, Remote, Toronto"
              rows={2}
            />
            <span className="field__hint">Add locations separated by commas.</span>
          </label>
          <label className="field">
            <span className="field__label">Minimum annual salary (optional)</span>
            <input
              className="text-field"
              name="salary_min"
              type="number"
              min="0"
              max="10000000"
              value={form.salary_min}
              onChange={updateField}
              placeholder="e.g. 90000"
            />
          </label>
          <label className="field">
            <span className="field__label">Maximum annual salary (optional)</span>
            <input
              className="text-field"
              name="salary_max"
              type="number"
              min="0"
              max="10000000"
              value={form.salary_max}
              onChange={updateField}
              placeholder="e.g. 150000"
            />
          </label>
          <label className="field">
            <span className="field__label">Salary currency</span>
            <input
              className="text-field"
              name="salary_currency"
              value={form.salary_currency}
              onChange={updateField}
              maxLength={3}
              minLength={3}
              placeholder="USD"
            />
            <span className="field__hint">Three-letter currency code, such as USD or CAD.</span>
          </label>
        </div>

        <fieldset className="job-type-fieldset">
          <legend>Work modes</legend>
          <p className="field__hint">Select every arrangement you would consider.</p>
          <div className="job-type-options">
            {workModeOptions.map((mode) => (
              <label className="check-option" key={mode}>
                <input
                  type="checkbox"
                  checked={form.work_modes.includes(mode)}
                  onChange={() => togglePreference('work_modes', mode)}
                />
                <span className="check-option__box"><Icon name="check" size={13} /></span>
                {mode}
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="job-type-fieldset">
          <legend>Employment types</legend>
          <p className="field__hint">Choose any type you would consider.</p>
          <div className="job-type-options">
            {employmentTypeOptions.map((type) => (
              <label className="check-option" key={type}>
                <input
                  type="checkbox"
                  checked={form.employment_types.includes(type)}
                  onChange={() => togglePreference('employment_types', type)}
                />
                <span className="check-option__box"><Icon name="check" size={13} /></span>
                {type}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="preferences-form__footer">
          <p
            className={`form-notice${noticeType === 'error' ? ' form-notice--error' : ''}`}
            role={noticeType === 'error' ? 'alert' : 'status'}
            aria-live="polite"
          >
            {notice}
          </p>
          <button className="button button--primary" type="submit" disabled={saving || loading}>
            {saving ? 'Saving…' : 'Save preferences'} <Icon name="arrow" size={16} />
          </button>
        </div>
      </form>
    </div>
  )
}
