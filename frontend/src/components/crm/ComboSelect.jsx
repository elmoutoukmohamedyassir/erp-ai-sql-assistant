import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { inputStyle } from './CrmUi'

/**
 * fetchOptions(query) => Promise<Array<{ id, label, sublabel? }>>
 * value: selected id
 * onChange(id, option)
 */
export default function ComboSelect({ value, label, onChange, fetchOptions, placeholder = 'Search…', disabled }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedLabel, setSelectedLabel] = useState(label || '')
  const boxRef = useRef(null)

  useEffect(() => { setSelectedLabel(label || '') }, [label])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoading(true)
    const t = setTimeout(async () => {
      try {
        const opts = await fetchOptions(query)
        if (!cancelled) setOptions(opts)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 200)
    return () => { cancelled = true; clearTimeout(t) }
  }, [query, open, fetchOptions])

  useEffect(() => {
    function onDocClick(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  return (
    <div ref={boxRef} style={{ position: 'relative' }}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(o => !o)}
        style={{
          ...inputStyle, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          cursor: disabled ? 'not-allowed' : 'pointer', textAlign: 'left',
          color: value ? 'var(--text)' : 'var(--dim)',
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {value ? selectedLabel || value : placeholder}
        </span>
        <ChevronDown size={13} color="var(--dim)" style={{ flexShrink: 0, marginLeft: 6 }} />
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, zIndex: 20,
          background: 'var(--surface)', border: '1px solid var(--border2)', borderRadius: 8,
          boxShadow: '0 12px 32px rgba(0,0,0,.45)', maxHeight: 260, overflowY: 'auto',
        }}>
          <div style={{ padding: 8, borderBottom: '1px solid var(--border)' }}>
            <input
              autoFocus
              style={inputStyle}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Type to search…"
            />
          </div>
          {loading && <div style={{ padding: '10px 12px', fontSize: 12, color: 'var(--dim)' }}>Searching…</div>}
          {!loading && options.length === 0 && (
            <div style={{ padding: '10px 12px', fontSize: 12, color: 'var(--dim)' }}>No matches</div>
          )}
          {!loading && options.map(opt => (
            <div
              key={opt.id}
              onClick={() => {
                onChange(opt.id, opt)
                setSelectedLabel(opt.label)
                setOpen(false)
                setQuery('')
              }}
              style={{
                padding: '8px 12px', fontSize: 13, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
                background: opt.id === value ? 'var(--card)' : 'transparent',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--card)' }}
              onMouseLeave={e => { e.currentTarget.style.background = opt.id === value ? 'var(--card)' : 'transparent' }}
            >
              <div>
                <div style={{ color: 'var(--text)' }}>{opt.label}</div>
                {opt.sublabel && <div style={{ fontSize: 11, color: 'var(--dim)' }}>{opt.sublabel}</div>}
              </div>
              {opt.id === value && <Check size={13} color="var(--cyan)" />}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
