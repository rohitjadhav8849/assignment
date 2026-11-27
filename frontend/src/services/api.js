const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function request(path, options = {}) {
  let response
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        Accept: 'application/json',
        ...(options.body && !isFormData ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
      },
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('Could not reach the API. Check that the backend is running.')
  }

  let payload
  try {
    payload = await response.json()
  } catch {
    throw new Error(`The API returned an unreadable response (${response.status}).`)
  }

  if (!response.ok) {
    const detail = typeof payload.detail === 'string' ? payload.detail : null
    throw new Error(detail || `The API request failed (${response.status}).`)
  }
  return payload
}

export function getCandidateProfile(options = {}) {
  return request('/api/candidate', options)
}

export function saveCandidateProfile(profile, options = {}) {
  return request('/api/candidate', {
    ...options,
    method: 'PUT',
    body: JSON.stringify(profile),
  })
}

export function getJobPicks(options = {}) {
  return request('/api/jobs/picks?limit=50', options)
}

const retrievalPaths = {
  bm25: '/api/jobs/retrieval/bm25',
  semantic: '/api/jobs/retrieval/semantic',
  hybrid: '/api/jobs/retrieval/hybrid',
}

export function getJobRetrieval(mode, options = {}) {
  const path = retrievalPaths[mode]
  if (!path) throw new Error(`Unknown job retrieval mode: ${mode}`)
  return request(`${path}?top_k=50`, options)
}

export function getJobDetails(jobId, options = {}) {
  return request(`/api/jobs/${encodeURIComponent(jobId)}`, options)
}

export function getCandidatePreferences(options = {}) {
  return request('/api/preferences', options)
}

export function saveCandidatePreferences(preferences, options = {}) {
  return request('/api/preferences', {
    ...options,
    method: 'PUT',
    body: JSON.stringify(preferences),
  })
}

export function getResumes(options = {}) {
  return request('/api/resumes', options)
}

export function getResume(resumeId, options = {}) {
  return request(`/api/resumes/${encodeURIComponent(resumeId)}`, options)
}

export function uploadResume(file, options = {}) {
  const formData = new FormData()
  formData.append('file', file)
  return request('/api/resumes', {
    ...options,
    method: 'POST',
    body: formData,
  })
}

export function retryResumeExtraction(resumeId, options = {}) {
  return request(`/api/resumes/${encodeURIComponent(resumeId)}/extract`, {
    ...options,
    method: 'POST',
  })
}

export function confirmResumeProfile(resumeId, profile, options = {}) {
  return request(`/api/resumes/${encodeURIComponent(resumeId)}/confirm`, {
    ...options,
    method: 'PUT',
    body: JSON.stringify(profile),
  })
}
