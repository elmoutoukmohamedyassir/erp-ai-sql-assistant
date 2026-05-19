import { useState, useEffect, useCallback } from 'react'
import { getHealth } from '../services/api'

export function useHealth() {
  const [status, setStatus] = useState('checking')

  const check = useCallback(async () => {
    try { await getHealth(); setStatus('ok') }
    catch { setStatus('err') }
  }, [])

  useEffect(() => {
    check()
    const id = setInterval(check, 30_000)
    return () => clearInterval(id)
  }, [check])

  return { status, check }
}