import Header from '../Header/Header.jsx'
import Sidebar from '../Sidebar/Sidebar.jsx'

const pageTitles = {
  chat: 'Your career, in conversation',
  picks: 'A better next move',
  tracker: 'Keep every opportunity close',
  resumes: 'Your experience, in one place',
  search: 'What are you looking for?',
  'job-detail': 'Inside the opportunity',
}

export default function Layout({ activePage, onNavigate, children }) {
  return (
    <div className="app-shell">
      <Sidebar
        activePage={activePage === 'job-detail' ? 'picks' : activePage}
        onNavigate={onNavigate}
      />
      <div className="workspace">
        <Header title={pageTitles[activePage]} />
        <main className="page-content">{children}</main>
      </div>
    </div>
  )
}
