import axios from 'axios'

// Deliberately a SEPARATE axios instance from services/api.js so the CRM
// module has zero risk of altering Admin Data-Entry's request/response
// behavior. Same conventions (JWT header, unwrapped responses, friendly
// error messages) so it feels consistent to the rest of the app.
const http = axios.create({
  baseURL: '',
  timeout: 60_000,
})

http.interceptors.request.use(config => {
  const token = sessionStorage.getItem('erp_token')
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  r => r.data,
  e => {
    const detail = e?.response?.data?.detail
    let msg
    if (Array.isArray(detail)) {
      msg = detail.map(d => d.msg || JSON.stringify(d)).join('; ')
    } else {
      msg = detail || e?.response?.data?.message || e?.message || 'Something went wrong'
    }
    return Promise.reject(new Error(msg))
  }
)

// ── Clients ──────────────────────────────────────────────────────────────
export const listClients  = (params = {})        => http.get('/crm/clients', { params })
export const getClient    = (id)                 => http.get(`/crm/clients/${encodeURIComponent(id)}`)
export const createClient = (data)               => http.post('/crm/clients', data)
export const updateClient = (id, data)           => http.put(`/crm/clients/${encodeURIComponent(id)}`, data)
export const deleteClient = (id)                 => http.delete(`/crm/clients/${encodeURIComponent(id)}`)

// ── Products ─────────────────────────────────────────────────────────────
export const listProducts  = (params = {})       => http.get('/crm/products', { params })
export const getProduct    = (id)                => http.get(`/crm/products/${encodeURIComponent(id)}`)
export const createProduct = (data)              => http.post('/crm/products', data)
export const updateProduct = (id, data)          => http.put(`/crm/products/${encodeURIComponent(id)}`, data)
export const deleteProduct = (id)                => http.delete(`/crm/products/${encodeURIComponent(id)}`)

// ── Stock ────────────────────────────────────────────────────────────────
export const listStock     = (params = {})       => http.get('/crm/stock', { params })
export const receiveStock  = (data)              => http.post('/crm/stock/receive', data)
export const adjustStock   = (data)              => http.post('/crm/stock/adjust', data)

// ── Orders ───────────────────────────────────────────────────────────────
export const listOrders  = (params = {})         => http.get('/crm/orders', { params })
export const getOrder    = (orderNumber)         => http.get(`/crm/orders/${encodeURIComponent(orderNumber)}`)
export const createOrder = (data)                => http.post('/crm/orders', data)
export const updateOrder = (orderNumber, data)   => http.put(`/crm/orders/${encodeURIComponent(orderNumber)}`, data)
