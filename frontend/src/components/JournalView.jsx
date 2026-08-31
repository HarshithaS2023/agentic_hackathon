import { useMemo, useState } from 'react'
import { JournalIcon } from '../icons.jsx'
import { createJournalEntry } from '../api.js'

const TODAY_STR = new Date().toISOString().slice(0, 10)

const LOG_TYPES = [
  { id: 'daily', label: 'Daily' },
  { id: 'matchplay', label: 'Match play' },
  { id: 'training', label: 'Training' },
  { id: 'recovery', label: 'Recovery' },
]
const LABEL = Object.fromEntries(LOG_TYPES.map((t) => [t.id, t.label]))

function Entry({ e }) {
  const isToday = e.date === TODAY_STR
  const soreness = e.soreness && e.soreness.present
  return (
    <div className={`timeline-entry${isToday ? ' today' : ''}`}>
      <div className="timeline-date mono">
        {e.date}
        {isToday ? ' · today' : ''}
      </div>
      {e.log_title && <div className="timeline-title">{e.log_title}</div>}
      <div className="timeline-stats">
        <span>Energy {e.energy_level}/5</span>
        <span>Hydration: {e.hydration_status}</span>
        {soreness && (
          <span className="soreness-flag">Soreness: {e.soreness.location || 'unspecified'}</span>
        )}
      </div>
      {e.performance_note && <div className="timeline-note">{e.performance_note}</div>}
    </div>
  )
}

export default function JournalView({ entries, onReloadJournal }) {
  const [logType, setLogType] = useState('daily')
  const [logTitle, setLogTitle] = useState('')
  const [energyLevel, setEnergyLevel] = useState(3)
  const [hydrationStatus, setHydrationStatus] = useState('ok')
  const [sorenessLocation, setSorenessLocation] = useState('')
  const [performanceNote, setPerformanceNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [filter, setFilter] = useState('all')

  const groups = useMemo(() => {
    const g = {}
    for (const e of entries) {
      const k = e.log_type || 'daily'
      ;(g[k] ||= []).push(e)
    }
    return g
  }, [entries])

  const visibleTypes = filter === 'all' ? LOG_TYPES.map((t) => t.id) : [filter]

  async function save(ev) {
    ev.preventDefault()
    if (saving) return
    setSaving(true)
    try {
      await createJournalEntry({
        logType,
        logTitle,
        energyLevel,
        hydrationStatus,
        sorenessLocation,
        performanceNote,
      })
      setLogTitle('')
      setSorenessLocation('')
      setPerformanceNote('')
      await onReloadJournal()
    } catch {
      alert("Couldn't save that log. Try again.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="card">
        <div className="card-head">
          <span className="chip-icon chip-peach">
            <JournalIcon />
          </span>
          <div>
            <div className="eyebrow">Logs</div>
            <div className="card-title">New log</div>
            <div className="card-sub">Daily check-ins, match play, training and recovery — kept just for you.</div>
          </div>
        </div>

        <form onSubmit={save}>
          <div className="seg">
            {LOG_TYPES.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`seg-btn${logType === t.id ? ' active' : ''}`}
                onClick={() => setLogType(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="field">
            <label>{logType === 'matchplay' ? 'Opponent / match' : 'Title (optional)'}</label>
            <input
              type="text"
              placeholder={logType === 'matchplay' ? 'vs. J. Alvarez — R16' : 'e.g. Morning session'}
              value={logTitle}
              onChange={(e) => setLogTitle(e.target.value)}
            />
          </div>

          <div className="row-2">
            <div className="field">
              <label>Energy level</label>
              <div className="range-row">
                <input
                  type="range"
                  min="1"
                  max="5"
                  value={energyLevel}
                  onChange={(e) => setEnergyLevel(Number(e.target.value))}
                />
                <span className="range-value">{energyLevel}</span>
              </div>
            </div>
            <div className="field">
              <label>Hydration</label>
              <select value={hydrationStatus} onChange={(e) => setHydrationStatus(e.target.value)}>
                <option value="low">Low</option>
                <option value="ok">OK</option>
                <option value="good">Good</option>
              </select>
            </div>
          </div>
          <div className="field">
            <label>Soreness / pain (leave blank if none)</label>
            <input
              type="text"
              placeholder="e.g. left calf"
              value={sorenessLocation}
              onChange={(e) => setSorenessLocation(e.target.value)}
            />
          </div>
          <div className="field">
            <label>{logType === 'matchplay' ? 'What worked, what to fix' : 'Notes'}</label>
            <textarea
              placeholder={logType === 'matchplay' ? 'Serve landed well; forehand broke down under pressure…' : 'How did today feel?'}
              value={performanceNote}
              onChange={(e) => setPerformanceNote(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving…' : 'Save log'}
          </button>
        </form>
      </div>

      <div className="card">
        <div className="card-head">
          <span className="chip-icon chip-peach">
            <JournalIcon />
          </span>
          <div>
            <div className="eyebrow">Logs</div>
            <div className="card-title">History</div>
            <div className="card-sub">Organized by type</div>
          </div>
        </div>

        <div className="seg seg-filter">
          <button
            type="button"
            className={`seg-btn${filter === 'all' ? ' active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All
          </button>
          {LOG_TYPES.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`seg-btn${filter === t.id ? ' active' : ''}`}
              onClick={() => setFilter(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {entries.length === 0 && <div className="empty-state">No logs yet.</div>}

        {visibleTypes.map((k) =>
          groups[k] && groups[k].length ? (
            <div key={k} className="journal-group">
              <div className="journal-group-head">{LABEL[k]}</div>
              <div className="timeline">
                {groups[k].map((e, i) => (
                  <Entry key={e.id || `${e.date}-${i}`} e={e} />
                ))}
              </div>
            </div>
          ) : null,
        )}
      </div>
    </>
  )
}
