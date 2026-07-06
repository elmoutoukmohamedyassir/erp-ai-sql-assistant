import { useEffect, useState, useCallback } from 'react'
import toast from 'react-hot-toast'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import * as crmApi from '../../services/crmApi'
import CrmTable from '../../components/crm/CrmTable'
import {
  Card, PrimaryButton, IconButton, SearchBar, Modal, ConfirmDialog,
  Pagination, FormField, inputStyle,
} from '../../components/crm/CrmUi'

const emptyForm = {
  name: '', sku: '', description: '', category: '', unit: '',
  sale_price: '', purchase_price: '', barcode: '',
}

const money = v => (v || v === 0) ? Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : null

export default function ProductsPage() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(25)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  const [confirmTarget, setConfirmTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await crmApi.listProducts({ search: search || undefined, page, page_size: pageSize })
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

  function openCreate() {
    setEditing(null)
    setForm(emptyForm)
    setModalOpen(true)
  }

  function openEdit(product) {
    setEditing(product)
    setForm({ ...emptyForm, ...product, sku: product.sku || product.id })
    setModalOpen(true)
  }

  async function submit(e) {
    e.preventDefault()
    if (!form.name.trim()) {
      toast.error('Product name is required')
      return
    }
    setSaving(true)
    try {
      const payload = {
        ...form,
        sale_price: form.sale_price === '' ? null : Number(form.sale_price),
        purchase_price: form.purchase_price === '' ? null : Number(form.purchase_price),
      }
      if (editing) {
        delete payload.sku
        await crmApi.updateProduct(editing.id, payload)
        toast.success('Product updated')
      } else {
        await crmApi.createProduct(payload)
        toast.success('Product added')
      }
      setModalOpen(false)
      load()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function confirmDelete() {
    setDeleting(true)
    try {
      await crmApi.deleteProduct(confirmTarget.id)
      toast.success('Product deleted')
      setConfirmTarget(null)
      load()
    } catch (e) {
      toast.error(e.message)
    } finally {
      setDeleting(false)
    }
  }

  const columns = [
    { key: 'name', label: 'Name', render: r => <span style={{ fontWeight: 600 }}>{r.name}</span> },
    { key: 'sku', label: 'Reference' },
    { key: 'category', label: 'Category' },
    { key: 'sale_price', label: 'Sale price', render: r => money(r.sale_price) },
    { key: 'unit', label: 'Unit' },
  ]

  return (
    <div className="fadein" style={{ display: 'flex', flexDirection: 'column', gap: 16, height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 19, fontWeight: 700, margin: 0, color: 'var(--text)' }}>Products</h1>
          <p style={{ fontSize: 12.5, color: 'var(--muted)', margin: '3px 0 0' }}>Manage your product catalog</p>
        </div>
        <PrimaryButton onClick={openCreate}><Plus size={14} /> Add product</PrimaryButton>
      </div>

      <Card style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 }}>
        <div style={{ padding: 14, borderBottom: '1px solid var(--border)' }}>
          <SearchBar value={search} onChange={setSearch} placeholder="Search products by name, category…" />
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 14px' }}>
          <CrmTable
            columns={columns}
            rows={rows}
            loading={loading}
            emptyTitle="No products yet"
            emptySubtitle="Add your first product to get started."
            onRowClick={openEdit}
            actions={row => (
              <>
                <IconButton icon={Pencil} title="Edit" onClick={() => openEdit(row)} />
                <IconButton icon={Trash2} title="Delete" danger onClick={() => setConfirmTarget(row)} />
              </>
            )}
          />
        </div>
        <div style={{ padding: 12, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination page={page} pageSize={pageSize} total={total} onPageChange={setPage} />
        </div>
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit product' : 'Add product'} width={560}>
        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <FormField label="Product name" required>
              <input style={inputStyle} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} autoFocus />
            </FormField>
            <FormField label="Reference / SKU">
              <input
                style={{ ...inputStyle, ...(editing ? { opacity: .6 } : {}) }}
                value={form.sku || ''}
                disabled={!!editing}
                placeholder="Leave blank to auto-generate"
                onChange={e => setForm({ ...form, sku: e.target.value })}
              />
            </FormField>
            <FormField label="Category">
              <input style={inputStyle} value={form.category || ''} onChange={e => setForm({ ...form, category: e.target.value })} />
            </FormField>
            <FormField label="Unit">
              <input style={inputStyle} placeholder="e.g. pcs, box, kg" value={form.unit || ''} onChange={e => setForm({ ...form, unit: e.target.value })} />
            </FormField>
            <FormField label="Sale price">
              <input style={inputStyle} type="number" step="0.01" value={form.sale_price ?? ''} onChange={e => setForm({ ...form, sale_price: e.target.value })} />
            </FormField>
            <FormField label="Purchase price">
              <input style={inputStyle} type="number" step="0.01" value={form.purchase_price ?? ''} onChange={e => setForm({ ...form, purchase_price: e.target.value })} />
            </FormField>
            <FormField label="Barcode">
              <input style={inputStyle} value={form.barcode || ''} onChange={e => setForm({ ...form, barcode: e.target.value })} />
            </FormField>
          </div>
          <FormField label="Description">
            <textarea
              style={{ ...inputStyle, minHeight: 70, resize: 'vertical', fontFamily: 'Outfit, sans-serif' }}
              value={form.description || ''}
              onChange={e => setForm({ ...form, description: e.target.value })}
            />
          </FormField>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
            <PrimaryButton type="submit" disabled={saving}>
              {saving ? 'Saving…' : editing ? 'Save changes' : 'Add product'}
            </PrimaryButton>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={!!confirmTarget}
        message={`Delete "${confirmTarget?.name}"? This can't be undone.`}
        onConfirm={confirmDelete}
        onCancel={() => setConfirmTarget(null)}
        loading={deleting}
      />
    </div>
  )
}
