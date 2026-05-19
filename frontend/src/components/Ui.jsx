export function Spinner({ size = 13 }) {
  return (
    <span
      style={{
        display: 'inline-block',
        width: size, height: size,
        border: '2px solid var(--border2)',
        borderTopColor: 'var(--cyan)',
        borderRadius: '50%',
        animation: 'spin .7s linear infinite',
        verticalAlign: 'middle',
        flexShrink: 0,
      }}
    />
  )
}

export function Badge({ children, color = 'gray' }) {
  const palettes = {
    green: { bg: 'rgba(61,185,85,.09)', color: 'var(--green)', border: 'rgba(61,185,85,.25)' },
    red:   { bg: 'rgba(240,80,80,.09)', color: 'var(--red)',   border: 'rgba(240,80,80,.25)' },
    cyan:  { bg: 'rgba(56,209,240,.09)',color: 'var(--cyan)',  border: 'rgba(56,209,240,.25)' },
    amber: { bg: 'rgba(212,150,30,.09)',color: 'var(--amber)', border: 'rgba(212,150,30,.25)' },
    gray:  { bg: 'rgba(107,120,136,.07)',color:'var(--muted)', border: 'var(--border2)' },
  }
  const p = palettes[color] || palettes.gray
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '2px 8px', borderRadius: 99,
      fontSize: 11, fontWeight: 500,
      background: p.bg, color: p.color,
      border: `1px solid ${p.border}`,
    }}>
      {children}
    </span>
  )
}

export function SectionTitle({ children }) {
  return (
    <p style={{
      fontSize: 11, fontWeight: 500, color: 'var(--muted)',
      textTransform: 'uppercase', letterSpacing: '.07em',
    }}>
      {children}
    </p>
  )
}

export function ErrBox({ children }) {
  return (
    <div style={{
      background: 'rgba(240,80,80,.06)', border: '1px solid rgba(240,80,80,.2)',
      borderRadius: 8, padding: '11px 14px',
      color: 'var(--red)', fontSize: 13, lineHeight: 1.55,
    }}>
      {children}
    </div>
  )
}

export function WarnBox({ children }) {
  return (
    <div style={{
      background: 'rgba(212,150,30,.06)', border: '1px solid rgba(212,150,30,.2)',
      borderRadius: 8, padding: '10px 14px',
      color: 'var(--amber)', fontSize: 12, lineHeight: 1.55,
    }}>
      {children}
    </div>
  )
}