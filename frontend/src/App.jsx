import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Toaster } from 'react-hot-toast'
import { MessageSquare, Table2, Activity, RefreshCw, LogOut, ShieldCheck, User, Edit3, Users, Package, Boxes, ClipboardList } from 'lucide-react'
import { useHealth } from './hooks/useHealth'
import { useAuth }   from './context/AuthContext'
import { AskPage }       from './pages/Askpage'
import { TablesPage }    from './pages/TablesPage'
import { HealthPage }    from './pages/HealthPage'
import { RebuildPage }   from './pages/RebuildPage'
import { LoginPage }     from './pages/LoginPage'
import { RegisterPage }  from './pages/RegisterPage'
import { DataEntryPage } from './pages/DataEntryPage'
import ClientsPage       from './pages/crm/ClientsPage'
import ProductsPage      from './pages/crm/ProductsPage'
import StockPage         from './pages/crm/StockPage'
import OrdersPage        from './pages/crm/OrdersPage'

// All tabs — visibility controlled by role
// CRM tabs (clients/products/stock/orders) are adminOnly: false because the
// backend CRM routes (api/crm/router.py) are protected with require_any,
// i.e. open to both "user" and "admin" roles.
const ALL_TABS = [
  { id: 'ask',       label: 'Ask',        icon: MessageSquare, adminOnly: false },
  { id: 'clients',   label: 'Clients',    icon: Users,         adminOnly: false },
  { id: 'products',  label: 'Products',   icon: Package,       adminOnly: false },
  { id: 'stock',     label: 'Stock',      icon: Boxes,         adminOnly: false },
  { id: 'orders',    label: 'Orders',     icon: ClipboardList, adminOnly: false },
  { id: 'dataentry', label: 'Data Entry', icon: Edit3,         adminOnly: true  },
  { id: 'tables',    label: 'Tables',     icon: Table2,        adminOnly: true  },
  { id: 'health',    label: 'Health',     icon: Activity,      adminOnly: true  },
  { id: 'rebuild',   label: 'Rebuild',    icon: RefreshCw,     adminOnly: true  },
]

const PAGES = {
  ask:       AskPage,
  clients:   ClientsPage,
  products:  ProductsPage,
  stock:     StockPage,
  orders:    OrdersPage,
  dataentry: DataEntryPage,
  tables:    TablesPage,
  health:    HealthPage,
  rebuild:   RebuildPage,
}

export default function App() {
  const { isAuth, isAdmin, user, logout } = useAuth()
  const [authView, setAuthView] = useState('login')   // 'login' | 'register'
  const [active,   setActive]   = useState('ask')
  // only poll /health when authenticated as admin (it requires admin JWT)
  const { status } = useHealth(isAuth && isAdmin)

  // ── not authenticated — show login / register ────────────────────────────
  if (!isAuth) {
    return authView === 'login'
      ? <LoginPage    onSwitch={() => setAuthView('register')} />
      : <RegisterPage onSwitch={() => setAuthView('login')} />
  }

  // tabs visible to current user
  const visibleTabs = ALL_TABS.filter(t => !t.adminOnly || isAdmin)

  // if active tab was admin-only and user just logged in as non-admin, reset
  const safeActive = visibleTabs.find(t => t.id === active) ? active : 'ask'
  const Page = PAGES[safeActive]

  const dotColor = { ok: '#3db955', err: '#f05050', checking: '#3d4a58' }[status]
  const dotGlow  = { ok: '0 0 6px rgba(61,185,85,.65)', err: '0 0 6px rgba(240,80,80,.65)' }[status] || 'none'

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
        </div>

        {/* right side: health dot + user chip + logout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {/* health */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: dotColor, boxShadow: dotGlow, transition: 'all .4s' }} />
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>
              {status === 'ok' ? 'Connected' : status === 'err' ? 'Offline' : 'Checking…'}
            </span>
          </div>

          {/* user chip */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '3px 10px', background: 'var(--card)',
            border: `1px solid ${isAdmin ? 'rgba(56,209,240,.25)' : 'var(--border)'}`,
            borderRadius: 99, fontSize: 12,
          }}>
            {isAdmin
              ? <ShieldCheck size={12} color="var(--cyan)" />
              : <User        size={12} color="var(--muted)" />
            }
            <span style={{ color: isAdmin ? 'var(--cyan)' : 'var(--muted)', fontWeight: 500 }}>
              {user?.username}
            </span>
            <span style={{
              fontSize: 10, color: isAdmin ? 'var(--cyan)' : 'var(--dim)',
              background: isAdmin ? 'rgba(56,209,240,.08)' : 'rgba(107,120,136,.08)',
              border: `1px solid ${isAdmin ? 'rgba(56,209,240,.2)' : 'var(--border2)'}`,
              borderRadius: 99, padding: '1px 6px', marginLeft: 2, fontWeight: 600,
              textTransform: 'uppercase', letterSpacing: '.05em',
            }}>
              {user?.role}
            </span>
          </div>

          {/* logout */}
          <button
            onClick={logout}
            title="Sign out"
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '4px 10px', background: 'transparent',
              border: '1px solid var(--border)', borderRadius: 6,
              color: 'var(--dim)', fontSize: 12, cursor: 'pointer',
              fontFamily: 'Outfit, sans-serif', transition: 'all .15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = 'var(--red)'; e.currentTarget.style.borderColor = 'rgba(240,80,80,.35)' }}
            onMouseLeave={e => { e.currentTarget.style.color = 'var(--dim)'; e.currentTarget.style.borderColor = 'var(--border)' }}
          >
            <LogOut size={12} /> Sign out
          </button>
        </div>
      </div>

      {/* ── tabs (only show tabs the role can access) ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 2, padding: '0 20px',
        height: 42, flexShrink: 0,
        borderBottom: '1px solid var(--border)', background: 'var(--surface)',
        position: 'relative',
      }}>
        {visibleTabs.map(({ id, label, icon: Icon }) => {
          const isAct = safeActive === id
          return (
            <button
              key={id}
              onClick={() => setActive(id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '5px 13px', borderRadius: 7, border: 'none',
                background: isAct ? 'var(--card)' : 'transparent',
                color: isAct ? 'var(--text)' : 'var(--muted)',
                fontSize: 13, cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
                transition: 'all .15s', position: 'relative',
              }}
              onMouseEnter={e => !isAct && (e.currentTarget.style.color = 'var(--text)')}
              onMouseLeave={e => !isAct && (e.currentTarget.style.color = 'var(--muted)')}
            >
              <Icon size={13} />
              {label}
              {isAct && (
                <motion.div
                  layoutId="tab-indicator"
                  style={{ position: 'absolute', bottom: -10, left: 0, right: 0, height: 2, background: 'var(--cyan)', borderRadius: 99 }}
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
            key={safeActive}
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