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
  name: '', contact: '', phone: '', mobile: '', email: '',
  address: '', address2: '', postal_code: '', city: '', country: '',
  tax_number: '', notes: '',
}

export default function ClientsPage() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(25)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null) // null = create
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  const [confirmTarget, setConfirmTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await crmApi.listClients({ search: search || undefined, page, page_size: pageSize })
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

  function openEdit(client) {
    setEditing(client)
    setForm({ ...emptyForm, ...client })
    setModalOpen(true)
  }

  async function submit(e) {
    e.preventDefault()
    if (!form.name.trim()) {
      toast.error('Client name is required')
      return
    }
    setSaving(true)
    try {
      if (editing) {
        await crmApi.updateClient(editing.id, form)
        toast.success('Client updated')
      } else {
        await crmApi.createClient(form)
        toast.success('Client added')
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
      await crmApi.deleteClient(confirmTarget.id)
      toast.success('Client deleted')
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
    { key: 'phone', label: 'Phone' },
    { key: 'email', label: 'Email' },
    { key: 'city', label: 'City' },
    { key: 'tax_number', label: 'Tax number' },
  ]

  return (
    <div className="fadein" style={{ display: 'flex', flexDirection: 'column', gap: 16, height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 19, fontWeight: 700, margin: 0, color: 'var(--text)' }}>Clients</h1>
          <p style={{ fontSize: 12.5, color: 'var(--muted)', margin: '3px 0 0' }}>Manage your customer accounts</p>
        </div>
        <PrimaryButton onClick={openCreate}><Plus size={14} /> Add client</PrimaryButton>
      </div>

      <Card style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 }}>
        <div style={{ padding: 14, borderBottom: '1px solid var(--border)' }}>
          <SearchBar value={search} onChange={setSearch} placeholder="Search clients by name, email, phone, city…" />
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 14px' }}>
          <CrmTable
            columns={columns}
            rows={rows}
            loading={loading}
            emptyTitle="No clients yet"
            emptySubtitle="Add your first client to get started."
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

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit client' : 'Add client'} width={560}>
        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <FormField label="Client name" required>
              <input style={inputStyle} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} autoFocus />
            </FormField>
            <FormField label="Contact person">
              <input style={inputStyle} value={form.contact || ''} onChange={e => setForm({ ...form, contact: e.target.value })} />
            </FormField>
            <FormField label="Phone">
              <input style={inputStyle} value={form.phone || ''} onChange={e => setForm({ ...form, phone: e.target.value })} />
            </FormField>
            <FormField label="Email">
              <input style={inputStyle} type="email" value={form.email || ''} onChange={e => setForm({ ...form, email: e.target.value })} />
            </FormField>
            <FormField label="Address">
              <input style={inputStyle} value={form.address || ''} onChange={e => setForm({ ...form, address: e.target.value })} />
            </FormField>
            <FormField label="City">
              <input style={inputStyle} value={form.city || ''} onChange={e => setForm({ ...form, city: e.target.value })} />
            </FormField>
            <FormField label="Postal code">
              <input style={inputStyle} value={form.postal_code || ''} onChange={e => setForm({ ...form, postal_code: e.target.value })} />
            </FormField>
            <FormField label="Country">
              <input style={inputStyle} value={form.country || ''} onChange={e => setForm({ ...form, country: e.target.value })} />
            </FormField>
            <FormField label="Tax number">
              <input style={inputStyle} value={form.tax_number || ''} onChange={e => setForm({ ...form, tax_number: e.target.value })} />
            </FormField>
          </div>
          <FormField label="Notes">
            <textarea
              style={{ ...inputStyle, minHeight: 70, resize: 'vertical', fontFamily: 'Outfit, sans-serif' }}
              value={form.notes || ''}
              onChange={e => setForm({ ...form, notes: e.target.value })}
            />
          </FormField>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
            <PrimaryButton type="submit" disabled={saving}>
              {saving ? 'Saving…' : editing ? 'Save changes' : 'Add client'}
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
