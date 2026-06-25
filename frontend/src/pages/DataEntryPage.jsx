import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { toast } from 'react-hot-toast'
import {
  Table2, PlusCircle, Edit3, ChevronDown, AlertTriangle,
  CheckCircle2, XCircle, Loader2, Search, Eye, Play,
  History, X, Info, RefreshCw,
} from 'lucide-react'
import {
  getAllTables, getTableMetadata,
  previewCreate, previewUpdate, executeRecord,
} from '../services/api'

// ─── tiny shared primitives ────────────────────────────────────────────────

const Card = ({ children, style = {} }) => (
  <div style={{
    background: 'var(--card)', border: '1px solid var(--border)',
    borderRadius: 10, padding: '16px 18px', ...style,
  }}>
    {children}
  </div>
)

const Label = ({ children, required }) => (
  <label style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600,
    letterSpacing: '.04em', textTransform: 'uppercase', display: 'flex',
    alignItems: 'center', gap: 4 }}>
    {children}
    {required && <span style={{ color: 'var(--red)', fontSize: 13 }}>*</span>}
  </label>
)

const Tag = ({ children, color = 'var(--dim)', bg = 'rgba(107,120,136,.1)' }) => (
  <span style={{
    fontSize: 10, fontWeight: 700, letterSpacing: '.06em',
    textTransform: 'uppercase', padding: '2px 7px', borderRadius: 99,
    color, background: bg, border: `1px solid ${color}22`,
  }}>{children}</span>
)

const inputStyle = {
  width: '100%', boxSizing: 'border-box',
  padding: '7px 11px',
  background: 'var(--bg)', border: '1px solid var(--border2)',
  borderRadius: 7, color: 'var(--text)',
  fontFamily: 'Outfit, sans-serif', fontSize: 13, outline: 'none',
}

// ─── TableSelector ─────────────────────────────────────────────────────────

