import Icon from '../common/Icon.jsx'

const items = [
  { id: 'chat', label: 'Chat', icon: 'chat' },
  { id: 'picks', label: 'Picks', icon: 'spark' },
  { id: 'tracker', label: 'Tracker', icon: 'tracker' },
  { id: 'resumes', label: 'Resumes', icon: 'resume' },
  { id: 'search', label: 'Your Search', icon: 'search' },
]

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="sidebar">
      <a
        className="brand"
        href="#home"
        aria-label="Northstar home"
        onClick={(event) => {
          event.preventDefault()
          onNavigate('chat')
        }}
      >
        <span className="brand__mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span className="brand__name">northstar</span>
      </a>

      <div className="sidebar__section-label">YOUR WORKSPACE</div>
      <nav className="sidebar__nav" aria-label="Main navigation">
        {items.map((item) => (
          <button
            className={`nav-item${activePage === item.id ? ' is-active' : ''}`}
            key={item.id}
            type="button"
            aria-label={item.label}
            aria-current={activePage === item.id ? 'page' : undefined}
            title={item.label}
            onClick={() => onNavigate(item.id)}
          >
            <Icon name={item.icon} size={18} />
            <span>{item.label}</span>
            {item.id === 'picks' && <span className="nav-item__dot" aria-hidden="true" />}
          </button>
        ))}
      </nav>

      <div className="sidebar__bottom">
        <div className="sidebar-note">
          <span className="sidebar-note__spark"><Icon name="spark" size={16} /></span>
          <p>Make your next move<br />a little more intentional.</p>
        </div>
        <div className="sidebar-profile">
          <span className="avatar avatar--small">SP</span>
          <span className="sidebar-profile__copy">
            <strong>Sample profile</strong>
            <span>Preview candidate</span>
          </span>
          <span className="profile-presence" aria-label="Workspace ready" />
        </div>
      </div>
    </aside>
  )
}
