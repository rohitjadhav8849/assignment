import { useState } from 'react'
import Layout from './components/Layout/Layout.jsx'
import Chat from './pages/Chat.jsx'
import Picks from './pages/Picks.jsx'
import Resumes from './pages/Resumes.jsx'
import Tracker from './pages/Tracker.jsx'
import YourSearch from './pages/YourSearch.jsx'
import JobDetails from './pages/JobDetails.jsx'

export default function App() {
  const [activePage, setActivePage] = useState('chat')
  const [selectedJobId, setSelectedJobId] = useState(null)

  function navigate(page) {
    setActivePage(page)
    if (page !== 'job-detail') setSelectedJobId(null)
  }

  function openJob(jobId) {
    setSelectedJobId(jobId)
    setActivePage('job-detail')
  }

  let page
  if (activePage === 'job-detail' && selectedJobId) {
    page = <JobDetails jobId={selectedJobId} onOpenJob={openJob} onNavigate={navigate} />
  } else if (activePage === 'picks') {
    page = <Picks onNavigate={navigate} onOpenJob={openJob} />
  } else if (activePage === 'tracker') {
    page = <Tracker />
  } else if (activePage === 'resumes') {
    page = <Resumes />
  } else if (activePage === 'search') {
    page = <YourSearch />
  } else {
    page = <Chat onNavigate={navigate} />
  }

  return (
    <Layout activePage={activePage} onNavigate={navigate}>{page}</Layout>
  )
}