function TableSelector({ tables, selected, onSelect }) {
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)

  const filtered = tables.filter(t =>
    t.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          width: '100%', padding: '9px 13px',
          background: 'var(--card)', border: '1px solid var(--border)',
          borderRadius: 8, color: selected ? 'var(--text)' : 'var(--dim)',
          fontFamily: 'IBM Plex Mono, monospace', fontSize: 13, cursor: 'pointer',
          transition: 'border-color .15s',
        }}
        onMouseEnter={e => e.currentTarget.style.borderColor = 'rgba(56,209,240,.4)'}
        onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Table2 size={13} color="var(--cyan)" />
          {selected || 'Select a table…'}
        </span>
        <ChevronDown size={13} color="var(--dim)"
          style={{ transform: open ? 'rotate(180deg)' : 'none', transition: '.15s' }} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.12 }}
            style={{
              position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0, zIndex: 50,
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 9, boxShadow: '0 12px 40px rgba(0,0,0,.5)',
              maxHeight: 320, display: 'flex', flexDirection: 'column', overflow: 'hidden',
            }}
          >
            <div style={{ padding: '10px 10px 6px', position: 'relative' }}>
              <Search size={12} style={{ position: 'absolute', left: 20, top: '50%',
                transform: 'translateY(-2px)', color: 'var(--dim)' }} />
              <input
                autoFocus
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search tables…"
                style={{ ...inputStyle, paddingLeft: 28, fontSize: 12 }}
              />
            </div>
            <div style={{ overflowY: 'auto', padding: '0 6px 8px' }}>
              {filtered.length === 0 ? (
                <p style={{ fontSize: 12, color: 'var(--dim)', padding: '8px 10px' }}>
                  No tables match "{search}"
                </p>
              ) : filtered.map(t => (
                <button
                  key={t}
                  onClick={() => { onSelect(t); setOpen(false); setSearch('') }}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left',
                    padding: '7px 10px', background: selected === t ? 'rgba(56,209,240,.07)' : 'transparent',
                    border: 'none', borderRadius: 6,
                    color: selected === t ? 'var(--cyan)' : 'var(--muted)',
                    fontFamily: 'IBM Plex Mono, monospace', fontSize: 12, cursor: 'pointer',
                    transition: 'all .1s',
                  }}
                  onMouseEnter={e => { if (selected !== t) e.currentTarget.style.background = 'rgba(255,255,255,.04)' }}
                  onMouseLeave={e => { if (selected !== t) e.currentTarget.style.background = 'transparent' }}
                >
                  {t}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─── DynamicForm ────────────────────────────────────────────────────────────

function DynamicForm({ metadata, values, onChange, mode }) {
  // mode: 'create' | 'update'
  // For UPDATE: "where" section uses separate state handled by parent

  const requiredSet = new Set(metadata.required_columns.map(c => c.toUpperCase()))
  const identitySet = new Set(metadata.identity_columns.map(c => c.toUpperCase()))
  const pkSet       = new Set(metadata.primary_keys.map(c => c.toUpperCase()))

  const showCol = (col) => {
    if (mode === 'create') return !identitySet.has(col.name.toUpperCase())
    return true // update: show all (identity cols are read-only)
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
      {metadata.columns.filter(showCol).map(col => {
        const upper     = col.name.toUpperCase()
        const isReq     = requiredSet.has(upper) && mode === 'create'
        const isIdent   = identitySet.has(upper)
        const isPK      = pkSet.has(upper)
        const readOnly  = isIdent

        const isDate    = col.data_type.includes('date') || col.data_type.includes('time')
        const isNum     = ['int','bigint','smallint','tinyint','decimal','numeric','float','real','money','smallmoney'].includes(col.data_type)
        const isBool    = col.data_type === 'bit'

        return (
          <div key={col.name} style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Label required={isReq}>{col.name}</Label>
              <div style={{ display: 'flex', gap: 4 }}>
                {isPK  && <Tag color="#f0c050" bg="rgba(240,192,80,.08)">PK</Tag>}
                {isIdent && <Tag color="var(--dim)">ID</Tag>}
                {!col.nullable && !isIdent && mode === 'create' && (
                  <Tag color="var(--red)" bg="rgba(240,80,80,.08)">required</Tag>
                )}
              </div>
            </div>

            <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: -3 }}>
              {col.data_type}{col.max_length ? `(${col.max_length})` : ''}
              {col.default ? ` · default: ${col.default}` : ''}
            </div>

            {isBool ? (
              <select
                disabled={readOnly}
                value={values[col.name] ?? ''}
                onChange={e => onChange(col.name, e.target.value === '' ? null : e.target.value === '1')}
                style={{ ...inputStyle, opacity: readOnly ? 0.45 : 1, cursor: readOnly ? 'not-allowed' : 'default' }}
              >
                <option value="">— null —</option>
                <option value="1">True (1)</option>
                <option value="0">False (0)</option>
              </select>
            ) : (
              <input
                type={isDate ? 'datetime-local' : isNum ? 'number' : 'text'}
                disabled={readOnly}
                placeholder={readOnly ? '(auto-generated)' : col.nullable ? 'optional' : 'required'}
                value={values[col.name] ?? ''}
                onChange={e => {
                  const v = e.target.value
                  onChange(col.name, v === '' ? null : isNum ? Number(v) : v)
                }}
                style={{
                  ...inputStyle,
                  opacity: readOnly ? 0.45 : 1,
                  cursor: readOnly ? 'not-allowed' : 'text',
                  borderColor: isReq && (values[col.name] === '' || values[col.name] == null)
                    ? 'rgba(240,80,80,.4)' : 'var(--border2)',
                }}
                onFocus={e => { if (!readOnly) e.target.style.borderColor = 'rgba(56,209,240,.4)' }}
                onBlur={e => {
                  const isReqMissing = isReq && (values[col.name] === '' || values[col.name] == null)
                  e.target.style.borderColor = isReqMissing ? 'rgba(240,80,80,.4)' : 'var(--border2)'
                }}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─── PreviewCard ────────────────────────────────────────────────────────────

function PreviewCard({ preview, onConfirm, onCancel, executing }) {
  if (!preview) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 6 }}
        style={{
          position: 'fixed', inset: 0, zIndex: 100,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(11,15,20,.75)', backdropFilter: 'blur(4px)',
        }}
      >
        <motion.div
          initial={{ scale: .96 }} animate={{ scale: 1 }}
          style={{
            width: '100%', maxWidth: 600, margin: '0 20px',
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 14, overflow: 'hidden',
            boxShadow: '0 24px 80px rgba(0,0,0,.6)',
          }}
        >
          {/* Header */}
          <div style={{
            padding: '14px 18px', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              {preview.valid
                ? <CheckCircle2 size={16} color="var(--green)" />
                : <XCircle      size={16} color="var(--red)" />
              }
              <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--text)' }}>
                {preview.valid ? 'Review before saving' : 'Validation failed'}
              </span>
            </div>
            <button onClick={onCancel} style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--dim)', display: 'flex', padding: 4,
            }}><X size={16} /></button>
          </div>

          <div style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14, maxHeight: '60vh', overflowY: 'auto' }}>

            {/* Operation badge */}
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <Tag
                color={preview.operation === 'INSERT' ? 'var(--green)' : '#f0c050'}
                bg={preview.operation === 'INSERT' ? 'rgba(61,185,85,.1)' : 'rgba(240,192,80,.1)'}
              >
                {preview.operation}
              </Tag>
              <span style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: 13,
                color: 'var(--cyan)', fontWeight: 600 }}>
                {preview.table}
              </span>
            </div>

            {/* Errors */}
            {preview.errors?.length > 0 && (
              <div style={{
                padding: '10px 12px', background: 'rgba(240,80,80,.07)',
                border: '1px solid rgba(240,80,80,.2)', borderRadius: 8,
              }}>
                {preview.errors.map((e, i) => (
                  <div key={i} style={{ display: 'flex', gap: 7, alignItems: 'flex-start',
                    fontSize: 12, color: 'var(--red)', lineHeight: 1.5 }}>
                    <XCircle size={12} style={{ marginTop: 2, flexShrink: 0 }} /> {e}
                  </div>
                ))}
              </div>
            )}

            {/* Warnings */}
            {preview.warnings?.length > 0 && (
              <div style={{
                padding: '10px 12px', background: 'rgba(240,192,80,.07)',
                border: '1px solid rgba(240,192,80,.2)', borderRadius: 8,
              }}>
                {preview.warnings.map((w, i) => (
                  <div key={i} style={{ display: 'flex', gap: 7, alignItems: 'flex-start',
                    fontSize: 12, color: '#f0c050', lineHeight: 1.5 }}>
                    <AlertTriangle size={12} style={{ marginTop: 2, flexShrink: 0 }} /> {w}
                  </div>
                ))}
              </div>
            )}

            {/* Generated SQL */}
            {preview.generated_sql && (
              <div>
                <div style={{ fontSize: 11, color: 'var(--dim)', marginBottom: 6,
                  textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 700 }}>
                  Generated SQL (parameterized)
                </div>
                <pre style={{
                  margin: 0, padding: '10px 12px',
                  background: 'var(--bg)', border: '1px solid var(--border)',
                  borderRadius: 7, fontFamily: 'IBM Plex Mono, monospace',
                  fontSize: 12, color: 'var(--cyan)', overflowX: 'auto',
                  lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                }}>
                  {preview.generated_sql}
                </pre>
                <p style={{ fontSize: 11, color: 'var(--dim)', marginTop: 6, display: 'flex', gap: 5 }}>
                  <Info size={11} style={{ marginTop: 1 }} />
                  Values shown inline for review. Execution uses bind parameters — no SQL injection.
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div style={{
            padding: '12px 18px', borderTop: '1px solid var(--border)',
            display: 'flex', justifyContent: 'flex-end', gap: 10,
          }}>
            <button
              onClick={onCancel}
              style={{
                padding: '7px 16px', background: 'transparent',
                border: '1px solid var(--border)', borderRadius: 7,
                color: 'var(--muted)', fontSize: 13, cursor: 'pointer',
                fontFamily: 'Outfit, sans-serif',
              }}
            >
              Cancel
            </button>
            {preview.valid && (
              <button
                onClick={onConfirm}
                disabled={executing}
                style={{
                  padding: '7px 18px', background: 'var(--cyan)',
                  border: 'none', borderRadius: 7,
                  color: '#0b0f14', fontSize: 13, fontWeight: 700,
                  cursor: executing ? 'wait' : 'pointer',
                  fontFamily: 'Outfit, sans-serif',
                  display: 'flex', alignItems: 'center', gap: 7,
                  opacity: executing ? 0.75 : 1,
                }}
              >
                {executing ? <Loader2 size={13} className="spin" /> : <Play size={13} />}
                {executing ? 'Saving…' : 'Confirm & Save'}
              </button>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

// ─── RecordHistory ──────────────────────────────────────────────────────────

function RecordHistory({ history }) {
  if (history.length === 0) return null

  return (
    <Card>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 12 }}>
        <History size={13} color="var(--cyan)" />
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>
          Session History
        </span>
        <span style={{ fontSize: 11, color: 'var(--dim)' }}>({history.length})</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {[...history].reverse().map((h, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 12px',
              background: h.success ? 'rgba(61,185,85,.05)' : 'rgba(240,80,80,.05)',
              border: `1px solid ${h.success ? 'rgba(61,185,85,.15)' : 'rgba(240,80,80,.15)'}`,
              borderRadius: 7,
            }}
          >
            {h.success
              ? <CheckCircle2 size={13} color="var(--green)" />
              : <XCircle      size={13} color="var(--red)" />
            }
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', gap: 7, alignItems: 'center' }}>
                <Tag
                  color={h.operation === 'INSERT' ? 'var(--green)' : '#f0c050'}
                  bg={h.operation === 'INSERT' ? 'rgba(61,185,85,.1)' : 'rgba(240,192,80,.1)'}
                >
                  {h.operation}
                </Tag>
                <span style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: 12, color: 'var(--cyan)' }}>
                  {h.table}
                </span>
                {h.success && (
                  <span style={{ fontSize: 11, color: 'var(--green)' }}>
                    {h.rows_affected} row(s) affected · {h.duration_ms}ms
                  </span>
                )}
              </div>
              {h.error && (
                <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 3 }}>{h.error}</div>
              )}
            </div>
            <span style={{ fontSize: 11, color: 'var(--dim)', whiteSpace: 'nowrap' }}>
              {new Date(h.ts).toLocaleTimeString()}
            </span>
          </motion.div>
        ))}
      </div>
    </Card>
  )
}

