import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Search, Table2, RefreshCw } from 'lucide-react'
import { getTables } from '../services/api'
import { SectionTitle, Spinner } from '../components/Ui'

export function TablesPage() {
  const [tables,  setTables]  = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [search,  setSearch]  = useState('')

  const load = async () => {
    setLoading(true); setError(null)
    try {
      const d = await getTables()
      setTables(d.tables || [])
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const filtered = tables.filter(t => t.toLowerCase().includes(search.toLowerCase()))

  return (
    <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16, height: '100%', overflow: 'hidden' }}>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
        <div>
          <SectionTitle>Database Tables</SectionTitle>
          <p style={{ fontSize: 12, color: 'var(--dim)', marginTop: 3 }}>
            {loading ? 'Loading…' : `${tables.length} tables in the schema index`}
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 14px', background: 'var(--card)',
            border: '1px solid var(--border)', borderRadius: 7,
            color: 'var(--muted)', fontSize: 12, cursor: loading ? 'not-allowed' : 'pointer',
            fontFamily: 'Outfit, sans-serif', transition: 'all .15s',
          }}
          onMouseEnter={e => !loading && (e.currentTarget.style.color = 'var(--text)')}
          onMouseLeave={e => e.currentTarget.style.color = 'var(--muted)'}
        >
          {loading ? <Spinner size={12} /> : <RefreshCw size={12} />}
          Refresh
        </button>
      </div>

      {/* search */}
      <div style={{ position: 'relative', maxWidth: 320 }}>
        <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--dim)' }} />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search tables…"
          style={{
            width: '100%', paddingLeft: 30, paddingRight: 12, paddingTop: 7, paddingBottom: 7,
            background: 'var(--card)', border: '1px solid var(--border2)', borderRadius: 7,
            color: 'var(--text)', fontFamily: 'Outfit, sans-serif', fontSize: 13, outline: 'none',
          }}
          onFocus={e => e.target.style.borderColor = 'rgba(56,209,240,.4)'}
          onBlur={e => e.target.style.borderColor = 'var(--border2)'}
        />
      </div>

      {/* list */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {error ? (
          <p style={{ color: 'var(--red)', fontSize: 13 }}>Failed to load: {error}</p>
        ) : loading ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {Array.from({ length: 24 }).map((_, i) => (
              <div key={i} style={{
                height: 28, width: 80 + (i % 5) * 20,
                background: 'var(--card)', border: '1px solid var(--border)',
                borderRadius: 6, animation: 'pulse 1.5s infinite',
              }} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <p style={{ color: 'var(--dim)', fontSize: 13 }}>No tables match "{search}"</p>
        ) : (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}
          >
            {filtered.map((t, i) => (
              <motion.span
                key={t}
                initial={{ opacity: 0, scale: .95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.004 }}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  padding: '4px 10px', background: 'var(--card)',
                  border: '1px solid var(--border)', borderRadius: 6,
                  fontFamily: 'IBM Plex Mono, monospace', fontSize: 11, color: 'var(--muted)',
                  cursor: 'default', transition: 'all .12s',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'rgba(56,209,240,.3)'
                  e.currentTarget.style.color = 'var(--text)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border)'
                  e.currentTarget.style.color = 'var(--muted)'
                }}
              >
                <Table2 size={10} />
                {t}
              </motion.span>
            ))}
          </motion.div>
        )}
      </div>
    </div>
  )
}