import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

function highlight(sql) {
  const KW = /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AS|AND|OR|NOT|IN|IS|NULL|ORDER|BY|GROUP|HAVING|TOP|DISTINCT|WITH|UNION|CASE|WHEN|THEN|ELSE|END|ISNULL|COALESCE|CAST|CONVERT|GETDATE|COUNT|SUM|AVG|MIN|MAX|LIKE|EXISTS|BETWEEN|INTO|SET)\b/gi
  const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
  return esc(sql)
    .replace(KW, m => `<span class="kw">${m}</span>`)
    .replace(/'([^']*)'/g, `<span class="str">'$1'</span>`)
    .replace(/\b(\d+)\b/g, `<span class="num">$1</span>`)
}

export function SqlBlock({ sql }) {
  const [copied, setCopied] = useState(false)

  const copy = () => {
    navigator.clipboard.writeText(sql)
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden',
    }}>
      {/* header bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '6px 12px', background: '#0d1117',
        borderBottom: '1px solid var(--border)',
      }}>
        <span style={{
          fontFamily: 'IBM Plex Mono, monospace', fontSize: 10,
          color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '.06em',
        }}>
          SQL
        </span>
        <button
          onClick={copy}
          style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '2px 9px', background: 'transparent',
            border: '1px solid var(--border2)', borderRadius: 5,
            color: copied ? 'var(--green)' : 'var(--muted)',
            fontSize: 11, cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
            transition: 'all .15s',
          }}
        >
          {copied ? <Check size={11} /> : <Copy size={11} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      {/* code */}
      <div
        style={{
          background: '#0d1117', padding: '12px 14px',
          fontFamily: 'IBM Plex Mono, monospace', fontSize: 12,
          lineHeight: 1.75, color: '#c9d1d9',
          overflowX: 'auto', whiteSpace: 'pre',
        }}
        dangerouslySetInnerHTML={{ __html: highlight(sql) }}
      />
    </div>
  )
}