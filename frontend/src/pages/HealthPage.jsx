import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Activity, Database, Clock, RefreshCw, CheckCircle2, XCircle } from 'lucide-react'
import { getHealth, getTables } from '../services/api'
import { SectionTitle, Spinner } from '../components/Ui'

export function HealthPage() {
  const [status,     setStatus]     = useState('checking')
  const [tableCount, setTableCount] = useState(null)
  const [lastCheck,  setLastCheck]  = useState(null)
  const [checking,   setChecking]   = useState(false)

  const check = async () => {
    setChecking(true)
    try {
      await getHealth()
      setStatus('ok')
    } catch {
      setStatus('err')
    }
    try {
      const d = await getTables()
      setTableCount((d.tables || []).length)
    } catch { /* ignore */ }
    setLastCheck(new Date())
    setChecking(false)
  }

  useEffect(() => {
    check()
    const id = setInterval(check, 30_000)
    return () => clearInterval(id)
  }, [])

  const cards = [
    {
      icon: status === 'ok' ? CheckCircle2 : XCircle,
      iconColor: status === 'ok' ? 'var(--green)' : status === 'err' ? 'var(--red)' : 'var(--dim)',
      label: 'API Status',
      value: status === 'ok' ? 'Online' : status === 'err' ? 'Offline' : 'Checking…',
      valueColor: status === 'ok' ? 'var(--green)' : status === 'err' ? 'var(--red)' : 'var(--muted)',
      sub: 'GET /health',
    },
    {
      icon: Database,
      iconColor: 'var(--cyan)',
      label: 'Indexed Tables',
      value: tableCount !== null ? tableCount : '—',
      sub: 'GET /tables',
    },
    {
      icon: Clock,
      iconColor: 'var(--amber)',
      label: 'Last Checked',
      value: lastCheck ? lastCheck.toLocaleTimeString() : '—',
      valueSize: 16,
      sub: 'Auto-refresh every 30s',
    },
  ]

  return (
    <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 20 }}>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <SectionTitle>API Health</SectionTitle>
          <p style={{ fontSize: 12, color: 'var(--dim)', marginTop: 3 }}>
            FastAPI backend · http://127.0.0.1:8000
          </p>
        </div>
        <button
          onClick={check}
          disabled={checking}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '7px 14px', background: 'var(--card)',
            border: '1px solid var(--border)', borderRadius: 7,
            color: 'var(--muted)', fontSize: 12,
            cursor: checking ? 'not-allowed' : 'pointer',
            fontFamily: 'Outfit, sans-serif', transition: 'all .15s',
          }}
          onMouseEnter={e => !checking && (e.currentTarget.style.color = 'var(--text)')}
          onMouseLeave={e => e.currentTarget.style.color = 'var(--muted)'}
        >
          {checking ? <Spinner size={12} /> : <RefreshCw size={12} />}
          Check now
        </button>
      </div>

      {/* cards grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
        {cards.map(({ icon: Icon, iconColor, label, value, valueColor, valueSize, sub }) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              background: 'var(--card)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '16px 18px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <Icon size={15} color={iconColor} />
              <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 500 }}>
                {label}
              </span>
            </div>
            <div style={{ fontSize: valueSize || 22, fontWeight: 600, color: valueColor || 'var(--text)', marginBottom: 4 }}>
              {value}
            </div>
            <div style={{ fontSize: 11, color: 'var(--dim)' }}>{sub}</div>
          </motion.div>
        ))}
      </div>

      {/* endpoint list */}
      <div>
        <p style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 500, marginBottom: 10 }}>
          Endpoints
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1, border: '1px solid var(--border)', borderRadius: 9, overflow: 'hidden' }}>
          {[
            { method: 'GET',  path: '/health',  desc: 'Liveness probe' },
            { method: 'GET',  path: '/tables',  desc: 'List all indexed tables' },
            { method: 'POST', path: '/ask',     desc: 'Natural language → SQL → results' },
            { method: 'POST', path: '/rebuild', desc: 'Rebuild FAISS schema index' },
          ].map(({ method, path, desc }, i) => (
            <div key={path} style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '10px 14px',
              background: i % 2 === 0 ? 'var(--card)' : 'transparent',
              borderBottom: i < 3 ? '1px solid var(--border)' : 'none',
            }}>
              <span style={{
                fontFamily: 'IBM Plex Mono, monospace', fontSize: 10, fontWeight: 500,
                color: method === 'GET' ? 'var(--green)' : 'var(--cyan)',
                background: method === 'GET' ? 'rgba(61,185,85,.1)' : 'rgba(56,209,240,.1)',
                border: `1px solid ${method === 'GET' ? 'rgba(61,185,85,.2)' : 'rgba(56,209,240,.2)'}`,
                padding: '1px 7px', borderRadius: 4, minWidth: 36, textAlign: 'center',
              }}>
                {method}
              </span>
              <span style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: 12, color: 'var(--text)', minWidth: 90 }}>{path}</span>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}