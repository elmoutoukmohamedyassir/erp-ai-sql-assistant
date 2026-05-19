import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Loader2, RotateCcw, Table2, Clock, Hash } from 'lucide-react'
import { postAsk } from '../services/api'
import { SqlBlock } from '../components/SqlBlock'
import { DataTable } from '../components/DataTable'
import { Badge, ErrBox, WarnBox, Spinner } from '../components/Ui'

const SUGGESTIONS = [
  'Show all customers',
  'List payment methods',
  'Top 10 articles by price',
  'Stock levels by depot',
  'Invoices this month',
  'List all journals',
]

export function AskPage() {
  const [value,   setValue]   = useState('')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState([])
  const textareaRef = useRef(null)
  const bottomRef   = useRef(null)

  // auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 130) + 'px'
  }, [value])

  // scroll to latest
  useEffect(() => {
    if (results.length) setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 80)
  }, [results])

  const submit = async (q) => {
    q = q?.trim() || value.trim()
    if (!q || loading) return
    setValue('')
    setLoading(true)
    try {
      const d = await postAsk(q)
      setResults(prev => [...prev, { q, d }])
    } catch (e) {
      setResults(prev => [...prev, { q, d: { error: e.message } }])
    } finally {
      setLoading(false)
    }
  }

  const onKey = e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>

      {/* ── scrollable results ── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
        {results.length === 0 && !loading && (
          <motion.div
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12, paddingBottom: 40 }}
          >
            <div style={{
              width: 44, height: 44, borderRadius: 12,
              background: 'rgba(56,209,240,.08)', border: '1px solid rgba(56,209,240,.18)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Hash size={20} color="var(--cyan)" />
            </div>
            <p style={{ color: 'var(--muted)', fontSize: 13 }}>Ask anything about your Sage 100 data</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, justifyContent: 'center', maxWidth: 480 }}>
              {SUGGESTIONS.map(s => (
                <button key={s} onClick={() => submit(s)} style={{
                  padding: '5px 13px', background: 'var(--card)',
                  border: '1px solid var(--border)', borderRadius: 99,
                  color: 'var(--muted)', fontSize: 12, cursor: 'pointer',
                  transition: 'all .15s', fontFamily: 'Outfit, sans-serif',
                }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(56,209,240,.35)'; e.currentTarget.style.color = 'var(--text)' }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--muted)' }}
                >
                  {s}
                </button>
              ))}
            </div>
          </motion.div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 820, margin: '0 auto' }}>
          <AnimatePresence>
            {results.map(({ q, d }, i) => (
              <ResultCard key={i} question={q} data={d} onRerun={() => submit(q)} />
            ))}
          </AnimatePresence>

          {loading && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              style={{
                background: 'var(--card)', border: '1px solid var(--border)',
                borderRadius: 10, padding: '14px 16px',
                display: 'flex', alignItems: 'center', gap: 10,
              }}
            >
              <Spinner />
              <span style={{ color: 'var(--muted)', fontSize: 13 }}>Generating SQL…</span>
            </motion.div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* ── input bar ── */}
      <div style={{
        borderTop: '1px solid var(--border)', background: 'var(--surface)',
        padding: '14px 24px',
      }}>
        <div style={{ maxWidth: 820, margin: '0 auto' }}>
          <motion.div
            animate={{ boxShadow: '0 0 0 1px var(--border)' }}
            whileFocusWithin={{ boxShadow: '0 0 0 1.5px rgba(56,209,240,.4), 0 0 20px rgba(56,209,240,.06)' }}
            style={{
              display: 'flex', alignItems: 'flex-end', gap: 10,
              background: 'var(--card)', borderRadius: 10, padding: '10px 12px',
            }}
          >
            <textarea
              ref={textareaRef}
              value={value}
              onChange={e => setValue(e.target.value)}
              onKeyDown={onKey}
              placeholder="Ask anything about your ERP data… (Enter to send, Shift+Enter for newline)"
              rows={1}
              style={{
                flex: 1, background: 'transparent', border: 'none', outline: 'none',
                color: 'var(--text)', fontFamily: 'Outfit, sans-serif', fontSize: 14,
                lineHeight: 1.55, resize: 'none', minHeight: 24, maxHeight: 130,
              }}
            />
            <button
              onClick={() => submit()}
              disabled={!value.trim() || loading}
              style={{
                width: 34, height: 34, borderRadius: 8, border: 'none',
                background: !value.trim() || loading ? 'var(--border2)' : 'var(--cyan)',
                color: !value.trim() || loading ? 'var(--dim)' : '#0a0c0f',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: !value.trim() || loading ? 'not-allowed' : 'pointer',
                transition: 'all .15s', flexShrink: 0,
              }}
            >
              {loading ? <Loader2 size={15} style={{ animation: 'spin .7s linear infinite' }} /> : <Send size={15} />}
            </button>
          </motion.div>
          <p style={{ fontSize: 11, color: 'var(--dim)', marginTop: 6, paddingLeft: 2 }}>
            Enter to send · Shift+Enter for newline
          </p>
        </div>
      </div>
    </div>
  )
}

