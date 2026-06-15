import { useState } from 'react'
import { motion } from 'framer-motion'
import { UserPlus, Eye, EyeOff, Loader2 } from 'lucide-react'
import { register } from '../services/api'
import { useAuth } from '../context/AuthContext'

export function RegisterPage({ onSwitch }) {
  const { login: authLogin } = useAuth()
  const [username, setUsername] = useState('')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [show,     setShow]     = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')

  const submit = async () => {
    if (!username.trim() || !email.trim() || !password.trim()) {
      setError('Please fill in all fields.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await register(username.trim(), email.trim(), password)
      authLogin(data.access_token, { username: data.username, role: data.role })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const onKey = e => { if (e.key === 'Enter') submit() }

  return (
    <div style={wrapStyle}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        style={cardStyle}
      >
        {/* brand */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={iconWrap}>
            <svg width="18" height="18" viewBox="0 0 14 14" fill="none">
              <path d="M2 7h10M2 4h6M2 10h8" stroke="#38d1f0" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)', marginTop: 10 }}>
            Create account
          </h1>
          <p style={{ fontSize: 12, color: 'var(--dim)', marginTop: 4 }}>
            Register as a <span style={{ color: 'var(--cyan)' }}>user</span> — ask anything about your ERP data
          </p>
        </div>

        {/* fields */}
        <Field label="Username">
          <input
            value={username}
            onChange={e => setUsername(e.target.value)}
            onKeyDown={onKey}
            placeholder="your_username"
            style={inputStyle}
            onFocus={e => e.target.style.borderColor = 'rgba(56,209,240,.5)'}
            onBlur={e  => e.target.style.borderColor = 'var(--border2)'}
            autoFocus
          />
        </Field>

        <Field label="Email" style={{ marginTop: 14 }}>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            onKeyDown={onKey}
            placeholder="you@company.com"
            style={inputStyle}
            onFocus={e => e.target.style.borderColor = 'rgba(56,209,240,.5)'}
            onBlur={e  => e.target.style.borderColor = 'var(--border2)'}
          />
        </Field>

        <Field label="Password" style={{ marginTop: 14 }}>
          <div style={{ position: 'relative' }}>
            <input
              type={show ? 'text' : 'password'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={onKey}
              placeholder="Min. 8 characters"
              style={{ ...inputStyle, paddingRight: 38 }}
              onFocus={e => e.target.style.borderColor = 'rgba(56,209,240,.5)'}
              onBlur={e  => e.target.style.borderColor = 'var(--border2)'}
            />
            <button
              onClick={() => setShow(s => !s)}
              style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--dim)' }}
            >
              {show ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
          <span style={{ fontSize: 11, color: 'var(--dim)', marginTop: 3 }}>Minimum 8 characters</span>
        </Field>

        {error && (
          <div style={{ marginTop: 12, padding: '9px 12px', background: 'rgba(240,80,80,.08)', border: '1px solid rgba(240,80,80,.25)', borderRadius: 7, fontSize: 12, color: 'var(--red)' }}>
            {error}
          </div>
        )}

        <button
          onClick={submit}
          disabled={loading}
          style={{ ...btnStyle, marginTop: 22, opacity: loading ? .7 : 1, cursor: loading ? 'not-allowed' : 'pointer' }}
        >
          {loading
            ? <Loader2 size={14} style={{ animation: 'spin .7s linear infinite' }} />
            : <UserPlus size={14} />
          }
          {loading ? 'Creating account…' : 'Create account'}
        </button>

        <p style={{ marginTop: 18, textAlign: 'center', fontSize: 12, color: 'var(--dim)' }}>
          Already have an account?{' '}
          <button onClick={onSwitch} style={{ background: 'none', border: 'none', color: 'var(--cyan)', cursor: 'pointer', fontSize: 12, fontFamily: 'Outfit, sans-serif' }}>
            Sign in
          </button>
        </p>
      </motion.div>
    </div>
  )
}

function Field({ label, children, style }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, ...style }}>
      <label style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '.06em' }}>{label}</label>
      {children}
    </div>
  )
}

const wrapStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  height: '100vh', background: 'var(--bg)', padding: 20,
}
const cardStyle = {
  width: '100%', maxWidth: 400,
  background: 'var(--surface)', border: '1px solid var(--border)',
  borderRadius: 14, padding: '32px 30px',
  boxShadow: '0 24px 64px rgba(0,0,0,.5)',
}
const iconWrap = {
  width: 44, height: 44, borderRadius: 12, margin: '0 auto',
  background: 'rgba(56,209,240,.08)', border: '1px solid rgba(56,209,240,.18)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
}
const inputStyle = {
  width: '100%', padding: '9px 12px',
  background: 'var(--card)', border: '1px solid var(--border2)',
  borderRadius: 7, color: 'var(--text)',
  fontFamily: 'Outfit, sans-serif', fontSize: 13, outline: 'none',
  boxSizing: 'border-box', transition: 'border-color .15s',
}
const btnStyle = {
  width: '100%', padding: '10px 0',
  background: 'var(--cyan)', border: 'none', borderRadius: 8,
  color: '#0a0c0f', fontWeight: 700, fontSize: 14,
  fontFamily: 'Outfit, sans-serif', display: 'flex',
  alignItems: 'center', justifyContent: 'center', gap: 8,
  transition: 'opacity .15s',
}