export default function Header({ title }) {
  return (
    <header className="topbar">
      <div className="topbar__title">
        <span className="topbar__workspace">CANDIDATE WORKSPACE</span>
        <h1>{title}</h1>
      </div>
      <div className="topbar__right">
        <span className="preview-pill"><span /> Prototype preview</span>
        <div className="topbar__profile">
          <span className="avatar">SP</span>
          <span className="topbar__profile-name">Sample profile</span>
        </div>
      </div>
    </header>
  )
}
