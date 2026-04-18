import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import client from '../api/client'

const ALL_PRODUCTS = ['TYRE_ESSENTIAL', 'TYRE_PLUS', 'COSMETIC', 'GAP', 'VRI', 'TLP']
const PRODUCT_LABELS = {
  TYRE_ESSENTIAL: 'Tyre Essential',
  TYRE_PLUS: 'Tyre Plus',
  COSMETIC: 'Cosmetic',
  GAP: 'GAP',
  VRI: 'VRI',
  TLP: 'TLP',
}

function fmt(value) {
  return Number(value).toLocaleString('en-GB', { style: 'currency', currency: 'GBP' })
}

export default function QuickQuotePage() {
  const { tenantConfig } = useAuth()
  const navigate = useNavigate()

  const allowedProducts = tenantConfig?.allowed_products ?? ALL_PRODUCTS

  const [form, setForm] = useState({
    customer_name: '',
    product: allowedProducts[0] || '',
    term_months: '12',
    vehicle_value: '',
    payment_type: 'CASH',
    finance_deposit: '',
    finance_term_months: '12',
  })
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
    setResult(null)
    setError(null)
  }

  function buildBody() {
    const body = {
      customer_name: form.customer_name,
      product: form.product,
      term_months: Number(form.term_months),
      vehicle: { purchase_price: Number(form.vehicle_value) },
      payment_type: form.payment_type,
    }
    if (form.payment_type === 'FINANCE') {
      body.finance_deposit = Number(form.finance_deposit)
      body.finance_term_months = Number(form.finance_term_months)
    }
    return body
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setResult(null)
    setLoading(true)
    try {
      const { data } = await client.post('/quotes/calculate', buildBody())
      setResult(data)
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Failed to calculate price. Please check your inputs.')
    } finally {
      setLoading(false)
    }
  }

  async function handleProceed() {
    setError(null)
    setLoading(true)
    try {
      const { data } = await client.post('/quotes/quick', buildBody())
      navigate(`/quotes/new?from=${data.id}`)
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Failed to save quote. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">Quick Quote</h2>
      </div>

      <div className="qq-layout">
        <div className="card qq-form-card">
          <div className="card-header">
            <span style={{ fontWeight: 600 }}>Quote details</span>
          </div>
          <div className="card-body">
            <form onSubmit={handleSubmit} className="qq-form">

              <div className="form-group">
                <label className="form-label">Customer name</label>
                <input
                  className="form-input"
                  type="text"
                  value={form.customer_name}
                  onChange={(e) => set('customer_name', e.target.value)}
                  placeholder="Full name"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Product</label>
                <select
                  className="form-select"
                  value={form.product}
                  onChange={(e) => set('product', e.target.value)}
                  required
                >
                  {allowedProducts.map((p) => (
                    <option key={p} value={p}>{PRODUCT_LABELS[p] ?? p}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Vehicle value (£)</label>
                <input
                  className="form-input"
                  type="number"
                  min="1"
                  max="200000"
                  step="1"
                  value={form.vehicle_value}
                  onChange={(e) => set('vehicle_value', e.target.value)}
                  placeholder="e.g. 18500"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Term</label>
                <select
                  className="form-select"
                  value={form.term_months}
                  onChange={(e) => set('term_months', e.target.value)}
                >
                  <option value="12">12 months</option>
                  <option value="24">24 months</option>
                  <option value="36">36 months</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Payment type</label>
                <div className="qq-toggle">
                  {['CASH', 'FINANCE'].map((pt) => (
                    <button
                      key={pt}
                      type="button"
                      className={`qq-toggle-btn${form.payment_type === pt ? ' active' : ''}`}
                      onClick={() => set('payment_type', pt)}
                    >
                      {pt === 'CASH' ? 'Cash' : 'Finance'}
                    </button>
                  ))}
                </div>
              </div>

              {form.payment_type === 'FINANCE' && (
                <>
                  <div className="form-group">
                    <label className="form-label">Deposit (£)</label>
                    <input
                      className="form-input"
                      type="number"
                      min="0"
                      step="0.01"
                      value={form.finance_deposit}
                      onChange={(e) => set('finance_deposit', e.target.value)}
                      placeholder="e.g. 50.00"
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Finance term</label>
                    <select
                      className="form-select"
                      value={form.finance_term_months}
                      onChange={(e) => set('finance_term_months', e.target.value)}
                    >
                      <option value="12">12 months</option>
                      <option value="24">24 months</option>
                      <option value="36">36 months</option>
                    </select>
                  </div>
                </>
              )}

              {error && <div className="qq-error">{error}</div>}

              <button className="btn btn-primary" type="submit" disabled={loading} style={{ marginTop: '0.5rem' }}>
                {loading ? 'Calculating...' : 'Get indicative price'}
              </button>
            </form>
          </div>
        </div>

        {result && (
          <div className="card qq-result-card">
            <div className="card-header">
              <span style={{ fontWeight: 600 }}>Indicative price</span>
            </div>
            <div className="card-body">
              <div className="qq-premium">{fmt(result.calculated_premium)}</div>
              <p className="text-muted" style={{ marginBottom: '1.25rem' }}>
                {PRODUCT_LABELS[form.product] ?? form.product} · {form.term_months} months · {form.payment_type}
              </p>

              {result.finance_breakdown && form.payment_type === 'FINANCE' && (() => {
                const fb = result.finance_breakdown
                const deposit = Number(form.finance_deposit) || 0
                const totalCost = Number(fb.total_repayable) + deposit
                return (
                  <div className="qq-finance-breakdown">
                    <div className="qq-finance-row">
                      <span>Down payment</span>
                      <strong>{fmt(deposit)}</strong>
                    </div>
                    <div className="qq-finance-row">
                      <span>Amount financed</span>
                      <strong>{fmt(fb.financed_amount)}</strong>
                    </div>
                    <div className="qq-finance-divider" />
                    <div className="qq-finance-row">
                      <span>Monthly payment</span>
                      <strong>{fmt(fb.monthly_payment)} × {form.finance_term_months} months</strong>
                    </div>
                    <div className="qq-finance-row">
                      <span>Finance charge (cost of credit)</span>
                      <strong>{fmt(fb.finance_charge)}</strong>
                    </div>
                    <div className="qq-finance-row">
                      <span>Representative APR</span>
                      <strong>{fb.apr}%</strong>
                    </div>
                    <div className="qq-finance-divider" />
                    <div className="qq-finance-row qq-finance-total">
                      <span>Total cost (inc. deposit)</span>
                      <strong>{fmt(totalCost)}</strong>
                    </div>
                  </div>
                )
              })()}

              <button
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '1.25rem' }}
                onClick={handleProceed}
                disabled={loading}
              >
                {loading ? 'Saving…' : 'Proceed to full quote'}
              </button>
            </div>
          </div>
        )}
      </div>

      <style>{`
        .qq-layout {
          display: grid;
          grid-template-columns: 420px 1fr;
          gap: 1.5rem;
          align-items: start;
        }
        @media (max-width: 700px) {
          .qq-layout { grid-template-columns: 1fr; }
        }
        .qq-form { display: flex; flex-direction: column; gap: 1rem; }
        .qq-toggle {
          display: flex;
          border: 1px solid var(--grey-300);
          border-radius: var(--radius-sm);
          overflow: hidden;
        }
        .qq-toggle-btn {
          flex: 1;
          padding: 0.5rem;
          border: none;
          background: var(--white);
          color: var(--grey-700);
          font-size: 0.875rem;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.15s, color 0.15s;
        }
        .qq-toggle-btn.active {
          background: var(--brand-primary);
          color: var(--white);
        }
        .qq-error {
          background: #fee2e2;
          color: var(--danger);
          border-radius: var(--radius-sm);
          padding: 0.6rem 0.75rem;
          font-size: 0.875rem;
        }
        .qq-premium {
          font-size: 2.5rem;
          font-weight: 700;
          color: var(--brand-primary);
          line-height: 1;
          margin-bottom: 0.5rem;
        }
        .qq-finance-breakdown {
          background: var(--grey-50);
          border-radius: var(--radius);
          padding: 1rem;
          display: flex;
          flex-direction: column;
          gap: 0.6rem;
        }
        .qq-finance-row {
          display: flex;
          justify-content: space-between;
          font-size: 0.9rem;
          color: var(--grey-700);
        }
        .qq-finance-divider {
          border-top: 1px solid var(--grey-200);
          margin: 0.25rem 0;
        }
        .qq-finance-total {
          color: var(--grey-900);
          font-size: 0.95rem;
        }
        .qq-finance-total strong {
          color: var(--brand-primary);
        }
      `}</style>
    </div>
  )
}
