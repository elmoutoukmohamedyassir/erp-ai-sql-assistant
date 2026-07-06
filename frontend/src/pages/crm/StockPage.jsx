import { useEffect, useState, useCallback } from 'react'
import toast from 'react-hot-toast'
import { PackagePlus, SlidersHorizontal } from 'lucide-react'
import * as crmApi from '../../services/crmApi'
import CrmTable from '../../components/crm/CrmTable'
import {
  Card, PrimaryButton, GhostButton, SearchBar, Modal,
  Pagination, FormField, inputStyle,
} from '../../components/crm/CrmUi'

export default function StockPage() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(25)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  const [receiveOpen, setReceiveOpen] = useState(false)
  const [adjustTarget, setAdjustTarget] = useState(null)
  const [receiveForm, setReceiveForm] = useState({ product_id: '', quantity: '', note: '' })
  const [adjustForm, setAdjustForm] = useState({ new_quantity: '', reason: '' })
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await crmApi.listStock({ search: search || undefined, page, page_size: pageSize })
      setRows(res.items)
      setTotal(res.total)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [search, page, pageSize])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [search])

  function openAdjust(row) {
    setAdjustTarget(row)
    setAdjustForm({ new_quantity: row.quantity ?? '', reason: '' })
  }

  async function submitReceive(e) {
    e.preventDefault()
    if (!receiveForm.product_id.trim() || !receiveForm.quantity) {
      toast.error('Product reference and quantity are required')
      return
    }
    setSaving(true)
    try {
      await crmApi.receiveStock({
        product_id: receiveForm.product_id.trim(),
        quantity: Number(receiveForm.quantity),
        note: receiveForm.note || undefined,
      })
      toast.success('Stock received')
      setReceiveOpen(false)
      setReceiveForm({ product_id: '', quantity: '', note: '' })
      load()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function submitAdjust(e) {
    e.preventDefault()
    setSaving(true)
    try {
      await crmApi.adjustStock({
        product_id: adjustTarget.product_id,
        new_quantity: Number(adjustForm.new_quantity),
        reason: adjustForm.reason || undefined,
      })
      toast.success('Stock adjusted')
      setAdjustTarget(null)
      load()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  const columns = [
    { key: 'product_name', label: 'Product', render: r => <span style={{ fontWeight: 600 }}>{r.product_name || r.product_id}</span> },
    { key: 'product_id', label: 'Reference' },
    { key: 'quantity', label: 'Quantity in stock', render: r => (
      <span style={{ fontWeight: 600, color: (r.quantity ?? 0) <= 0 ? 'var(--red)' : 'var(--text)' }}>
        {r.quantity ?? 0}
      </span>
    ) },
  ]

  return (
    <div className="fadein" style={{ display: 'flex', flexDirection: 'column', gap: 16, height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 19, fontWeight: 700, margin: 0, color: 'var(--text)' }}>Stock</h1>
          <p style={{ fontSize: 12.5, color: 'var(--muted)', margin: '3px 0 0' }}>Current stock levels by product</p>
        </div>
        <PrimaryButton onClick={() => setReceiveOpen(true)}><PackagePlus size={14} /> Receive stock</PrimaryButton>
      </div>

      <Card style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 }}>
        <div style={{ padding: 14, borderBottom: '1px solid var(--border)' }}>
          <SearchBar value={search} onChange={setSearch} placeholder="Search stock by product name or reference…" />
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 14px' }}>
          <CrmTable
            columns={columns}
            rows={rows}
            loading={loading}
            emptyTitle="No stock records yet"
            emptySubtitle="Receive stock for a product to see it here."
            actions={row => (
              <GhostButton onClick={() => openAdjust(row)}>
                <SlidersHorizontal size={12} /> Adjust
              </GhostButton>
            )}
          />
        </div>
        <div style={{ padding: 12, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination page={page} pageSize={pageSize} total={total} onPageChange={setPage} />
        </div>
      </Card>

      <Modal open={receiveOpen} onClose={() => setReceiveOpen(false)} title="Receive stock" width={420}>
        <form onSubmit={submitReceive} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <FormField label="Product reference" required>
            <input
              style={inputStyle} autoFocus
              placeholder="e.g. ART000012"
              value={receiveForm.product_id}
              onChange={e => setReceiveForm({ ...receiveForm, product_id: e.target.value })}
            />
          </FormField>
          <FormField label="Quantity received" required>
            <input
              style={inputStyle} type="number" step="1" min="0"
              value={receiveForm.quantity}
              onChange={e => setReceiveForm({ ...receiveForm, quantity: e.target.value })}
            />
          </FormField>
          <FormField label="Note">
            <input
              style={inputStyle}
              value={receiveForm.note}
              onChange={e => setReceiveForm({ ...receiveForm, note: e.target.value })}
            />
          </FormField>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
            <PrimaryButton type="submit" disabled={saving}>{saving ? 'Saving…' : 'Receive stock'}</PrimaryButton>
          </div>
        </form>
      </Modal>

      <Modal open={!!adjustTarget} onClose={() => setAdjustTarget(null)} title="Adjust stock" width={420}>
        {adjustTarget && (
          <form onSubmit={submitAdjust} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <p style={{ fontSize: 12.5, color: 'var(--muted)', margin: 0 }}>
              {adjustTarget.product_name || adjustTarget.product_id} — current quantity: <strong>{adjustTarget.quantity ?? 0}</strong>
            </p>
            <FormField label="Corrected quantity" required>
              <input
                style={inputStyle} type="number" step="1" min="0" autoFocus
                value={adjustForm.new_quantity}
                onChange={e => setAdjustForm({ ...adjustForm, new_quantity: e.target.value })}
              />
            </FormField>
            <FormField label="Reason">
              <input
                style={inputStyle}
                placeholder="e.g. Stock count correction"
                value={adjustForm.reason}
                onChange={e => setAdjustForm({ ...adjustForm, reason: e.target.value })}
              />
            </FormField>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
              <PrimaryButton type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save adjustment'}</PrimaryButton>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}