// ─── Main DataEntryPage ──────────────────────────────────────────────────────

export function DataEntryPage() {
  const [mode, setMode]           = useState('create')   // 'create' | 'update'
  const [tables, setTables]       = useState([])
  const [tablesLoading, setTablesLoading] = useState(true)
  const [selectedTable, setSelectedTable] = useState(null)
  const [metadata, setMetadata]   = useState(null)
  const [metaLoading, setMetaLoading] = useState(false)
  const [values, setValues]       = useState({})
  const [whereValues, setWhereValues] = useState({})
  const [preview, setPreview]     = useState(null)
  const [previewing, setPreviewing] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [history, setHistory]     = useState([])

  // Load table list on mount
  useEffect(() => {
    setTablesLoading(true)
    getAllTables()
      .then(d => setTables(d.tables || []))
      .catch(e => toast.error(`Failed to load tables: ${e.message}`))
      .finally(() => setTablesLoading(false))
  }, [])

  // Load metadata when a table is selected
  useEffect(() => {
    if (!selectedTable) { setMetadata(null); return }
    setMetaLoading(true)
    setValues({})
    setWhereValues({})
    setPreview(null)
    getTableMetadata(selectedTable)
      .then(d => setMetadata(d))
      .catch(e => toast.error(`Metadata error: ${e.message}`))
      .finally(() => setMetaLoading(false))
  }, [selectedTable])

  const handleValueChange = useCallback((col, val) => {
    setValues(prev => ({ ...prev, [col]: val }))
  }, [])

  const handleWhereChange = useCallback((col, val) => {
    setWhereValues(prev => ({ ...prev, [col]: val }))
  }, [])

  const handlePreview = async () => {
    const cleanValues = Object.fromEntries(
      Object.entries(values).filter(([, v]) => v !== '' && v != null)
    )
    const cleanWhere = Object.fromEntries(
      Object.entries(whereValues).filter(([, v]) => v !== '' && v != null)
    )

    if (Object.keys(cleanValues).length === 0) {
      toast.error('Fill in at least one field before previewing.')
      return
    }
    if (mode === 'update' && Object.keys(cleanWhere).length === 0) {
      toast.error('Specify at least one WHERE condition to identify the row to update.')
      return
    }

    setPreviewing(true)
    try {
      const result = mode === 'create'
        ? await previewCreate(selectedTable, cleanValues)
        : await previewUpdate(selectedTable, cleanWhere, cleanValues)
      setPreview(result)
    } catch (e) {
      toast.error(`Preview failed: ${e.message}`)
    } finally {
      setPreviewing(false)
    }
  }

  const handleExecute = async () => {
    if (!preview?.valid) return
    setExecuting(true)
    try {
      const result = await executeRecord(
        preview.operation,
        preview.table,
        preview.values,
        preview.where || undefined,
      )
      const entry = {
        ts: Date.now(),
        operation: result.operation,
        table: result.table,
        success: result.executed,
        rows_affected: result.rows_affected,
        duration_ms: result.duration_ms,
        error: result.error,
      }
      setHistory(h => [...h, entry])

      if (result.executed) {
        toast.success(`${result.operation} saved — ${result.rows_affected} row(s) affected`)
        setValues({})
        setWhereValues({})
        setPreview(null)
      } else {
        toast.error(`Execute failed: ${result.error}`)
        setPreview(null)
      }
    } catch (e) {
      toast.error(`Execute error: ${e.message}`)
    } finally {
      setExecuting(false)
    }
  }

  const identitySet = new Set((metadata?.identity_columns || []).map(c => c.toUpperCase()))

  return (
    <div style={{
      padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16,
      height: '100%', overflowY: 'auto',
    }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: 'var(--text)',
            display: 'flex', alignItems: 'center', gap: 8 }}>
            <Edit3 size={16} color="var(--cyan)" /> Data Entry
          </h2>
          <p style={{ margin: '3px 0 0', fontSize: 12, color: 'var(--dim)' }}>
            Create or update records directly in database tables.
          </p>
        </div>

        {/* Mode toggle */}
        <div style={{
          display: 'flex', gap: 2, padding: 3,
          background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 9,
        }}>
          {['create', 'update'].map(m => (
            <button
              key={m}
              onClick={() => { setMode(m); setPreview(null) }}
              style={{
                padding: '5px 14px', border: 'none', borderRadius: 7,
                background: mode === m ? 'rgba(56,209,240,.12)' : 'transparent',
                color: mode === m ? 'var(--cyan)' : 'var(--dim)',
                fontFamily: 'Outfit, sans-serif', fontSize: 12, fontWeight: 600,
                cursor: 'pointer', transition: 'all .15s',
                display: 'flex', alignItems: 'center', gap: 5,
              }}
            >
              {m === 'create' ? <PlusCircle size={12} /> : <Edit3 size={12} />}
              {m === 'create' ? 'Create Record' : 'Update Record'}
            </button>
          ))}
        </div>
      </div>

      {/* ── Table Selector ── */}
      <Card>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Label>Select Table</Label>
          {tablesLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8,
              padding: '10px 13px', background: 'var(--bg)',
              border: '1px solid var(--border)', borderRadius: 8 }}>
              <Loader2 size={13} color="var(--dim)" className="spin" />
              <span style={{ fontSize: 13, color: 'var(--dim)' }}>Loading tables…</span>
            </div>
          ) : (
            <TableSelector
              tables={tables}
              selected={selectedTable}
              onSelect={setSelectedTable}
            />
          )}
        </div>
      </Card>

      {/* ── Form ── */}
      <AnimatePresence>
        {selectedTable && (
          <motion.div
            key={selectedTable + mode}
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{ display: 'flex', flexDirection: 'column', gap: 14 }}
          >
            {metaLoading ? (
              <Card style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '18px 20px' }}>
                <Loader2 size={15} color="var(--cyan)" className="spin" />
                <span style={{ fontSize: 13, color: 'var(--muted)' }}>
                  Loading schema for <strong style={{ fontFamily: 'IBM Plex Mono, monospace' }}>{selectedTable}</strong>…
                </span>
              </Card>
            ) : metadata ? (
              <>
                {/* UPDATE: WHERE section */}
                {mode === 'update' && (
                  <Card>
                    <div style={{ marginBottom: 14 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
                        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)' }}>
                          Identify Row
                        </span>
                        <Tag color="#f0c050" bg="rgba(240,192,80,.1)">WHERE</Tag>
                      </div>
                      <p style={{ margin: 0, fontSize: 12, color: 'var(--dim)' }}>
                        Specify which row(s) to update. Use primary key columns for precision.
                      </p>
                    </div>
                    <DynamicForm
                      metadata={metadata}
                      values={whereValues}
                      onChange={handleWhereChange}
                      mode="where"
                    />
                  </Card>
                )}

                {/* Values section */}
                <Card>
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
                      <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)' }}>
                        {mode === 'create' ? 'Record Values' : 'New Values'}
                      </span>
                      <span style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: 13, color: 'var(--cyan)' }}>
                        {metadata.table}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 11, color: 'var(--dim)' }}>
                        {metadata.columns.length} columns ·
                        {metadata.required_columns.length} required ·
                        {metadata.identity_columns.length} auto-generated
                      </span>
                    </div>
                  </div>

                  <DynamicForm
                    metadata={metadata}
                    values={values}
                    onChange={handleValueChange}
                    mode={mode === 'create' ? 'create' : 'update'}
                  />

                  {/* Action buttons */}
                  <div style={{ marginTop: 18, display: 'flex', alignItems: 'center',
                    justifyContent: 'flex-end', gap: 10, flexWrap: 'wrap' }}>
                    <button
                      onClick={() => { setValues({}); setWhereValues({}); setPreview(null) }}
                      style={{
                        padding: '7px 14px', background: 'transparent',
                        border: '1px solid var(--border)', borderRadius: 7,
                        color: 'var(--muted)', fontSize: 13, cursor: 'pointer',
                        fontFamily: 'Outfit, sans-serif', display: 'flex', alignItems: 'center', gap: 6,
                      }}
                    >
                      <RefreshCw size={12} /> Clear
                    </button>
                    <button
                      onClick={handlePreview}
                      disabled={previewing}
                      style={{
                        padding: '7px 18px',
                        background: 'rgba(56,209,240,.1)',
                        border: '1px solid rgba(56,209,240,.3)',
                        borderRadius: 7, color: 'var(--cyan)',
                        fontSize: 13, fontWeight: 700,
                        cursor: previewing ? 'wait' : 'pointer',
                        fontFamily: 'Outfit, sans-serif',
                        display: 'flex', alignItems: 'center', gap: 7,
                        transition: 'all .15s',
                      }}
                      onMouseEnter={e => !previewing && (e.currentTarget.style.background = 'rgba(56,209,240,.18)')}
                      onMouseLeave={e => e.currentTarget.style.background = 'rgba(56,209,240,.1)'}
                    >
                      {previewing
                        ? <Loader2 size={13} className="spin" />
                        : <Eye size={13} />
                      }
                      {previewing ? 'Validating…' : 'Preview & Validate'}
                    </button>
                  </div>
                </Card>
              </>
            ) : null}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── History ── */}
      <RecordHistory history={history} />

      {/* ── Preview Modal ── */}
      {preview && (
        <PreviewCard
          preview={preview}
          onConfirm={handleExecute}
          onCancel={() => setPreview(null)}
          executing={executing}
        />
      )}

      {/* Spinner keyframe */}
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        .spin { animation: spin .8s linear infinite; }
      `}</style>
    </div>
  )
}
