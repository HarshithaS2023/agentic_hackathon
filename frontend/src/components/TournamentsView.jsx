import { TrophyIcon, PlaneIcon, BedIcon } from '../icons.jsx'

function ListCard({ tone, Icon, eyebrow, title, sub, rows, render, emptyText }) {
  return (
    <div className="card">
      <div className="card-head">
        <span className={`chip-icon chip-${tone}`}>
          <Icon />
        </span>
        <div>
          <div className="eyebrow">{eyebrow}</div>
          <div className="card-title">{title}</div>
          <div className="card-sub">{sub}</div>
        </div>
      </div>
      {rows.length === 0 ? <div className="empty-state">{emptyText}</div> : rows.map(render)}
    </div>
  )
}

export default function TournamentsView({ tournaments, flights, hotels }) {
  return (
    <>
      <ListCard
        tone="navy"
        Icon={TrophyIcon}
        eyebrow="Trips"
        title="Tournaments"
        sub="Events ORCA has found or you've added"
        rows={tournaments}
        emptyText="No tournaments yet. Use ORCA Search on the home screen."
        render={(t, i) => (
          <div key={t.id || `${t.name}-${i}`} className="trip-row">
            <span className="trip-date mono">{t.date || '—'}</span>
            <span className="trip-body">
              <span className="trip-name">{t.name || 'Untitled'}</span>
              <span className="trip-meta">{[t.level, t.location].filter(Boolean).join(' · ')}</span>
            </span>
            {t.source_url && (
              <a className="trip-link" href={t.source_url} target="_blank" rel="noreferrer">
                Source
              </a>
            )}
          </div>
        )}
      />

      <ListCard
        tone="blue"
        Icon={PlaneIcon}
        eyebrow="Trips"
        title="Flights"
        sub="Booked or shortlisted by ORCA"
        rows={flights}
        emptyText="No flights yet. Ask ORCA Plan to find flights for a tournament week."
        render={(f, i) => (
          <div key={f.id || i} className="trip-row">
            <span className="trip-date mono">{f.date || '—'}</span>
            <span className="trip-body">
              <span className="trip-name">
                {f.origin || f.from} → {f.destination || f.to}
              </span>
              <span className="trip-meta">
                {[f.airline, f.depart_time, f.price && `$${f.price}`].filter(Boolean).join(' · ')}
              </span>
            </span>
            {f.source_url && (
              <a className="trip-link" href={f.source_url} target="_blank" rel="noreferrer">
                Details
              </a>
            )}
          </div>
        )}
      />

      <ListCard
        tone="peach"
        Icon={BedIcon}
        eyebrow="Trips"
        title="Hotels"
        sub="Stays near your venues"
        rows={hotels}
        emptyText="No hotels yet. Ask ORCA Plan to find a stay near the venue."
        render={(h, i) => (
          <div key={h.id || i} className="trip-row">
            <span className="trip-date mono">{h.check_in || h.date || '—'}</span>
            <span className="trip-body">
              <span className="trip-name">{h.name || 'Hotel'}</span>
              <span className="trip-meta">
                {[h.location, h.nights && `${h.nights} nights`, h.price && `$${h.price}/night`]
                  .filter(Boolean)
                  .join(' · ')}
              </span>
            </span>
            {h.source_url && (
              <a className="trip-link" href={h.source_url} target="_blank" rel="noreferrer">
                Details
              </a>
            )}
          </div>
        )}
      />
    </>
  )
}
