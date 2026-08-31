// Shared inline SVGs. `currentColor` lets the pastel chip badges tint them.

export function PlanIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <path
        d="M3 4.5C3 3.67 3.67 3 4.5 3h11c.83 0 1.5.67 1.5 1.5v8c0 .83-.67 1.5-1.5 1.5H8l-3.5 3v-3H4.5C3.67 14 3 13.33 3 12.5v-8Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function TripsIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <path
        d="M4 8.5 10 3l6 5.5M5 8v8.5h10V8"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <path d="M8.5 16.5v-4h3v4" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  )
}

export function JournalIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <rect x="3.5" y="2.5" width="13" height="15" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <line x1="6.5" y1="6.5" x2="13.5" y2="6.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="6.5" y1="10" x2="13.5" y2="10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="6.5" y1="13.5" x2="10.5" y2="13.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

export function CalendarIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <rect x="3" y="4" width="14" height="13" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <line x1="3" y1="8" x2="17" y2="8" stroke="currentColor" strokeWidth="1.6" />
      <line x1="7" y1="2.5" x2="7" y2="5.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <line x1="13" y1="2.5" x2="13" y2="5.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

export function TrophyIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <path d="M6 3h8v4a4 4 0 0 1-8 0V3Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M6 4H3.5v1.5A2.5 2.5 0 0 0 6 8M14 4h2.5v1.5A2.5 2.5 0 0 1 14 8" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10 11v3M7 17h6M8 17c0-1.5 1-2 2-2s2 .5 2 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export function PlaneIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <path
        d="M10 2.5c.8 0 1.2.9 1.2 2.2v3l5.3 3v1.6l-5.3-1.5v3.3l1.7 1.2v1.3L10 18.6l-2.6-1v-1.3l1.7-1.2v-3.3L3.8 12.3v-1.6l5.3-3v-3C9.1 3.4 9.2 2.5 10 2.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function BedIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <path d="M3 5v10M3 14h14v-3a3 3 0 0 0-3-3H3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="6.5" cy="9.5" r="1.6" stroke="currentColor" strokeWidth="1.4" />
      <line x1="17" y1="14" x2="17" y2="16" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

export function ChevronLeft() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <path d="M12 4 6 10l6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function ChevronRight() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <path d="M8 4l6 6-6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function SearchIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.6" />
      <line x1="17" y1="17" x2="12.8" y2="12.8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

export function SendIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <path d="M17 3 3 9.5l6 2.5 2 6L17 3Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}
