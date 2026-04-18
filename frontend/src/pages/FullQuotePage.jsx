import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import client from '../api/client'

const ALL_PRODUCTS = ['TYRE_ESSENTIAL', 'TYRE_PLUS', 'COSMETIC', 'GAP', 'VRI', 'TLP']

const TLP_LIMITS = [
  { threshold: 15000, limit: 500 },
  { threshold: 30000, limit: 750 },
  { threshold: 50000, limit: 1000 },
  { threshold: Infinity, limit: 1500 },
]

function getTlpLimit(vehicleValue) {
  const bucket = TLP_LIMITS.find(({ threshold }) => vehicleValue <= threshold)
  return bucket ? bucket.limit : 1500
}
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

function Section({ title, children }) {
  return (
    <div className="fq-section">
      <div className="fq-section-title">{title}</div>
      <div className="fq-section-body">{children}</div>
    </div>
  )
}

function Field({ label, required, children }) {
  return (
    <div className="form-group">
      <label className="form-label">{label}{required && <span className="fq-required"> *</span>}</label>
      {children}
    </div>
  )
}

const EMPTY_FORM = {
  customer_name: '',
  customer_dob: '',
  customer_email: '',
  address_line1: '',
  address_city: '',
  address_postcode: '',
  vehicle_value: '',
  registration: '',
  make: '',
  model: '',
  year: '',
  purchase_date: '',
  finance_type: '',
  product: 'GAP',
  term_months: '12',
  loan_amount: '',
  payment_type: 'CASH',
  finance_deposit: '',
  finance_term_months: '12',
}

