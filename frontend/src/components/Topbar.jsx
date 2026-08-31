const TODAY = new Date().toLocaleDateString(undefined, {
  weekday: 'long',
  month: 'long',
  day: 'numeric',
})

const TITLES = {
  home: { eyebrow: 'Overview', title: 'Your calendar' },
  plan: { eyebrow: 'Orchestrator', title: 'ORCA Plan' },
  tournaments: { eyebrow: 'Trips', title: 'Tournaments' },
  journal: { eyebrow: 'Logs', title: 'Journal' },
}

function StatChip({ num, label }) {
  return (
    <div className="stat-chip">
      <div className="stat-num">{num}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

export default function Topbar({ view, tournamentCount, upcomingCount, journalCount }) {
  const { eyebrow, title } = TITLES[view] ?? TITLES.home
  return (
    <div className="topbar">
      <div className="topbar-title">
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{TODAY}</p>
      </div>
      <div className="stat-row">
        <StatChip num={tournamentCount} label="Tournaments" />
        <StatChip num={upcomingCount} label="Upcoming" />
        <StatChip num={journalCount} label="Journal logs" />
      </div>
    </div>
  )
}
