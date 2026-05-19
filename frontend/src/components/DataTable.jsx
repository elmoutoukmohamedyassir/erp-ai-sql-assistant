import { useState, useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

const PER = 50

export function DataTable({ columns, rows }) {
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    if (!search.trim()) return rows
    const q = search.toLowerCase()
    return rows.filter(r => r.some(c => String(c ?? '').toLowerCase().includes(q)))
  }, [rows, search])

  const pages   = Math.max(1, Math.ceil(filtered.length / PER))
  const safePage = Math.min(page, pages - 1)
  const slice   = filtered.slice(safePage * PER, (safePage + 1) * PER)

  const S = { // inline style helpers
    th: { padding: '7px 12px', textAlign: 'left', color: 'var(--muted)', fontWeight: 500, whiteSpace: 'nowrap', fontSize: 12 },
    td: {
      padding: '6px 12px', color: 'var(--muted)',
      fontFamily: 'IBM Plex Mono, monospace', fontSize: 11,
      whiteSpace: 'nowrap', maxWidth: 200,
      overflow: 'hidden', textOverflow: 'ellipsis',
      borderBottom: '1px solid rgba(30,37,48,.7)',
    },
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
        <input
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(0) }}
          placeholder="Search results…"
          style={{
            background: 'var(--surface)', border: '1px solid var(--border2)',
            borderRadius: 7, padding: '5px 11px', color: 'var(--text)',
            fontFamily: 'Outfit, sans-serif', fontSize: 12, outline: 'none', width: 200,
          }}
        />
        <span style={{ fontSize: 11, color: 'var(--dim)' }}>
          {filtered.length} row{filtered.length !== 1 ? 's' : ''}
          {search && ` of ${rows.length}`}
        </span>
      </div>

      {/* table */}
      <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#0d1117', borderBottom: '1px solid var(--border)' }}>
                {columns.map((c, i) => <th key={i} style={S.th}>{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {slice.length === 0 ? (
                <tr><td colSpan={columns.length} style={{ padding: '20px', textAlign: 'center', color: 'var(--dim)', fontSize: 12 }}>No results</td></tr>
              ) : slice.map((row, ri) => (
                <tr key={ri} style={{ transition: 'background .1s' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(56,209,240,.03)'}
                  onMouseLeave={e => e.currentTarget.style.background = ''}
                >
                  {row.map((cell, ci) => (
                    <td key={ci} style={S.td} title={String(cell ?? '')}>
                      {cell === null || cell === undefined
                        ? <i style={{ color: 'var(--dim)' }}>null</i>
                        : String(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* pagination */}
      {pages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
          <PgBtn onClick={() => setPage(p => Math.max(0, p - 1))} disabled={safePage === 0}><ChevronLeft size={13} /></PgBtn>
          {Array.from({ length: Math.min(pages, 9) }, (_, i) => {
            const n = pages <= 9 ? i : getPageNums(safePage, pages)[i]
            if (n === '…') return <span key={i} style={{ color: 'var(--dim)', fontSize: 11, padding: '0 2px' }}>…</span>
            return (
              <PgBtn key={n} active={n === safePage} onClick={() => setPage(n)}>
                {n + 1}
              </PgBtn>
            )
          })}
          <PgBtn onClick={() => setPage(p => Math.min(pages - 1, p + 1))} disabled={safePage === pages - 1}><ChevronRight size={13} /></PgBtn>
          <span style={{ fontSize: 11, color: 'var(--dim)', marginLeft: 4 }}>{filtered.length} total</span>
        </div>
      )}
    </div>
  )
}

function PgBtn({ children, onClick, disabled, active }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '3px 8px', minWidth: 28, textAlign: 'center',
        background: active ? 'rgba(56,209,240,.1)' : 'var(--card)',
        border: `1px solid ${active ? 'var(--cyan)' : 'var(--border)'}`,
        borderRadius: 5, color: active ? 'var(--cyan)' : 'var(--muted)',
        fontSize: 11, cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? .35 : 1, transition: 'all .12s',
        fontFamily: 'Outfit, sans-serif',
      }}
    >
      {children}
    </button>
  )
}

function getPageNums(cur, total) {
  if (cur < 4) return [0,1,2,3,4,'…',total-1]
  if (cur > total - 5) return [0,'…',total-5,total-4,total-3,total-2,total-1]
  return [0,'…',cur-1,cur,cur+1,'…',total-1]
}