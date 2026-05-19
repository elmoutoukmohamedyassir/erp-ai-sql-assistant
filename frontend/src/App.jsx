import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Toaster } from 'react-hot-toast'
import { MessageSquare, Table2, Activity, RefreshCw } from 'lucide-react'
import { useHealth } from './hooks/useHealth'
import { AskPage }     from './pages/Askpage'
import { TablesPage }  from './pages/TablesPage'
import { HealthPage }  from './pages/HealthPage'
import { RebuildPage } from './pages/RebuildPage'

const TABS = [
  { id: 'ask',     label: 'Ask',     icon: MessageSquare },
  { id: 'tables',  label: 'Tables',  icon: Table2 },
  { id: 'health',  label: 'Health',  icon: Activity },
  { id: 'rebuild', label: 'Rebuild', icon: RefreshCw },
]

const PAGES = {
  ask:     AskPage,
  tables:  TablesPage,
  health:  HealthPage,
  rebuild: RebuildPage,
}

export default function App() {
  const [active, setActive] = useState('ask')
  const { status } = useHealth()

  const Page = PAGES[active]

  const dotColor = {
    ok:       '#3db955',
    err:      '#f05050',
    checking: '#3d4a58',
  }[status]

  const dotGlow = {
    ok:  '0 0 6px rgba(61,185,85,.65)',
    err: '0 0 6px rgba(240,80,80,.65)',
  }[status] || 'none'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>

      {/* ── top bar ── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        height: 48, padding: '0 20px', flexShrink: 0,
        borderBottom: '1px solid var(--border)', background: 'var(--surface)',
      }}>
        {/* brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 7,
            background: 'rgba(56,209,240,.1)', border: '1px solid rgba(56,209,240,.18)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 7h10M2 4h6M2 10h8" stroke="#38d1f0" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)' }}>
            ERP <span style={{ color: 'var(--cyan)' }}>AI</span> Assistant
          </span>
          <span style={{ fontSize: 11, color: 'var(--dim)', marginLeft: 2, display: 'none' }}>· Sage 100</span>
        </div>

        {/* health dot */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: dotColor, boxShadow: dotGlow,
            transition: 'all .4s',
          }} />
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>
            {status === 'ok' ? 'Connected' : status === 'err' ? 'Offline' : 'Checking…'}
          </span>
        </div>
      </div>

      {/* ── tabs ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 2, padding: '0 20px',
        height: 42, flexShrink: 0,
        borderBottom: '1px solid var(--border)', background: 'var(--surface)',
        position: 'relative',
      }}>
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = active === id
          return (
            <button
              key={id}
              onClick={() => setActive(id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '5px 13px', borderRadius: 7, border: 'none',
                background: isActive ? 'var(--card)' : 'transparent',
                color: isActive ? 'var(--text)' : 'var(--muted)',
                fontSize: 13, cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
                transition: 'all .15s', position: 'relative',
              }}
              onMouseEnter={e => !isActive && (e.currentTarget.style.color = 'var(--text)')}
              onMouseLeave={e => !isActive && (e.currentTarget.style.color = 'var(--muted)')}
            >
              <Icon size={13} />
              {label}
              {isActive && (
                <motion.div
                  layoutId="tab-indicator"
                  style={{
                    position: 'absolute', bottom: -10, left: 0, right: 0, height: 2,
                    background: 'var(--cyan)', borderRadius: 99,
                  }}
                  transition={{ type: 'spring', stiffness: 400, damping: 35 }}
                />
              )}
            </button>
          )
        })}
      </div>

      {/* ── page ── */}
      <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={active}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.18 }}
            style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
          >
            <Page />
          </motion.div>
        </AnimatePresence>
      </div>

      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: 'var(--card)', color: 'var(--text)',
            border: '1px solid var(--border)', borderRadius: 9,
            fontSize: 13, fontFamily: 'Outfit, sans-serif',
            boxShadow: '0 8px 24px rgba(0,0,0,.4)',
          },
          success: { iconTheme: { primary: 'var(--green)', secondary: 'var(--card)' } },
          error:   { iconTheme: { primary: 'var(--red)',   secondary: 'var(--card)' } },
        }}
      />
    </div>
  )
}