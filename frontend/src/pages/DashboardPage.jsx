import { useEffect, useState } from 'react'
import { Users, ShoppingCart, Package, Boxes, ArrowRight } from 'lucide-react'
import * as crmApi from '../services/crmApi'
import { Card } from '../components/crm/CrmUi'

const money = v => (v || v === 0) ? Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'

export default function DashboardPage({ onNavigate, user }) {
  const [stats, setStats] = useState({ clients: null, products: null, orders: null, revenue: null })

  useEffect(() => {
    let cancelled = false
    async function load() {
      const results = await Promise.allSettled([
        crmApi.listClients({ page: 1, page_size: 1 }),
        crmApi.listProducts({ page: 1, page_size: 1 }),
        crmApi.listOrders({ page: 1, page_size: 5 }),
      ])
      if (cancelled) return
      const [clientsRes, productsRes, ordersRes] = results
      setStats({
        clients: clientsRes.status === 'fulfilled' ? clientsRes.value.total : null,
        products: productsRes.status === 'fulfilled' ? productsRes.value.total : null,
        orders: ordersRes.status === 'fulfilled' ? ordersRes.value.total : null,
        recentOrders: ordersRes.status === 'fulfilled' ? ordersRes.value.items : [],
      })
    }
    load()
    return () => { cancelled = true }
  }, [])

  const cards = [
    { key: 'clients', label: 'Clients', value: stats.clients, icon: Users, color: 'var(--cyan)', nav: 'crm-clients' },
    { key: 'products', label: 'Products', value: stats.products, icon: Package, color: 'var(--green)', nav: 'crm-products' },
    { key: 'orders', label: 'Orders', value: stats.orders, icon: ShoppingCart, color: 'var(--amber)', nav: 'crm-orders' },
    { key: 'stock', label: 'Stock', value: null, icon: Boxes, color: 'var(--muted)', nav: 'crm-stock', hint: 'View levels' },
  ]

  return (
    <div className="fadein" style={{ display: 'flex', flexDirection: 'column', gap: 20, height: '100%', overflowY: 'auto' }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0, color: 'var(--text)' }}>
          Welcome{user?.username ? `, ${user.username}` : ''}
        </h1>
        <p style={{ fontSize: 12.5, color: 'var(--muted)', margin: '3px 0 0' }}>Here's a quick look at your CRM</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
        {cards.map(c => (
          <Card
            key={c.key}
            style={{ cursor: 'pointer', transition: 'border-color .15s' }}
          >
            <div
              onClick={() => onNavigate?.(c.nav)}
              style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
            >
              <div style={{
                width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'var(--bg)', border: '1px solid var(--border)',
              }}>
                <c.icon size={15} color={c.color} />
              </div>
              <div>
                <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text)' }}>
                  {c.value === null || c.value === undefined ? (c.hint || '—') : c.value}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                  {c.label} <ArrowRight size={11} />
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Card>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Recent orders</span>
          <span
            onClick={() => onNavigate?.('crm-orders')}
            style={{ fontSize: 12, color: 'var(--cyan)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3 }}
          >
            View all <ArrowRight size={11} />
          </span>
        </div>
        {!stats.recentOrders || stats.recentOrders.length === 0 ? (
          <div style={{ fontSize: 12.5, color: 'var(--dim)', padding: '12px 0' }}>No orders yet.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {stats.recentOrders.map((o, i) => (
              <div key={o.order_number} style={{
                display: 'flex', justifyContent: 'space-between', padding: '9px 2px', fontSize: 13,
                borderBottom: i < stats.recentOrders.length - 1 ? '1px solid var(--border)' : 'none',
              }}>
                <span>{o.order_number} — {o.customer_name || 'Unknown customer'}</span>
                <span style={{ color: 'var(--muted)' }}>${money(o.total)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
