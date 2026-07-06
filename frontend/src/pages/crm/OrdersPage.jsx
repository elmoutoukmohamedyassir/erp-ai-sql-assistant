import { useEffect, useState, useCallback } from 'react'
import toast from 'react-hot-toast'
import { Plus, Pencil, Eye, X } from 'lucide-react'
import * as crmApi from '../../services/crmApi'
import CrmTable from '../../components/crm/CrmTable'
import ComboSelect from '../../components/crm/ComboSelect'
import {
  Card, PrimaryButton, GhostButton, IconButton, SearchBar, Modal,
  Pagination, FormField, inputStyle,
} from '../../components/crm/CrmUi'

const money = v => (v || v === 0) ? Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'

const emptyLine = () => ({ key: Math.random().toString(36).slice(2), product_id: '', product_label: '', quantity: 1, unit_price: '' })

export default function OrdersPage() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(25)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  const [modalOpen, setModalOpen] = useState(false)
  const [editingNumber, setEditingNumber] = useState(null)
  const [customerId, setCustomerId] = useState('')
  const [customerLabel, setCustomerLabel] = useState('')
  const [reference, setReference] = useState('')
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState([emptyLine()])
  const [saving, setSaving] = useState(false)

  const [detailOrder, setDetailOrder] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await crmApi.listOrders({ search: search || undefined, page, page_size: pageSize })
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

  const fetchCustomers = useCallback(async q => {
    const res = await crmApi.listClients({ search: q || undefined, page: 1, page_size: 10 })
    return res.items.map(c => ({ id: c.id, label: c.name, sublabel: c.city || c.email }))
  }, [])

  const fetchProducts = useCallback(async q => {
    const res = await crmApi.listProducts({ search: q || undefined, page: 1, page_size: 10 })
    return res.items.map(p => ({ id: p.id, label: p.name, sublabel: p.sale_price != null ? `$${money(p.sale_price)}` : p.id }))
  }, [])

  function openCreate() {
    setEditingNumber(null)
    setCustomerId('')
    setCustomerLabel('')
    setReference('')
    setNotes('')
    setLines([emptyLine()])
    setModalOpen(true)
  }

  async function openEdit(order) {
    setEditingNumber(order.order_number)
    setModalOpen(true)
    setDetailLoading(true)
    try {
      const full = await crmApi.getOrder(order.order_number)
      setCustomerId(full.customer_id || '')
      setCustomerLabel(full.customer_name || '')
      setReference(full.reference || '')
      setNotes(full.notes || '')
      setLines(
        full.lines.length
          ? full.lines.map(l => ({
              key: Math.random().toString(36).slice(2),
              product_id: l.product_id, product_label: l.product_name || l.product_id,
              quantity: l.quantity, unit_price: l.unit_price,
            }))
          : [emptyLine()]
      )
    } catch (e) {
      toast.error(e.message)
      setModalOpen(false)
    } finally {
      setDetailLoading(false)
    }
  }

  async function openDetails(order) {
    setDetailOrder({ ...order, lines: null })
    try {
      const full = await crmApi.getOrder(order.order_number)
      setDetailOrder(full)
    } catch (e) {
      toast.error(e.message)
      setDetailOrder(null)
    }
  }

  function updateLine(key, patch) {
    setLines(ls => ls.map(l => (l.key === key ? { ...l, ...patch } : l)))
  }

  function addLine() {
    setLines(ls => [...ls, emptyLine()])
  }

  function removeLine(key) {
    setLines(ls => (ls.length > 1 ? ls.filter(l => l.key !== key) : ls))
  }

  const orderTotal = lines.reduce((sum, l) => {
    const qty = Number(l.quantity) || 0
    const price = Number(l.unit_price) || 0
    return sum + qty * price
  }, 0)

  async function submit(e) {
    e.preventDefault()
    if (!customerId) {
      toast.error('Please select a customer')
      return
    }
    const validLines = lines.filter(l => l.product_id && Number(l.quantity) > 0)
    if (validLines.length === 0) {
      toast.error('Add at least one product line')
      return
    }
    setSaving(true)
    try {
      const payload = {
        customer_id: customerId,
        reference: reference || undefined,
        notes: notes || undefined,
        lines: validLines.map(l => ({
          product_id: l.product_id,
          quantity: Number(l.quantity),
          unit_price: l.unit_price === '' ? undefined : Number(l.unit_price),
        })),
      }
      if (editingNumber) {
        await crmApi.updateOrder(editingNumber, payload)
        toast.success('Order updated')
      } else {
        await crmApi.createOrder(payload)
        toast.success('Order created')
      }
      setModalOpen(false)
      load()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  const columns = [
    { key: 'order_number', label: 'Order #', render: r => <span style={{ fontWeight: 600 }}>{r.order_number}</span> },
    { key: 'customer_name', label: 'Customer' },
    { key: 'date', label: 'Date' },
    { key: 'status', label: 'Status' },
    { key: 'total', label: 'Total', render: r => `$${money(r.total)}` },
  ]

  return (
    <div className="fadein" style={{ display: 'flex', flexDirection: 'column', gap: 16, height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 19, fontWeight: 700, margin: 0, color: 'var(--text)' }}>Orders</h1>
          <p style={{ fontSize: 12.5, color: 'var(--muted)', margin: '3px 0 0' }}>Create and track customer orders</p>
        </div>
        <PrimaryButton onClick={openCreate}><Plus size={14} /> New order</PrimaryButton>
      </div>

      <Card style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 }}>
        <div style={{ padding: 14, borderBottom: '1px solid var(--border)' }}>
          <SearchBar value={search} onChange={setSearch} placeholder="Search orders by customer or order number…" />
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 14px' }}>
          <CrmTable
            columns={columns}
            rows={rows}
            loading={loading}
            emptyTitle="No orders yet"
            emptySubtitle="Create your first order to get started."
            onRowClick={openDetails}
            actions={row => (
              <>
                <IconButton icon={Eye} title="View details" onClick={() => openDetails(row)} />
                <IconButton icon={Pencil} title="Edit" onClick={() => openEdit(row)} />
              </>
            )}
          />
        </div>
        <div style={{ padding: 12, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination page={page} pageSize={pageSize} total={total} onPageChange={setPage} />
        </div>
      </Card>

      {/* Create / edit modal */}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editingNumber ? `Edit order ${editingNumber}` : 'New order'} width={680}>
        {detailLoading ? (
          <div style={{ padding: '30px 0', textAlign: 'center', color: 'var(--dim)', fontSize: 13 }}>Loading order…</div>
        ) : (
          <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <FormField label="Customer" required>
                <ComboSelect
                  value={customerId}
                  label={customerLabel}
                  onChange={(id, opt) => { setCustomerId(id); setCustomerLabel(opt.label) }}
                  fetchOptions={fetchCustomers}
                  placeholder="Select a customer…"
                />
              </FormField>
              <FormField label="Reference">
                <input style={inputStyle} value={reference} onChange={e => setReference(e.target.value)} placeholder="Optional PO / reference" />
              </FormField>
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--muted)' }}>
                  Products
                </span>
                <GhostButton onClick={addLine}><Plus size={12} /> Add line</GhostButton>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {lines.map(line => (
                  <div key={line.key} style={{ display: 'grid', gridTemplateColumns: '2fr 90px 110px 28px', gap: 8, alignItems: 'center' }}>
                    <ComboSelect
                      value={line.product_id}
                      label={line.product_label}
                      onChange={(id, opt) => updateLine(line.key, {
                        product_id: id, product_label: opt.label,
                        unit_price: line.unit_price || (opt.sublabel?.startsWith('$') ? opt.sublabel.slice(1) : ''),
                      })}
                      fetchOptions={fetchProducts}
                      placeholder="Select a product…"
                    />
                    <input
                      style={inputStyle} type="number" min="0" step="1" placeholder="Qty"
                      value={line.quantity}
                      onChange={e => updateLine(line.key, { quantity: e.target.value })}
                    />
                    <input
                      style={inputStyle} type="number" min="0" step="0.01" placeholder="Price"
                      value={line.unit_price}
                      onChange={e => updateLine(line.key, { unit_price: e.target.value })}
                    />
                    <IconButton icon={X} title="Remove line" danger onClick={() => removeLine(line.key)} />
                  </div>
                ))}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10, fontSize: 13.5, color: 'var(--text)' }}>
                Total:&nbsp;<strong>${money(orderTotal)}</strong>
              </div>
            </div>

            <FormField label="Notes">
              <textarea
                style={{ ...inputStyle, minHeight: 60, resize: 'vertical', fontFamily: 'Outfit, sans-serif' }}
                value={notes}
                onChange={e => setNotes(e.target.value)}
              />
            </FormField>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <PrimaryButton type="submit" disabled={saving}>
                {saving ? 'Saving…' : editingNumber ? 'Save changes' : 'Create order'}
              </PrimaryButton>
            </div>
          </form>
        )}
      </Modal>

      {/* Details modal */}
      <Modal open={!!detailOrder} onClose={() => setDetailOrder(null)} title={detailOrder ? `Order ${detailOrder.order_number}` : ''} width={560}>
        {detailOrder && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 13 }}>
              <div><span style={{ color: 'var(--dim)' }}>Customer</span><br /><strong>{detailOrder.customer_name || '—'}</strong></div>
              <div><span style={{ color: 'var(--dim)' }}>Date</span><br /><strong>{detailOrder.date || '—'}</strong></div>
              <div><span style={{ color: 'var(--dim)' }}>Reference</span><br /><strong>{detailOrder.reference || '—'}</strong></div>
              <div><span style={{ color: 'var(--dim)' }}>Status</span><br /><strong>{detailOrder.status || '—'}</strong></div>
            </div>

            {detailOrder.lines === null ? (
              <div style={{ fontSize: 12.5, color: 'var(--dim)' }}>Loading lines…</div>
            ) : (
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 6 }}>
                  Products
                </div>
                <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
                  {detailOrder.lines.map((l, i) => (
                    <div key={i} style={{
                      display: 'flex', justifyContent: 'space-between', padding: '9px 12px', fontSize: 13,
                      borderBottom: i < detailOrder.lines.length - 1 ? '1px solid var(--border)' : 'none',
                    }}>
                      <span>{l.product_name || l.product_id} <span style={{ color: 'var(--dim)' }}>× {l.quantity}</span></span>
                      <span>${money(l.line_total)}</span>
                    </div>
                  ))}
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10, fontSize: 14 }}>
                  Total:&nbsp;<strong>${money(detailOrder.total)}</strong>
                </div>
              </div>
            )}

            {detailOrder.notes && (
              <div style={{ fontSize: 12.5, color: 'var(--muted)' }}>
                <span style={{ color: 'var(--dim)' }}>Notes:</span> {detailOrder.notes}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