function ResultCard({ question, data: d, onRerun }) {
  const [open, setOpen] = useState(true)
  // Backend returns flat: { columns, rows, duration_ms, sql, error, ... }
  const rows = d.rows?.length ?? d.data?.rows?.length ?? 0
  const ms   = d.duration_ms ?? d.data?.duration_ms
  const atts = d.attempts ?? 1

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}
    >
      {/* head */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
        padding: '11px 14px', borderBottom: '1px solid var(--border)', gap: 12,
      }}>
        <span style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.45, flex: 1 }}>{question}</span>
        <div style={{ display: 'flex', gap: 5, alignItems: 'center', flexShrink: 0, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {d.error
            ? <Badge color="red">error</Badge>
            : rows > 0
              ? <Badge color="green">{rows} rows</Badge>
              : d.sql ? <Badge color="gray">0 rows</Badge> : null
          }
          {ms != null && <Badge color="cyan"><Clock size={9} style={{ marginRight: 3 }} />{ms}ms</Badge>}
          {atts > 1 && <Badge color="amber">{atts} attempts</Badge>}
          <button
            onClick={onRerun}
            title="Re-run"
            style={{
              background: 'transparent', border: '1px solid var(--border)',
              borderRadius: 5, padding: '2px 7px', cursor: 'pointer',
              color: 'var(--dim)', display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 11, fontFamily: 'Outfit, sans-serif', transition: 'all .15s',
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--text)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--dim)'}
          >
            <RotateCcw size={10} /> Re-run
          </button>
          <button
            onClick={() => setOpen(o => !o)}
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer',
              color: 'var(--dim)', fontSize: 11, fontFamily: 'Outfit, sans-serif',
            }}
          >
            {open ? '▲' : '▼'}
          </button>
        </div>
      </div>

      {/* body */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: 12 }}>

              {d.error && <ErrBox>{d.error}</ErrBox>}

              {d.warnings?.map((w, i) => <WarnBox key={i}>{w}</WarnBox>)}

              {/* retrieved tables */}
              {d.retrieved_tables?.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                  {d.retrieved_tables.map(t => (
                    <span key={t} style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4,
                      padding: '2px 8px', borderRadius: 99,
                      background: 'rgba(107,120,136,.07)', border: '1px solid var(--border2)',
                      fontFamily: 'IBM Plex Mono, monospace', fontSize: 10, color: 'var(--muted)',
                    }}>
                      <Table2 size={9} /> {t}
                    </span>
                  ))}
                </div>
              )}

              {d.sql && <SqlBlock sql={d.sql} />}

              {(d.rows?.length > 0 || d.data?.rows?.length > 0) && (
                <DataTable
                  columns={d.columns ?? d.data?.columns ?? []}
                  rows={d.rows ?? d.data?.rows ?? []}
                />
              )}

              {!d.error && d.sql && !(d.rows?.length || d.data?.rows?.length) && (
                <p style={{ textAlign: 'center', color: 'var(--dim)', fontSize: 12, padding: '10px 0' }}>
                  Query executed — no rows returned
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}