export default function FullQuotePage() {
  const { tenantConfig } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const fromQuoteId = searchParams.get('from')

  const allowedProducts = tenantConfig?.allowed_products ?? ALL_PRODUCTS

  const [form, setForm] = useState({ ...EMPTY_FORM, product: allowedProducts[0] || 'GAP' })
  const [previewPremium, setPreviewPremium] = useState(null)
  const [previewFinance, setPreviewFinance] = useState(null)
  const [loading, setLoading] = useState(false)
  const [prefilling, setPrefilling] = useState(!!fromQuoteId)
  const [error, setError] = useState(null)
  const [fieldErrors, setFieldErrors] = useState({})

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
    setFieldErrors((e) => ({ ...e, [field]: null }))
    setError(null)
  }

  // Pre-fill from quick quote (read-only fetch — quick quote just populates the form)
  useEffect(() => {
    if (!fromQuoteId) return
    client.get(`/quotes/${fromQuoteId}`)
      .then(({ data }) => {
        const deposit = data.finance_breakdown?.financed_amount
          ? String(Number(data.vehicle?.purchase_price || 0) - Number(data.finance_breakdown.financed_amount))
          : ''
        setForm((f) => ({
          ...f,
          customer_name: data.customer_name || '',
          product: allowedProducts.includes(data.product) ? data.product : f.product,
          term_months: String(data.term_months),
          vehicle_value: data.vehicle?.purchase_price ? String(data.vehicle.purchase_price) : '',
          registration: data.vehicle?.registration || '',
          make: data.vehicle?.make || '',
          model: data.vehicle?.model || '',
          year: data.vehicle?.year ? String(data.vehicle.year) : '',
          purchase_date: data.vehicle?.purchase_date || '',
          payment_type: data.payment_type || 'CASH',
          finance_deposit: data.finance_deposit ? String(data.finance_deposit) : '',
          finance_term_months: data.finance_term_months ? String(data.finance_term_months) : '12',
        }))
        setPreviewPremium(data.calculated_premium)
        if (data.payment_type === 'FINANCE' && data.finance_breakdown) setPreviewFinance(data.finance_breakdown)
      })
      .catch(() => setError('Could not load quote to pre-fill.'))
      .finally(() => setPrefilling(false))
  }, [fromQuoteId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Live pricing preview (debounced) — includes finance when applicable
  const recalculate = useCallback(() => {
    const value = Number(form.vehicle_value)
    const term = Number(form.term_months)
    if (!value || !form.product || !term) return

    const body = {
      customer_name: form.customer_name || 'Preview',
      product: form.product,
      term_months: term,
      vehicle: { purchase_price: value },
      payment_type: form.payment_type,
    }

    if (form.payment_type === 'FINANCE' && form.finance_deposit !== '' && form.finance_term_months) {
      body.finance_deposit = Number(form.finance_deposit)
      body.finance_term_months = Number(form.finance_term_months)
    }

    client.post('/quotes/calculate', body)
      .then(({ data }) => {
        setPreviewPremium(data.calculated_premium)
        setPreviewFinance(data.finance_breakdown ?? null)
      })
      .catch(() => {})
  }, [form.vehicle_value, form.product, form.term_months, form.customer_name,
      form.payment_type, form.finance_deposit, form.finance_term_months])

  useEffect(() => {
    const t = setTimeout(recalculate, 500)
    return () => clearTimeout(t)
  }, [recalculate])

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setFieldErrors({})
    setLoading(true)

    const vehicle = {
      purchase_price: Number(form.vehicle_value),
      registration: form.registration,
      make: form.make,
      model: form.model,
      year: Number(form.year),
      purchase_date: form.purchase_date,
      ...(form.finance_type ? { finance_type: form.finance_type } : {}),
    }

    const product_fields = {}
    if (form.product === 'GAP' && form.loan_amount) {
      product_fields.loan_amount = Number(form.loan_amount)
    }
    if (form.product === 'TLP') {
      product_fields.tlp_limit = getTlpLimit(Number(form.vehicle_value))
    }

    const address = (form.address_line1 || form.address_city || form.address_postcode)
      ? { line1: form.address_line1, city: form.address_city, postcode: form.address_postcode }
      : undefined

    try {
      const body = {
        customer_name: form.customer_name,
        product: form.product,
        term_months: Number(form.term_months),
        vehicle,
        ...(form.customer_dob ? { customer_dob: form.customer_dob } : {}),
        ...(form.customer_email ? { customer_email: form.customer_email } : {}),
        ...(address ? { customer_address: address } : {}),
        ...(Object.keys(product_fields).length ? { product_fields } : {}),
        payment_type: form.payment_type,
        ...(form.payment_type === 'FINANCE' ? {
          finance_deposit: Number(form.finance_deposit),
          finance_term_months: Number(form.finance_term_months),
        } : {}),
      }
      const { data } = await client.post('/quotes', body)
      navigate(`/quotes/${data.id}`)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        setError(detail)
      } else if (Array.isArray(detail)) {
        const errs = {}
        detail.forEach((d) => {
          const field = d.loc?.[d.loc.length - 1]
          if (field) errs[field] = d.msg
        })
        setFieldErrors(errs)
        setError('Please fix the highlighted fields.')
      } else {
        setError('Failed to create quote. Please check your inputs.')
      }
    } finally {
      setLoading(false)
    }
  }

  if (prefilling) {
    return <div className="page"><p className="text-muted">Loading quote…</p></div>
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2 className="page-title">{fromQuoteId ? 'Full Quote' : 'New Quote'}</h2>
          {fromQuoteId && (
            <p className="text-muted" style={{ marginTop: '0.25rem' }}>
              Pre-filled from quick quote #{fromQuoteId}
            </p>
          )}
        </div>
        {previewPremium && (
          <div className="fq-premium-preview">
            <div className="fq-preview-label">
              {form.payment_type === 'FINANCE' && previewFinance ? 'Total payable (inc. deposit)' : 'Indicative premium'}
            </div>
            <div className="fq-preview-amount">
              {form.payment_type === 'FINANCE' && previewFinance
                ? fmt(Number(previewFinance.total_repayable) + Number(form.finance_deposit || 0))
                : fmt(previewPremium)}
            </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="fq-layout">
        <div className="fq-col">

          <Section title="Customer details">
            <Field label="Full name" required>
              <input className={`form-input${fieldErrors.customer_name ? ' fq-input-error' : ''}`}
                type="text" value={form.customer_name}
                onChange={(e) => set('customer_name', e.target.value)} required />
              {fieldErrors.customer_name && <span className="fq-field-error">{fieldErrors.customer_name}</span>}
            </Field>
            <Field label="Date of birth">
              <input className="form-input" type="date" value={form.customer_dob}
                onChange={(e) => set('customer_dob', e.target.value)} />
            </Field>
            <Field label="Email address">
              <input className="form-input" type="email" value={form.customer_email}
                onChange={(e) => set('customer_email', e.target.value)} />
            </Field>
            <div className="fq-address-grid">
              <Field label="Address line 1">
                <input className="form-input" type="text" value={form.address_line1}
                  onChange={(e) => set('address_line1', e.target.value)} />
              </Field>
              <Field label="City">
                <input className="form-input" type="text" value={form.address_city}
                  onChange={(e) => set('address_city', e.target.value)} />
              </Field>
              <Field label="Postcode">
                <input className="form-input" type="text" value={form.address_postcode}
                  onChange={(e) => set('address_postcode', e.target.value)} />
              </Field>
            </div>
          </Section>

          <Section title="Vehicle details">
            <div className="fq-two-col">
              <Field label="Purchase price (£)" required>
                <input className="form-input" type="number" min="1" max="200000" step="1"
                  value={form.vehicle_value}
                  onChange={(e) => set('vehicle_value', e.target.value)} required />
              </Field>
              <Field label="Registration" required>
                <input className="form-input" type="text" value={form.registration}
                  onChange={(e) => set('registration', e.target.value)} required />
              </Field>
              <Field label="Make" required>
                <input className="form-input" type="text" value={form.make}
                  onChange={(e) => set('make', e.target.value)} required />
              </Field>
              <Field label="Model" required>
                <input className="form-input" type="text" value={form.model}
                  onChange={(e) => set('model', e.target.value)} required />
              </Field>
              <Field label="Year" required>
                <input className="form-input" type="number" min="2015" max="2027"
                  value={form.year}
                  onChange={(e) => set('year', e.target.value)} required />
              </Field>
              <Field label="Purchase date" required>
                <input className="form-input" type="date" value={form.purchase_date}
                  onChange={(e) => set('purchase_date', e.target.value)} required />
              </Field>
            </div>
            <Field label="Finance type">
              <select className="form-select" value={form.finance_type}
                onChange={(e) => set('finance_type', e.target.value)}>
                <option value="">— None —</option>
                <option value="PCP">PCP</option>
                <option value="HP">HP</option>
                <option value="cash">Cash</option>
                <option value="loan">Loan</option>
              </select>
            </Field>
          </Section>

        </div>

        <div className="fq-col">

          <Section title="Cover details">
            <Field label="Product" required>
              <select className="form-select" value={form.product}
                onChange={(e) => set('product', e.target.value)} required>
                {allowedProducts.map((p) => (
                  <option key={p} value={p}>{PRODUCT_LABELS[p] ?? p}</option>
                ))}
              </select>
            </Field>
            <Field label="Term" required>
              <select className="form-select" value={form.term_months}
                onChange={(e) => set('term_months', e.target.value)}>
                <option value="12">12 months</option>
                <option value="24">24 months</option>
                <option value="36">36 months</option>
              </select>
            </Field>
            {form.product === 'GAP' && (
              <Field label="Loan amount (£)" required>
                <input className={`form-input${fieldErrors.loan_amount ? ' fq-input-error' : ''}`}
                  type="number" min="0" step="0.01" value={form.loan_amount}
                  onChange={(e) => set('loan_amount', e.target.value)} required />
                {fieldErrors.loan_amount && <span className="fq-field-error">{fieldErrors.loan_amount}</span>}
              </Field>
            )}
            {form.product === 'TLP' && form.vehicle_value && (
              <Field label="Cover limit">
                <div className="fq-derived-value">
                  £{getTlpLimit(Number(form.vehicle_value)).toLocaleString('en-GB')}
                  <span className="text-muted" style={{ marginLeft: '0.5rem', fontSize: '0.8rem' }}>based on vehicle value</span>
                </div>
              </Field>
            )}
          </Section>

          <Section title="Payment">
            <Field label="Payment type">
              <div className="qq-toggle">
                {['CASH', 'FINANCE'].map((pt) => (
                  <button key={pt} type="button"
                    className={`qq-toggle-btn${form.payment_type === pt ? ' active' : ''}`}
                    onClick={() => set('payment_type', pt)}>
                    {pt === 'CASH' ? 'Cash' : 'Finance'}
                  </button>
                ))}
              </div>
            </Field>
            {form.payment_type === 'FINANCE' && (
              <>
                <div className="fq-two-col">
                  <Field label="Deposit (£)" required>
                    <input className="form-input" type="number" min="0" step="0.01"
                      value={form.finance_deposit}
                      onChange={(e) => set('finance_deposit', e.target.value)} required />
                  </Field>
                  <Field label="Finance term" required>
                    <select className="form-select" value={form.finance_term_months}
                      onChange={(e) => set('finance_term_months', e.target.value)}>
                      <option value="12">12 months</option>
                      <option value="24">24 months</option>
                      <option value="36">36 months</option>
                    </select>
                  </Field>
                </div>
                {previewFinance && (
                  <div className="fq-finance-breakdown">
                    <div className="fq-fin-row"><span>Amount financed</span><strong>{fmt(previewFinance.financed_amount)}</strong></div>
                    <div className="fq-fin-row"><span>Monthly payment</span><strong>{fmt(previewFinance.monthly_payment)} × {form.finance_term_months} months</strong></div>
                    <div className="fq-fin-row"><span>Finance charge</span><strong>{fmt(previewFinance.finance_charge)}</strong></div>
                    <div className="fq-fin-row"><span>Representative APR</span><strong>{previewFinance.apr}%</strong></div>
                    <div className="fq-fin-divider" />
                    <div className="fq-fin-row fq-fin-total">
                      <span>Total payable (inc. deposit)</span>
                      <strong>{fmt(Number(previewFinance.total_repayable) + Number(form.finance_deposit || 0))}</strong>
                    </div>
                  </div>
                )}
              </>
            )}
          </Section>

          {error && <div className="qq-error">{error}</div>}

          <button className="btn btn-primary btn-lg" type="submit" disabled={loading}
            style={{ width: '100%' }}>
            {loading ? 'Saving quote…' : 'Save full quote'}
          </button>

        </div>
      </form>

      <style>{`
        .fq-layout {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 1.5rem;
          align-items: start;
        }
        @media (max-width: 800px) {
          .fq-layout { grid-template-columns: 1fr; }
        }
        .fq-col { display: flex; flex-direction: column; gap: 1.25rem; }
        .fq-section {
          background: var(--white);
          border: 1px solid var(--grey-200);
          border-radius: var(--radius);
          overflow: hidden;
        }
        .fq-section-title {
          padding: 0.75rem 1.25rem;
          background: var(--grey-50);
          border-bottom: 1px solid var(--grey-200);
          font-size: 0.8125rem;
          font-weight: 700;
          color: var(--grey-500);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .fq-section-body {
          padding: 1.25rem;
          display: flex;
          flex-direction: column;
          gap: 0.875rem;
        }
        .fq-two-col {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 0.875rem;
        }
        .fq-address-grid {
          display: grid;
          grid-template-columns: 2fr 1fr 1fr;
          gap: 0.875rem;
        }
        .fq-derived-value {
          padding: 0.55rem 0.75rem;
          background: var(--grey-50);
          border: 1px solid var(--grey-200);
          border-radius: var(--radius-sm);
          font-size: 0.9375rem;
          font-weight: 600;
          color: var(--grey-900);
        }
        .fq-required { color: var(--danger); }
        .fq-input-error { border-color: var(--danger) !important; }
        .fq-field-error { color: var(--danger); font-size: 0.8rem; margin-top: 0.15rem; }
        .fq-premium-preview {
          text-align: right;
          background: var(--white);
          border: 1px solid var(--grey-200);
          border-radius: var(--radius);
          padding: 0.75rem 1.25rem;
          box-shadow: var(--shadow-sm);
          min-width: 220px;
        }
        .fq-preview-label {
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--grey-500);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .fq-preview-amount {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--brand-primary);
          line-height: 1.2;
          margin-bottom: 0.25rem;
        }
        .fq-finance-breakdown {
          background: var(--grey-50);
          border-radius: var(--radius);
          padding: 0.875rem 1rem;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .fq-fin-row {
          display: flex;
          justify-content: space-between;
          font-size: 0.875rem;
          color: var(--grey-700);
          gap: 1rem;
        }
        .fq-fin-divider {
          border-top: 1px solid var(--grey-200);
        }
        .fq-fin-total {
          font-weight: 700;
          color: var(--grey-900);
          font-size: 0.9rem;
        }
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
      `}</style>
    </div>
  )
}
