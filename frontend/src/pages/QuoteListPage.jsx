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
const STATUSES = ['QUICK_QUOTE', 'QUOTED']

function fmt(value) {
  return Number(value).toLocaleString('en-GB', { style: 'currency', currency: 'GBP' })
}

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

function StatusBadge({ status }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{status.replace('_', ' ')}</span>
}

const COLUMNS = [
  { key: 'customer_name',      label: 'Customer' },
  { key: 'product',            label: 'Product' },
  { key: 'status',             label: 'Status' },
  { key: 'payment_type',       label: 'Payment' },
  { key: 'calculated_premium', label: 'Premium', align: 'right' },
  { key: 'created_at',         label: 'Created' },
]

function SortIcon({ col, sort }) {
  if (sort.col !== col) return <span className="sort-icon sort-idle">⇅</span>
  return <span className="sort-icon sort-active">{sort.dir === 'asc' ? '↑' : '↓'}</span>
}

export default function QuoteListPage() {
  const navigate = useNavigate()
  const [quotes, setQuotes] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ status: '', product: '' })
  const [sort, setSort] = useState({ col: 'created_at', dir: 'desc' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const PAGE_SIZE = 20

  useEffect(() => {
    setLoading(true)
    setError(null)
    const params = { page, page_size: PAGE_SIZE, sort_by: sort.col, sort_dir: sort.dir }
    if (filters.status) params.status = filters.status
    if (filters.product) params.product = filters.product

    client.get('/quotes', { params })
      .then(({ data }) => {
        setQuotes(data.items)
        setTotal(data.total)
      })
      .catch(() => setError('Failed to load quotes.'))
      .finally(() => setLoading(false))
  }, [page, filters, sort])

  function setFilter(key, value) {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1)
  }

  function toggleSort(col) {
    setSort((s) => s.col === col
      ? { col, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { col, dir: 'asc' }
    )
    setPage(1)
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">Quotes</h2>
        <button className="btn btn-primary" onClick={() => navigate('/quotes/new')}>
          New Quote
        </button>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="ql-filters">
            <select className="form-select ql-filter-select"
              value={filters.status}
              onChange={(e) => setFilter('status', e.target.value)}>
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s.replace('_', ' ')}</option>
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
          </div>
          <span className="text-muted">{total} quote{total !== 1 ? 's' : ''}</span>
        </div>

        {error && <div className="ql-error">{error}</div>}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {COLUMNS.map((col) => (
                  <th key={col.key}
                    className={`ql-th-sortable${col.align === 'right' ? ' text-right' : ''}`}
                    onClick={() => toggleSort(col.key)}>
                    {col.label}
                    <SortIcon col={col.key} sort={sort} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={COLUMNS.length} className="ql-empty">Loading…</td></tr>
              )}
              {!loading && quotes.length === 0 && (
                <tr><td colSpan={COLUMNS.length} className="ql-empty">No quotes found</td></tr>
              )}
              {!loading && quotes.map((q) => (
                <tr key={q.id} onClick={() => navigate(`/quotes/${q.id}`)}>
                  <td>{q.customer_name}</td>
                  <td>{PRODUCT_LABELS[q.product] ?? q.product}</td>
                  <td><StatusBadge status={q.status} /></td>
                  <td>{q.payment_type}</td>
                  <td className="text-right">{fmt(q.calculated_premium)}</td>
                  <td>{fmtDate(q.created_at)}</td>
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
        .ql-filters { display: flex; gap: 0.75rem; }
        .ql-filter-select { width: auto; min-width: 140px; }
        .ql-error {
          background: #fee2e2;
          color: var(--danger);
          padding: 0.75rem 1.25rem;
          font-size: 0.875rem;
        }
        .ql-empty { text-align: center; padding: 2rem; color: var(--grey-500); }
        .ql-th-sortable {
          cursor: pointer;
          user-select: none;
          white-space: nowrap;
        }
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
