import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { X, ChevronLeft, ChevronRight, AlertTriangle, Search } from 'lucide-react'

// ─── shared style tokens ────────────────────────────────────────────────────

export const inputStyle = {
  width: '100%', boxSizing: 'border-box',
  padding: '8px 12px',
  background: 'var(--bg)', border: '1px solid var(--border2)',
  borderRadius: 7, color: 'var(--text)',
  fontFamily: 'Outfit, sans-serif', fontSize: 13, outline: 'none',
}

export const Card = ({ children, style = {} }) => (
  <div style={{
    background: 'var(--card)', border: '1px solid var(--border)',
    borderRadius: 10, padding: '16px 18px', ...style,
  }}>
    {children}
  </div>
)

export const PrimaryButton = ({ children, onClick, disabled, style = {}, type = 'button' }) => (
  <button
    type={type}
    onClick={onClick}
    disabled={disabled}
    style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '8px 16px', borderRadius: 8, border: 'none',
      background: disabled ? 'var(--border2)' : 'var(--cyan)',
      color: disabled ? 'var(--dim)' : '#04141a',
      fontSize: 13, fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer',
      fontFamily: 'Outfit, sans-serif', transition: 'opacity .15s', opacity: 1,
      ...style,
    }}
    onMouseEnter={e => !disabled && (e.currentTarget.style.opacity = '.85')}
    onMouseLeave={e => !disabled && (e.currentTarget.style.opacity = '1')}
  >
    {children}
  </button>
)

export const GhostButton = ({ children, onClick, disabled, danger, style = {} }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '7px 13px', borderRadius: 7,
      border: `1px solid ${danger ? 'rgba(240,80,80,.3)' : 'var(--border)'}`,
      background: 'transparent',
      color: disabled ? 'var(--dim)' : danger ? 'var(--red)' : 'var(--muted)',
      fontSize: 12.5, cursor: disabled ? 'not-allowed' : 'pointer',
      fontFamily: 'Outfit, sans-serif', transition: 'all .15s',
      ...style,
    }}
  >
    {children}
  </button>
)

export const IconButton = ({ icon: Icon, onClick, title, danger, size = 13 }) => (
  <button
    onClick={onClick}
    title={title}
    style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      width: 28, height: 28, borderRadius: 6,
      border: `1px solid ${danger ? 'rgba(240,80,80,.25)' : 'var(--border)'}`,
      background: 'transparent', color: danger ? 'var(--red)' : 'var(--muted)',
      cursor: 'pointer', transition: 'all .15s', flexShrink: 0,
    }}
    onMouseEnter={e => { e.currentTarget.style.background = danger ? 'rgba(240,80,80,.08)' : 'var(--surface)' }}
    onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
  >
    <Icon size={size} />
  </button>
)

export const Label = ({ children, required }) => (
  <label style={{
    fontSize: 11, color: 'var(--muted)', fontWeight: 600,
    letterSpacing: '.04em', textTransform: 'uppercase', display: 'flex',
    alignItems: 'center', gap: 4, marginBottom: 5,
  }}>
    {children}
    {required && <span style={{ color: 'var(--red)', fontSize: 13 }}>*</span>}
  </label>
)

export const FormField = ({ label, required, children }) => (
  <div>
    <Label required={required}>{label}</Label>
    {children}
  </div>
)

export const SearchBar = ({ value, onChange, placeholder = 'Search…' }) => (
  <div style={{ position: 'relative', width: 260, maxWidth: '100%' }}>
    <Search size={13} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--dim)' }} />
    <input
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      style={{ ...inputStyle, paddingLeft: 30 }}
    />
  </div>
)

// ─── Modal ───────────────────────────────────────────────────────────────────

export function Modal({ open, onClose, title, children, width = 520 }) {
  useEffect(() => {
    if (!open) return
    const onKey = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, background: 'rgba(5,7,10,.6)',
          backdropFilter: 'blur(2px)', zIndex: 100,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
        }}
      >
        <motion.div
          initial={{ opacity: 0, y: 12, scale: .98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: .98 }}
          transition={{ duration: .15 }}
          onClick={e => e.stopPropagation()}
          style={{
            width, maxWidth: '100%', maxHeight: '88vh', overflowY: 'auto',
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 12, boxShadow: '0 24px 64px rgba(0,0,0,.55)',
          }}
        >
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '14px 18px', borderBottom: '1px solid var(--border)', position: 'sticky', top: 0,
            background: 'var(--surface)', zIndex: 1,
          }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>{title}</span>
            <button onClick={onClose} style={{
              display: 'flex', width: 26, height: 26, alignItems: 'center', justifyContent: 'center',
              background: 'transparent', border: 'none', borderRadius: 6, color: 'var(--dim)', cursor: 'pointer',
            }}>
              <X size={15} />
            </button>
          </div>
          <div style={{ padding: 18 }}>{children}</div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body
  )
}

// ─── Confirm dialog ─────────────────────────────────────────────────────────

export function ConfirmDialog({ open, title = 'Are you sure?', message, confirmLabel = 'Delete', onConfirm, onCancel, loading }) {
  if (!open) return null
  return (
    <Modal open={open} onClose={onCancel} title={title} width={380}>
      <div style={{ display: 'flex', gap: 12, marginBottom: 18 }}>
        <div style={{
          width: 34, height: 34, borderRadius: 8, flexShrink: 0,
          background: 'rgba(240,80,80,.1)', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <AlertTriangle size={16} color="var(--red)" />
        </div>
        <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.6 }}>{message}</p>
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <GhostButton onClick={onCancel}>Cancel</GhostButton>
        <PrimaryButton
          onClick={onConfirm}
          disabled={loading}
          style={{ background: 'var(--red)', color: '#fff' }}
        >
          {loading ? 'Deleting…' : confirmLabel}
        </PrimaryButton>
      </div>
    </Modal>
  )
}

// ─── Pagination ─────────────────────────────────────────────────────────────

export function Pagination({ page, pageSize, total, onPageChange }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (pages <= 1) return null
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
      <PgBtn onClick={() => onPageChange(Math.max(1, page - 1))} disabled={page === 1}>
        <ChevronLeft size={13} />
      </PgBtn>
      <span style={{ fontSize: 12, color: 'var(--dim)', padding: '0 4px' }}>
        Page {page} of {pages} · {total} total
      </span>
      <PgBtn onClick={() => onPageChange(Math.min(pages, page + 1))} disabled={page === pages}>
        <ChevronRight size={13} />
      </PgBtn>
    </div>
  )
}

function PgBtn({ children, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        width: 28, height: 28, background: 'var(--card)',
        border: '1px solid var(--border)', borderRadius: 6,
        color: 'var(--muted)', cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? .35 : 1,
      }}
    >
      {children}
    </button>
  )
}

// ─── Empty / loading states ─────────────────────────────────────────────────

export function EmptyState({ icon: Icon, title, subtitle, action }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '48px 20px', gap: 8, textAlign: 'center',
    }}>
      {Icon && <Icon size={26} color="var(--dim)" style={{ marginBottom: 4 }} />}
      <span style={{ fontSize: 13.5, color: 'var(--muted)', fontWeight: 500 }}>{title}</span>
      {subtitle && <span style={{ fontSize: 12, color: 'var(--dim)', maxWidth: 320 }}>{subtitle}</span>}
      {action}
    </div>
  )
}

export function LoadingBlock() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '4px 0' }}>
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} style={{
          height: 40, borderRadius: 8, background: 'var(--card)',
          border: '1px solid var(--border)', opacity: 1 - i * 0.08,
        }} />
      ))}
    </div>
  )
}
