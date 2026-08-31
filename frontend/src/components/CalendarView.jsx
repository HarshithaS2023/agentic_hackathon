import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from '../icons.jsx'

// Monday-first so Saturday and Sunday sit next to each other as one block.
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const TYPE_LABEL = { tournament: 'Tournament', flight: 'Flight', hotel: 'Hotel' }

const isoOf = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const startOfMonth = (d) => new Date(d.getFullYear(), d.getMonth(), 1)
const todayIso = isoOf(new Date())

function EventChip({ ev }) {
  const cls = `cal-ev cal-ev-${ev.type}`
  return ev.url ? (
    <a className={cls} href={ev.url} target="_blank" rel="noreferrer" title={ev.title}>
      {ev.title}
    </a>
  ) : (
    <span className={cls} title={ev.title}>
      {ev.title}
    </span>
  )
}

export default function CalendarView({ events }) {
  const [cursor, setCursor] = useState(startOfMonth(new Date()))

  const { byIso, undated, upcoming } = useMemo(() => {
    const map = new Map()
    const noDate = []
    for (const ev of events) {
      if (!ev.iso) {
        noDate.push(ev)
        continue
      }
      if (!map.has(ev.iso)) map.set(ev.iso, [])
      map.get(ev.iso).push(ev)
    }
    const up = events
      .filter((e) => e.iso && e.iso >= todayIso)
      .sort((a, b) => a.iso.localeCompare(b.iso))
      .slice(0, 6)
    return { byIso: map, undated: noDate, upcoming: up }
  }, [events])

  const year = cursor.getFullYear()
  const month = cursor.getMonth()
  // Monday-based offset: Mon=0 … Sun=6
  const firstWeekday = (new Date(year, month, 1).getDay() + 6) % 7
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const weeks = Math.ceil((firstWeekday + daysInMonth) / 7)
  const gridStart = new Date(year, month, 1 - firstWeekday)

  const cells = Array.from({ length: weeks * 7 }, (_, i) => {
    const d = new Date(gridStart)
    d.setDate(gridStart.getDate() + i)
    return d
  })

  const monthLabel = cursor.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  const step = (delta) => setCursor(new Date(year, month + delta, 1))

  return (
    <div className="card cal-card">
      <div className="card-head cal-head">
        <div>
          <div className="eyebrow">Schedule</div>
          <div className="card-title">{monthLabel}</div>
          <div className="card-sub">Tournaments, flights and hotels in one place</div>
        </div>
        <div className="cal-nav">
          <button type="button" className="cal-btn" onClick={() => step(-1)} aria-label="Previous month">
            <ChevronLeft />
          </button>
          <button type="button" className="cal-today-btn" onClick={() => setCursor(startOfMonth(new Date()))}>
            Today
          </button>
          <button type="button" className="cal-btn" onClick={() => step(1)} aria-label="Next month">
            <ChevronRight />
          </button>
        </div>
      </div>

      <div className="cal-weekrow">
        {WEEKDAYS.map((w, i) => (
          <div key={w} className={`cal-wd${i >= 5 ? ' cal-weekend' : ''}`}>
            {w}
          </div>
        ))}
      </div>

      <div className="cal-grid">
        {cells.map((d) => {
          const iso = isoOf(d)
          const dayEvents = byIso.get(iso) || []
          const weekend = d.getDay() === 0 || d.getDay() === 6
          const out = d.getMonth() !== month
          return (
            <div
              key={iso}
              className={[
                'cal-cell',
                weekend ? 'cal-weekend' : '',
                out ? 'cal-out' : '',
                iso === todayIso ? 'cal-today' : '',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              <div className="cal-daynum">{d.getDate()}</div>
              <div className="cal-events">
                {dayEvents.slice(0, 3).map((ev, i) => (
                  <EventChip key={i} ev={ev} />
                ))}
                {dayEvents.length > 3 && <span className="cal-more">+{dayEvents.length - 3} more</span>}
              </div>
            </div>
          )
        })}
      </div>

      <div className="cal-legend">
        {Object.entries(TYPE_LABEL).map(([k, label]) => (
          <span key={k} className="cal-legend-item">
            <span className={`cal-dot cal-ev-${k}`} />
            {label}
          </span>
        ))}
        <span className="cal-legend-item">
          <span className="cal-dot cal-weekend-dot" />
          Weekend
        </span>
      </div>

      {(upcoming.length > 0 || undated.length > 0) && (
        <div className="cal-upcoming">
          {upcoming.length > 0 && (
            <>
              <div className="eyebrow">Upcoming</div>
              {upcoming.map((ev, i) => (
                <div key={i} className="cal-up-row">
                  <span className="cal-up-date mono">{ev.rawDate}</span>
                  <span className={`cal-dot cal-ev-${ev.type}`} />
                  <span className="cal-up-title">{ev.title}</span>
                  <span className="cal-up-meta">{ev.meta}</span>
                </div>
              ))}
            </>
          )}
          {undated.length > 0 && (
            <>
              <div className="eyebrow" style={{ marginTop: upcoming.length ? 14 : 0 }}>
                Date TBD
              </div>
              {undated.map((ev, i) => (
                <div key={i} className="cal-up-row">
                  <span className="cal-up-date mono">{ev.rawDate || '—'}</span>
                  <span className={`cal-dot cal-ev-${ev.type}`} />
                  <span className="cal-up-title">{ev.title}</span>
                  <span className="cal-up-meta">{ev.meta}</span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}
