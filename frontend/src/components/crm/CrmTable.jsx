import { Loader2, Inbox } from 'lucide-react'
import { EmptyState } from './CrmUi'

/**
 * Generic business-object table.
 * columns: [{ key, label, width?, render?(row) }]
 * rows: array of business objects (already plain JSON from crmApi)
 * actions: (row) => ReactNode   — rendered in the trailing cell
 */
export default function CrmTable({ columns, rows, loading, emptyTitle = 'Nothing here yet', emptySubtitle, actions, onRowClick }) {
  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '56px 0', color: 'var(--dim)' }}>
        <Loader2 size={18} className="spin" style={{ marginRight: 8 }} />
        <span style={{ fontSize: 13 }}>Loading…</span>
      </div>
    )
  }

  if (!rows || rows.length === 0) {
    return <EmptyState icon={Inbox} title={emptyTitle} subtitle={emptySubtitle} />
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.key} style={{
                textAlign: 'left', padding: '9px 12px', fontSize: 11, fontWeight: 600,
                letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--dim)',
                borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap', width: col.width,
              }}>
                {col.label}
              </th>
            ))}
            {actions && <th style={{ borderBottom: '1px solid var(--border)', width: 1 }} />}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={row.id || row.order_number || row.product_id || i}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              style={{
                borderBottom: '1px solid var(--border)',
                cursor: onRowClick ? 'pointer' : 'default',
                transition: 'background .1s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'var(--card)' }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
            >
              {columns.map(col => (
                <td key={col.key} style={{ padding: '10px 12px', color: 'var(--text)', verticalAlign: 'middle' }}>
                  {col.render ? col.render(row) : (row[col.key] ?? <span style={{ color: 'var(--dim)' }}>—</span>)}
                </td>
              ))}
              {actions && (
                <td style={{ padding: '10px 12px', textAlign: 'right' }} onClick={e => e.stopPropagation()}>
                  <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                    {actions(row)}
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
