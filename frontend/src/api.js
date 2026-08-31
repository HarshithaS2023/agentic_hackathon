// Demo player identity. No auth yet — hardcoded stand-in until real sign-in.
export const USER_ID = 'demo-player'

async function api(path, opts) {
  const res = await fetch(path, opts)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

function postJSON(path, body) {
  return api(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

// Optional endpoints the backend may not implement yet — resolve to a safe
// empty shape instead of throwing so the UI still renders.
async function apiSoft(path, fallback) {
  try {
    return await api(path)
  } catch {
    return fallback
  }
}

// ---------------- Trips: tournaments / flights / hotels ----------------

export function getTournaments() {
  return api('/api/dashboard/tournaments')
}

export function getFlights() {
  return apiSoft('/api/dashboard/flights', { flights: [] })
}

export function getHotels() {
  return apiSoft('/api/dashboard/hotels', { hotels: [] })
}

// ORCA Search — the orchestrator's discovery step. `kind` is one of
// 'tournaments' | 'flights' | 'hotels'. Only the tournaments endpoint exists
// today; kind is passed through for when flights/hotels search lands.
export function orcaSearch({ kind, location, level }) {
  return postJSON('/api/dashboard/search-tournaments', {
    user_id: USER_ID,
    kind,
    location,
    level,
  })
}

// ---------------- Journal ----------------

export function getJournal() {
  return api(`/api/dashboard/journal?user_id=${encodeURIComponent(USER_ID)}`)
}

export function createJournalEntry({
  logType,
  logTitle,
  energyLevel,
  hydrationStatus,
  sorenessLocation,
  performanceNote,
}) {
  const soreness = (sorenessLocation || '').trim()
  return postJSON('/api/dashboard/journal', {
    user_id: USER_ID,
    log_type: logType,
    log_title: (logTitle || '').trim() || null,
    energy_level: energyLevel,
    hydration_status: hydrationStatus,
    soreness_present: soreness.length > 0,
    soreness_location: soreness || null,
    soreness_severity: null,
    performance_note: (performanceNote || '').trim(),
  })
}

// ---------------- ORCA Plan (chat + booking confirmations) ----------------

export function sendMessage(message) {
  return postJSON('/api/dashboard/message', { user_id: USER_ID, message })
}

export function getBookings() {
  return apiSoft('/api/dashboard/bookings', { bookings: [] })
}
