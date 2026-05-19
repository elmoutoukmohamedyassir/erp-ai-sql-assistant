import axios from 'axios'

const http = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 120_000,
})

http.interceptors.response.use(
  r => r.data,
  e => Promise.reject(new Error(
    e?.response?.data?.detail || e?.response?.data?.message || e?.message || 'Unknown error'
  ))
)

export const getHealth  = ()           => http.get('/health')
export const getTables  = ()           => http.get('/tables')
export const postRebuild= ()           => http.post('/rebuild')
export const postAsk    = (q, top_k=8) => http.post('/ask', { question: q, top_k })