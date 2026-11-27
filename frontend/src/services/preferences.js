const STORAGE_KEY = 'northstar.search-preferences'

export const defaultPreferences = {
  categories: '',
  roles: '',
  skills: '',
  locations: '',
  jobTypes: [],
}

export function readPreferences() {
  const value = window.localStorage.getItem(STORAGE_KEY)
  if (!value) return null

  const parsed = JSON.parse(value)
  if (
    !parsed ||
    typeof parsed !== 'object' ||
    typeof parsed.categories !== 'string' ||
    typeof parsed.roles !== 'string' ||
    typeof parsed.skills !== 'string' ||
    typeof parsed.locations !== 'string' ||
    !Array.isArray(parsed.jobTypes)
  ) {
    throw new Error('Saved preferences are not in the expected format.')
  }

  return {
    categories: parsed.categories,
    roles: parsed.roles,
    skills: parsed.skills,
    locations: parsed.locations,
    jobTypes: parsed.jobTypes.filter((value) => typeof value === 'string'),
  }
}

export function writePreferences(preferences) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))
}
