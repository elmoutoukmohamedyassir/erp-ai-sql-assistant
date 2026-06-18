import { useState, useEffect, useCallback } from 'react'
import { getHealth } from '../services/api'

export function useHealth(enabled = true) {
  const [status, setStatus] = useState('checking')

  const check = useCallback(async () => {
    if (!enabled) { setStatus('ok'); return }
    try { await getHealth(); setStatus('ok') }
    catch { setStatus('err') }
  }, [enabled])

  useEffect(() => {
    check()
    const id = setInterval(check, 30_000)
    return () => clearInterval(id)
  }, [check])

  return { status, check }
}