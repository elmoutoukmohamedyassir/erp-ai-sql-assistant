import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { RefreshCw, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'
import { postRebuild } from '../services/api'
import { SectionTitle, Spinner } from '../components/Ui'

export function RebuildPage() {
  const [state,   setState]   = useState('idle')  // idle | loading | ok | err
  const [message, setMessage] = useState('')

  const run = async () => {
    setState('loading')
    setMessage('')
    try {
      const d = await postRebuild()
      setState('ok')
      setMessage(d.status || 'Schema index rebuilt successfully.')
    } catch (e) {
      setState('err')
      setMessage(e.message)
    }
  }

  const iconMap = {
    idle:    { icon: null,          color: 'var(--cyan)'  },
    loading: { icon: null,          color: 'var(--muted)' },
    ok:      { icon: CheckCircle2,  color: 'var(--green)' },
    err:     { icon: XCircle,       color: 'var(--red)'   },
  }
  const { icon: StatusIcon, color: statusColor } = iconMap[state]

  return (
    <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 580 }}>

      <div>
        <SectionTitle>Rebuild Schema Index</SectionTitle>
        <p style={{ fontSize: 12, color: 'var(--dim)', marginTop: 4 }}>POST /rebuild</p>
      </div>

      <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.65 }}>
        Re-introspects the SQL Server database and rebuilds the FAISS semantic search index
        used for table retrieval. Run this after any schema changes — new tables, renamed columns,
        dropped views, etc.
      </p>

      {/* warning notice */}
      <div style={{
        display: 'flex', gap: 10,
        background: 'rgba(212,150,30,.06)', border: '1px solid rgba(212,150,30,.2)',
        borderRadius: 9, padding: '11px 14px',
      }}>
        <AlertTriangle size={15} color="var(--amber)" style={{ flexShrink: 0, marginTop: 1 }} />
        <p style={{ fontSize: 12, color: 'var(--amber)', lineHeight: 1.6 }}>
          This operation re-introspects every table and re-embeds all schema chunks.
          It may take 1–3 minutes depending on the number of tables.
        </p>
      </div>

      {/* action */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <button
          onClick={run}
          disabled={state === 'loading'}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 22px', background: 'transparent',
            border: `1px solid ${state === 'loading' ? 'var(--border2)' : 'var(--cyan)'}`,
            borderRadius: 8, cursor: state === 'loading' ? 'not-allowed' : 'pointer',
            color: state === 'loading' ? 'var(--muted)' : 'var(--cyan)',
            fontFamily: 'Outfit, sans-serif', fontWeight: 600, fontSize: 14,
            transition: 'all .15s',
          }}
          onMouseEnter={e => state !== 'loading' && (e.currentTarget.style.background = 'rgba(56,209,240,.07)')}
          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
        >
          {state === 'loading'
            ? <><Spinner size={14} /> Rebuilding…</>
            : <><RefreshCw size={14} /> Rebuild Index</>
          }
        </button>

        {state !== 'idle' && state !== 'loading' && (
          <button
            onClick={() => { setState('idle'); setMessage('') }}
            style={{
              padding: '10px 16px', background: 'transparent',
              border: '1px solid var(--border)', borderRadius: 8,
              color: 'var(--muted)', fontSize: 13, cursor: 'pointer',
              fontFamily: 'Outfit, sans-serif', transition: 'all .15s',
            }}
          >
            Reset
          </button>
        )}
      </div>

      {/* result */}
      <AnimatePresence>
        {message && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{
              display: 'flex', alignItems: 'flex-start', gap: 10,
              background: state === 'ok' ? 'rgba(61,185,85,.06)' : 'rgba(240,80,80,.06)',
              border: `1px solid ${state === 'ok' ? 'rgba(61,185,85,.25)' : 'rgba(240,80,80,.25)'}`,
              borderRadius: 9, padding: '12px 14px',
            }}
          >
            {StatusIcon && <StatusIcon size={15} color={statusColor} style={{ flexShrink: 0, marginTop: 1 }} />}
            <p style={{ fontSize: 13, color: statusColor, lineHeight: 1.5 }}>{message}</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* steps */}
      <div>
        <p style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '.07em', fontWeight: 500, marginBottom: 10 }}>
          What happens during rebuild
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0, border: '1px solid var(--border)', borderRadius: 9, overflow: 'hidden' }}>
          {[
            { n: '01', text: 'Connect to SQL Server via SQLAlchemy' },
            { n: '02', text: 'Introspect all tables, columns, PKs and FKs' },
            { n: '03', text: 'Build rich text chunks per table' },
            { n: '04', text: 'Embed chunks with all-MiniLM-L6-v2' },
            { n: '05', text: 'Build and persist FAISS IndexFlatIP' },
            { n: '06', text: 'Clear in-memory schema LRU cache' },
          ].map(({ n, text }, i, arr) => (
            <div key={n} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '9px 14px',
              background: i % 2 === 0 ? 'var(--card)' : 'transparent',
              borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none',
            }}>
              <span style={{
                fontFamily: 'IBM Plex Mono, monospace', fontSize: 10,
                color: 'var(--dim)', minWidth: 22,
              }}>{n}</span>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>{text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}