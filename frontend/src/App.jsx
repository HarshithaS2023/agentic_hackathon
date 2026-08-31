import { useCallback, useEffect, useMemo, useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import Topbar from './components/Topbar.jsx'
import CalendarView from './components/CalendarView.jsx'
import OrcaSearch from './components/OrcaSearch.jsx'
import PlanView from './components/PlanView.jsx'
import TournamentsView from './components/TournamentsView.jsx'
import JournalView from './components/JournalView.jsx'
import { getTournaments, getFlights, getHotels, getJournal } from './api.js'

const todayIso = new Date().toISOString().slice(0, 10)

// Best-effort parse of a backend date string into YYYY-MM-DD. Returns null
// when the string isn't a recognizable date so the event still shows in the
// "Date TBD" strip rather than vanishing.
function toIso(raw) {
  if (!raw) return null
  const d = new Date(raw)
  if (!Number.isNaN(d.getTime())) return d.toISOString().slice(0, 10)
  const m = String(raw).match(/(\d{4})-(\d{2})-(\d{2})/)
  return m ? `${m[1]}-${m[2]}-${m[3]}` : null
}

export default function App() {
  const [view, setView] = useState('home')
  const [tournaments, setTournaments] = useState([])
  const [flights, setFlights] = useState([])
  const [hotels, setHotels] = useState([])
  const [journalEntries, setJournalEntries] = useState([])

  const reloadTrips = useCallback(async () => {
    const [t, f, h] = await Promise.all([
      getTournaments().catch(() => ({ tournaments: [] })),
      getFlights(),
      getHotels(),
    ])
    setTournaments(t.tournaments || [])
    setFlights(f.flights || [])
    setHotels(h.hotels || [])
  }, [])

  const reloadJournal = useCallback(async () => {
    try {
      const data = await getJournal()
      setJournalEntries(data.entries || [])
    } catch {
      setJournalEntries([])
    }
  }, [])

  useEffect(() => {
    reloadTrips()
    reloadJournal()
  }, [reloadTrips, reloadJournal])

  const events = useMemo(() => {
    const mk = (arr, type, map) =>
      (arr || []).map((x) => {
        const e = map(x)
        return { ...e, type, iso: toIso(e.rawDate) }
      })
    return [
      ...mk(tournaments, 'tournament', (t) => ({
        rawDate: t.date,
        title: t.name || 'Tournament',
        meta: [t.level, t.location].filter(Boolean).join(' · '),
        url: t.source_url,
      })),
      ...mk(flights, 'flight', (f) => ({
        rawDate: f.date || f.depart_date,
        title: `${f.origin || f.from || '?'} → ${f.destination || f.to || '?'}`,
        meta: [f.airline, f.price && `$${f.price}`].filter(Boolean).join(' · '),
        url: f.source_url,
      })),
      ...mk(hotels, 'hotel', (h) => ({
        rawDate: h.check_in || h.date,
        title: h.name || 'Hotel',
        meta: [h.location, h.nights && `${h.nights} nights`].filter(Boolean).join(' · '),
        url: h.source_url,
      })),
    ]
  }, [tournaments, flights, hotels])

  const upcomingCount = events.filter((e) => e.iso && e.iso >= todayIso).length

  const homeLayout = view === 'home'

  return (
    <div className={`shell${homeLayout ? '' : ' shell-2col'}`}>
      <Sidebar view={view} onNavigate={setView} />

      <main className="main">
        <Topbar
          view={view}
          tournamentCount={tournaments.length}
          upcomingCount={upcomingCount}
          journalCount={journalEntries.length}
        />

        {view === 'home' && <CalendarView events={events} />}
        {view === 'plan' && <PlanView />}
        {view === 'tournaments' && (
          <TournamentsView tournaments={tournaments} flights={flights} hotels={hotels} />
        )}
        {view === 'journal' && (
          <JournalView entries={journalEntries} onReloadJournal={reloadJournal} />
        )}
      </main>

      {homeLayout && <OrcaSearch onReloadTrips={reloadTrips} />}
    </div>
  )
}
