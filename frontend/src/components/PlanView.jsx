import { useEffect, useRef, useState } from 'react'
import { SendIcon } from '../icons.jsx'
import { sendMessage, getBookings } from '../api.js'

const SUGGESTED = [
  'Plan my trip to the next tournament',
  'Book flights and a hotel for that week',
  "Confirm my registration",
  "What's my itinerary?",
]

const GREETING = {
  role: 'assistant',
  text:
    "I'm ORCA. Tell me where and when you're playing and I'll line up the tournament, flights and a hotel — then walk you through confirming each booking.",
}

export default function PlanView() {
  const [messages, setMessages] = useState([GREETING])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [bookings, setBookings] = useState([])
  const threadRef = useRef(null)

  useEffect(() => {
    getBookings().then((d) => setBookings(d.bookings || []))
  }, [])

  useEffect(() => {
    const el = threadRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  async function send(text) {
    const message = (text ?? input).trim()
    if (!message || sending) return
    setInput('')
    setSending(true)
    setMessages((m) => [
      ...m,
      { role: 'user', text: message },
      { role: 'assistant', text: '…', pending: true },
    ])
    try {
      const data = await sendMessage(message)
      setMessages((m) => [
        ...m.slice(0, -1),
        { role: 'assistant', text: data.reply || "I didn't catch that — try rephrasing." },
      ])
      getBookings().then((d) => setBookings(d.bookings || []))
    } catch {
      setMessages((m) => [
        ...m.slice(0, -1),
        { role: 'assistant', text: 'Something went wrong reaching ORCA.' },
      ])
    } finally {
      setSending(false)
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="plan-grid">
      <div className="card plan-chat">
        <div className="card-head">
          <div>
            <div className="eyebrow">Planning</div>
            <div className="card-title">Talk to ORCA</div>
            <div className="card-sub">One thread for building and confirming your trip</div>
          </div>
        </div>

        <div className="plan-thread" ref={threadRef}>
          {messages.map((m, i) => (
            <div key={i} className={`chat-msg ${m.role === 'user' ? 'user-msg' : 'assistant-msg'}`}>
              {m.text}
            </div>
          ))}
        </div>

        <div className="assistant-suggested">
          {SUGGESTED.map((s) => (
            <button
              key={s}
              type="button"
              className="suggest-chip"
              onClick={() => {
                setInput(s)
                send(s)
              }}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="assistant-input-row">
          <input
            type="text"
            placeholder="Ask ORCA to plan, adjust or confirm…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <button
            type="button"
            className="send-btn"
            aria-label="Send"
            disabled={sending}
            onClick={() => send()}
          >
            <SendIcon />
          </button>
        </div>
      </div>

      <div className="card plan-bookings">
        <div className="card-head">
          <div>
            <div className="eyebrow">Bookings</div>
            <div className="card-title">Confirmations</div>
            <div className="card-sub">What ORCA has locked in</div>
          </div>
        </div>
        {bookings.length === 0 ? (
          <div className="empty-state">
            No confirmed bookings yet. Ask ORCA to plan a trip and confirm the options it finds.
          </div>
        ) : (
          bookings.map((b, i) => (
            <div key={b.id || i} className="booking-row">
              <span className={`cal-dot cal-ev-${b.type || 'tournament'}`} />
              <div className="booking-body">
                <div className="booking-title">{b.title || b.name}</div>
                <div className="booking-meta">
                  {[b.date, b.location, b.confirmation && `#${b.confirmation}`].filter(Boolean).join(' · ')}
                </div>
              </div>
              <span className={`booking-status booking-${(b.status || 'confirmed').toLowerCase()}`}>
                {b.status || 'Confirmed'}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
