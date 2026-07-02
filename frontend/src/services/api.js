import axios from 'axios'

// Vite proxy (vite.config.js) forwards all these paths to FastAPI on :8000
// so the browser never makes a cross-origin request.
const http = axios.create({
  baseURL: '',          // relative — proxy handles forwarding
  timeout: 120_000,
})

// ── attach JWT from sessionStorage on every request ───────────────────────
http.interceptors.request.use(config => {
  const token = sessionStorage.getItem('erp_token')
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  return config
})

// ── unwrap responses; surface the real error detail from FastAPI ──────────
http.interceptors.response.use(
  r => r.data,
  e => {
    const detail = e?.response?.data?.detail
    // detail can be a string or a Pydantic validation error array
    let msg
    if (Array.isArray(detail)) {
      msg = detail.map(d => d.msg || JSON.stringify(d)).join('; ')
    } else {
      msg = detail || e?.response?.data?.message || e?.message || 'Unknown error'
    }
    return Promise.reject(new Error(msg))
  }
)

// ── auth ──────────────────────────────────────────────────────────────────
export const register = (username, email, password) =>
  http.post('/auth/register', { username, email, password, role: 'user' })

// login uses form-encoded body (OAuth2PasswordRequestForm)
export const login = (username, password) => {
  const form = new URLSearchParams()
  form.append('username', username)
  form.append('password', password)
  return http.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
}

export const getMe = () => http.get('/auth/me')

// ── app ───────────────────────────────────────────────────────────────────
export const getHealth   = ()            => http.get('/health')
export const getTables   = ()            => http.get('/tables')
export const postRebuild = ()            => http.post('/rebuild')
export const postAsk     = (q, top_k=8) => http.post('/ask', { question: q, top_k })

// ── Data-Entry: table metadata ─────────────────────────────────────────────
export const getAllTables       = ()           => http.get('/tables')
export const getTableMetadata   = (tableName)  => http.get(`/tables/${encodeURIComponent(tableName)}/metadata`)

// ── Data-Entry: record create / update / execute ──────────────────────────
export const previewCreate  = (table, values)        => http.post('/records/create',  { table, values })
export const previewUpdate  = (table, where, values) => http.post('/records/update',  { table, where, values })
export const executeRecord  = (operation, table, values, where = null) =>
  http.post('/records/execute', { operation, table, values, ...(where ? { where } : {}) })