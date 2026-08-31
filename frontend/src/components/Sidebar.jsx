import { PlanIcon, TripsIcon, JournalIcon } from '../icons.jsx'
import { USER_ID } from '../api.js'

const NAV_ITEMS = [
  { id: 'plan', label: 'ORCA Plan', sub: 'Planning & bookings', Icon: PlanIcon },
  { id: 'tournaments', label: 'Tournaments', sub: 'Flights & hotels', Icon: TripsIcon },
  { id: 'journal', label: 'Journal', sub: 'Daily & match logs', Icon: JournalIcon },
]

export default function Sidebar({ view, onNavigate }) {
  return (
    <aside className="sidebar">
      <button type="button" className="brand" onClick={() => onNavigate('home')}>
        <img className="brand-logo" src="/orcalogo.jpeg" alt="ORCA" />
        <span className="brand-word">ORCA</span>
      </button>

      <nav className="nav">
        {NAV_ITEMS.map(({ id, label, sub, Icon }) => (
          <button
            key={id}
            type="button"
            className={`nav-item${view === id ? ' active' : ''}`}
            onClick={() => onNavigate(id)}
          >
            <span className="nav-item-icon">
              <Icon />
            </span>
            <span className="nav-item-text">
              <span className="nav-item-label">{label}</span>
              <span className="nav-item-sub">{sub}</span>
            </span>
          </button>
        ))}
      </nav>

      <div className="sidebar-player">
        <div className="player-avatar">{USER_ID.slice(0, 2).toUpperCase()}</div>
        <div className="player-id">{USER_ID}</div>
      </div>
    </aside>
  )
}
