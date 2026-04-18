import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'

const PRODUCTS = ['TYRE_ESSENTIAL', 'TYRE_PLUS', 'COSMETIC', 'GAP', 'VRI', 'TLP']
const PRODUCT_LABELS = {
  TYRE_ESSENTIAL: 'Tyre Essential',
  TYRE_PLUS: 'Tyre Plus',
  COSMETIC: 'Cosmetic',
  GAP: 'GAP',
  VRI: 'VRI',
  TLP: 'TLP',
}
const STATUSES = ['BOUND', 'ISSUED', 'CANCELLED']

function fmt(value) {
  return Number(value).toLocaleString('en-GB', { style: 'currency', currency: 'GBP' })
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

function StatusBadge({ status }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{status}</span>
}

const COLUMNS = [
  { key: 'policy_number', label: 'Policy #' },
  { key: 'insured',       label: 'Insured', sortable: false },
  { key: 'product',       label: 'Product' },
  { key: 'status',        label: 'Status' },
  { key: 'dealer',        label: 'Dealer', sortable: false },
  { key: 'inception_date', label: 'Inception' },
  { key: 'expiry_date',   label: 'Expiry' },
  { key: 'premium',       label: 'Premium', align: 'right' },
]

function SortIcon({ col, sort }) {
  if (!col.sortable && col.sortable !== undefined) return null
  if (sort.col !== col.key) return <span className="sort-icon sort-idle">⇅</span>
  return <span className="sort-icon sort-active">{sort.dir === 'asc' ? '↑' : '↓'}</span>
}

export default function PolicyListPage() {
  const navigate = useNavigate()
  const [policies, setPolicies] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ status: '', product: '', date_from: '', date_to: '' })
  const [sort, setSort] = useState({ col: 'inception_date', dir: 'desc' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const PAGE_SIZE = 20

  useEffect(() => {
    setLoading(true)
    setError(null)
    const params = { page, page_size: PAGE_SIZE, sort_by: sort.col, sort_dir: sort.dir }
    if (filters.status) params.status = filters.status
    if (filters.product) params.product = filters.product
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to) params.date_to = filters.date_to

    client.get('/policies', { params })
      .then(({ data }) => {
        setPolicies(data.items)
        setTotal(data.total)
      })
      .catch(() => setError('Failed to load policies.'))
      .finally(() => setLoading(false))
  }, [page, filters, sort])

  function setFilter(key, value) {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1)
  }

  function toggleSort(col) {
    if (col.sortable === false) return
    setSort((s) => s.col === col.key
      ? { col: col.key, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { col: col.key, dir: 'asc' }
    )
    setPage(1)
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">Policies</h2>
        <span className="text-muted">{total} polic{total !== 1 ? 'ies' : 'y'}</span>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="ql-filters">
            <select className="form-select ql-filter-select"
              value={filters.status}
              onChange={(e) => setFilter('status', e.target.value)}>
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <select className="form-select ql-filter-select"
              value={filters.product}
              onChange={(e) => setFilter('product', e.target.value)}>
              <option value="">All products</option>
              {PRODUCTS.map((p) => (
                <option key={p} value={p}>{PRODUCT_LABELS[p]}</option>
              ))}
            </select>
            <input className="form-input ql-filter-date" type="date"
              value={filters.date_from}
              onChange={(e) => setFilter('date_from', e.target.value)}
              title="Inception from" />
            <input className="form-input ql-filter-date" type="date"
              value={filters.date_to}
              onChange={(e) => setFilter('date_to', e.target.value)}
              title="Inception to" />
          </div>
        </div>

        {error && <div className="ql-error">{error}</div>}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {COLUMNS.map((col) => (
                  <th key={col.key}
                    className={`${col.sortable !== false ? 'ql-th-sortable' : ''}${col.align === 'right' ? ' text-right' : ''}`}
                    onClick={() => toggleSort(col)}>
                    {col.label}
                    <SortIcon col={col} sort={sort} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={COLUMNS.length} className="ql-empty">Loading…</td></tr>
              )}
              {!loading && policies.length === 0 && (
                <tr><td colSpan={COLUMNS.length} className="ql-empty">No policies found</td></tr>
              )}
              {!loading && policies.map((p) => (
                <tr key={p.id} onClick={() => navigate(`/policies/${p.id}`)}>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{p.policy_number}</td>
                  <td>{p.insured_name ?? '—'}</td>
                  <td>{PRODUCT_LABELS[p.product] ?? p.product}</td>
                  <td><StatusBadge status={p.status} /></td>
                  <td>{p.dealer?.name ?? '—'}</td>
                  <td>{fmtDate(p.inception_date)}</td>
                  <td>{fmtDate(p.expiry_date)}</td>
                  <td className="text-right">{fmt(p.premium)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="ql-pagination">
            <button className="btn btn-secondary btn-sm"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span className="text-muted">Page {page} of {totalPages}</span>
            <button className="btn btn-secondary btn-sm"
              disabled={page === totalPages}
              onClick={() => setPage((p) => p + 1)}>
              Next
            </button>
          </div>
        )}
      </div>

      <style>{`
        .ql-filters { display: flex; gap: 0.75rem; flex-wrap: wrap; }
        .ql-filter-select { width: auto; min-width: 140px; }
        .ql-filter-date { width: auto; min-width: 130px; }
        .ql-error {
          background: #fee2e2;
          color: var(--danger);
          padding: 0.75rem 1.25rem;
          font-size: 0.875rem;
        }
        .ql-empty { text-align: center; padding: 2rem; color: var(--grey-500); }
        .ql-th-sortable { cursor: pointer; user-select: none; white-space: nowrap; }
        .ql-th-sortable:hover { background: var(--grey-100); }
        .sort-icon { margin-left: 0.35rem; font-size: 0.75rem; }
        .sort-idle { color: var(--grey-300); }
        .sort-active { color: var(--brand-primary); }
        .ql-pagination {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 1rem;
          padding: 1rem;
          border-top: 1px solid var(--grey-200);
        }
      `}</style>
    </div>
  )
}
