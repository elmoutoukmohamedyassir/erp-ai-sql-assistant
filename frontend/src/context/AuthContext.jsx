import { createContext, useContext, useState, useCallback } from 'react'

const AuthContext = createContext(null)

const TOKEN_KEY = 'erp_token'
const USER_KEY  = 'erp_user'

function loadStored() {
  try {
    const token = sessionStorage.getItem(TOKEN_KEY)
    const user  = JSON.parse(sessionStorage.getItem(USER_KEY) || 'null')
    if (token && user) return { token, user }
  } catch { /* ignore */ }
  return { token: null, user: null }
}

export function AuthProvider({ children }) {
  const stored = loadStored()
  const [token, setToken] = useState(stored.token)
  const [user,  setUser]  = useState(stored.user)   // { username, role }

  const login = useCallback((tokenStr, userData) => {
    sessionStorage.setItem(TOKEN_KEY, tokenStr)
    sessionStorage.setItem(USER_KEY,  JSON.stringify(userData))
    setToken(tokenStr)
    setUser(userData)
  }, [])

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }, [])

  const isAdmin = user?.role === 'admin'
  const isAuth  = !!token

  return (
    <AuthContext.Provider value={{ token, user, isAuth, isAdmin, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}