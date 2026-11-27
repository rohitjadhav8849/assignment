import { useEffect, useState } from 'react'
import Icon from '../components/common/Icon.jsx'
import { getCandidateProfile } from '../services/api.js'

const welcomeMessage = {
  id: 'welcome',
  role: 'assistant',
  text: 'Hi there. I’m here to help you think through your next career move. Tell me what you’re looking for, or start by adding a few preferences.',
}

export default function Chat({ onNavigate }) {
  const [messages, setMessages] = useState([welcomeMessage])
  const [draft, setDraft] = useState('')
  const [profile, setProfile] = useState(null)
  const [profileError, setProfileError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    getCandidateProfile({ signal: controller.signal })
      .then(setProfile)
      .catch((error) => {
        if (error.name !== 'AbortError') setProfileError(error.message)
      })
    return () => controller.abort()
  }, [])

  function sendMessage(event) {
    event.preventDefault()
    const text = draft.trim()
    if (!text) return

    setMessages((current) => [
      ...current,
      { id: `${Date.now()}-user`, role: 'user', text },
      {
        id: `${Date.now()}-preview`,
        role: 'assistant',
        text: 'AI chat responses are not connected in this prototype.',
      },
    ])
    setDraft('')
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  const completedProfileFields = profile
    ? [
      profile.skills.length > 0,
      profile.experience_years !== null,
      profile.preferred_roles.length > 0,
      profile.categories.length > 0,
      profile.locations.length > 0,
      profile.work_modes.length > 0,
      profile.employment_types.length > 0,
    ].filter(Boolean).length
    : 0
  const profileProgress = Math.round((completedProfileFields / 7) * 100)

  return (
    <div className="chat-layout">
      <section className="chat-panel" aria-label="Career conversation">
        <div className="chat-panel__intro">
          <span className="chat-panel__orb"><Icon name="spark" size={20} /></span>
          <div>
            <p className="eyebrow">YOUR CAREER COMPANION</p>
            <p className="chat-panel__subhead">A space to get clear on what comes next.</p>
          </div>
        </div>

        <div className="chat-thread" aria-live="polite">
          {messages.map((message) => (
            <article
              className={`message message--${message.role}`}
              key={message.id}
            >
              {message.role === 'assistant' && (
                <span className="message__avatar" aria-hidden="true">n</span>
              )}
              <div className="message__body">
                <span className="message__author">
                  {message.role === 'assistant' ? 'Northstar' : 'You'}
                </span>
                <p>{message.text}</p>
              </div>
            </article>
          ))}
        </div>

        <form className="chat-composer" onSubmit={sendMessage}>
          <label className="sr-only" htmlFor="chat-message">Message Northstar</label>
          <textarea
            id="chat-message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Tell me what kind of work feels right..."
            rows={1}
          />
          <div className="chat-composer__footer">
            <span>Prototype preview · AI replies are not connected</span>
            <button
              className="icon-button icon-button--send"
              type="submit"
              aria-label="Send message"
              disabled={!draft.trim()}
            >
              <Icon name="send" size={17} />
            </button>
          </div>
        </form>
      </section>

      <aside className="context-panel">
        <div className="context-panel__heading">
          <span className="context-icon"><Icon name="spark" size={17} /></span>
          <div>
            <p className="eyebrow">YOUR CONTEXT</p>
            <h2>A little about you</h2>
          </div>
        </div>
        <p className="context-panel__copy">
          Your preferences will help shape a more personal job search.
        </p>
        <div className="context-progress">
          <div className="context-progress__top">
            <span>Search preferences</span>
            <span className="context-progress__status">
              {profileError ? 'Unavailable' : profile ? `${profileProgress}% complete` : 'Loading'}
            </span>
          </div>
          <div className="context-progress__track">
            <span style={{ width: `${profileProgress}%` }} />
          </div>
          <p>
            {profileError
              ? profileError
              : profile?.is_configured
                ? 'Your saved candidate profile is ready to shape job recommendations.'
                : 'Share the roles, skills and places that matter to you.'}
          </p>
        </div>
        <button className="text-link" type="button" onClick={() => onNavigate('search')}>
          {profile?.is_configured ? 'Update your preferences' : 'Add your preferences'}
          <Icon name="arrow" size={15} />
        </button>
        <div className="context-panel__divider" />
        <p className="context-panel__footnote">
          Your workspace is just getting started. You can update your search any time.
        </p>
      </aside>
    </div>
  )
}
