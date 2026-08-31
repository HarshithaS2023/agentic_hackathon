import { useEffect, useState } from 'react'
import { SearchIcon } from '../icons.jsx'
import { orcaSearch } from '../api.js'

const KINDS = [
  { id: 'tournaments', label: 'Tournaments' },
  { id: 'flights', label: 'Flights' },
  { id: 'hotels', label: 'Hotels' },
]

const FIELDS = {
  tournaments: { a: ['Location', 'San Diego, CA'], b: ['Level', 'Futures'] },
  flights: { a: ['Destination', 'Tenerife (TFS)'], b: ['Departing from', 'San Diego (SAN)'] },
  hotels: { a: ['Location', 'Near the venue'], b: ['Dates', 'Mar 3–9'] },
}

const PHRASES = {
  tournaments: [
    'Searching usta.com…',
    'Checking regional tennis associations…',
    'Cross-referencing tournament dates…',
    'Reading tournament listings…',
  ],
  flights: [
    'Querying airline availability…',
    'Comparing routes and layovers…',
    'Scanning fare calendars…',
    'Ranking by price and timing…',
  ],
  hotels: [
    'Scanning nearby stays…',
    'Filtering by distance to the venue…',
    'Checking rates and availability…',
    'Reading recent guest reviews…',
  ],
}

function Thinking({ kind }) {
  const list = PHRASES[kind]
  const [phrase, setPhrase] = useState(list[0])
  useEffect(() => {
    let i = 0
    setPhrase(list[0])
    const id = setInterval(() => {
      i = (i + 1) % list.length
      setPhrase(list[i])
    }, 1400)
    return () => clearInterval(id)
  }, [list])

  return (
    <div className="orca-thinking">
      <div className="orca-wave">
        <span />
        <span />
        <span />
        <span />
        <span />
      </div>
      <div className="thinking-text">{phrase}</div>
    </div>
  )
}

export default function OrcaSearch({ onReloadTrips }) {
  const [kind, setKind] = useState('tournaments')
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const fields = FIELDS[kind]

  async function run(e) {
    e.preventDefault()
    if (!a.trim() || loading) return
    setLoading(true)
    setResult(null)
    try {
      const data = await orcaSearch({ kind, location: a.trim(), level: b.trim() })
      const rows = data.results || data.tournaments || []
      setResult({
        summary: `Found ${rows.length} ${rows.length === 1 ? 'match' : 'matches'}${data.summary ? ` — ${data.summary}` : ''}`,
        queries: data.search_queries_used || [],
        rows,
      })
      if (kind === 'tournaments') await onReloadTrips()
    } catch {
      setResult({ summary: 'Search failed — try again.', queries: [], rows: [] })
    } finally {
      setLoading(false)
    }
  }

  return (
    <aside className="orca">
      <div className="orca-head">
        <span className="chip-icon">
          <SearchIcon />
        </span>
        <div className="orca-title">ORCA Search</div>
      </div>
      <p className="orca-intro">
        The orchestrator&apos;s discovery step — it looks up {kind} and shows its work as it goes.
      </p>

      <div className="orca-kinds">
        {KINDS.map((k) => (
          <button
            key={k.id}
            type="button"
            className={`orca-kind${kind === k.id ? ' active' : ''}`}
            onClick={() => {
              setKind(k.id)
              setResult(null)
            }}
          >
            {k.label}
          </button>
        ))}
      </div>

      <form onSubmit={run}>
        <div className="field">
          <label>{fields.a[0]}</label>
          <input type="text" placeholder={fields.a[1]} value={a} onChange={(e) => setA(e.target.value)} />
        </div>
        <div className="field">
          <label>{fields.b[0]}</label>
          <input type="text" placeholder={fields.b[1]} value={b} onChange={(e) => setB(e.target.value)} />
        </div>
        <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
          {loading ? 'Searching…' : `Search ${KINDS.find((k) => k.id === kind).label.toLowerCase()}`}
        </button>
      </form>

      {loading && <Thinking kind={kind} />}

      {!loading && result && (
        <div className="orca-result">
          <strong>{result.summary}</strong>
          {result.queries.length > 0 && <div className="orca-queries">Searched: {result.queries.join(', ')}</div>}
          {result.rows.map((r, i) => (
            <div key={i} className="orca-row">
              <span className="orca-row-date mono">{r.date || '—'}</span>
              <span className="orca-row-body">
                <span className="orca-row-name">{r.name || r.title || 'Result'}</span>
                <span className="orca-row-meta">
                  {[r.level, r.location, r.price].filter(Boolean).join(' · ')}
                </span>
              </span>
              {r.source_url && (
                <a className="orca-row-link" href={r.source_url} target="_blank" rel="noreferrer">
                  Source
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </aside>
  )
}
