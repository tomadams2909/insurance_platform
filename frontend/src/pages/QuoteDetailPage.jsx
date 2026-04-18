import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import client from '../api/client'

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

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

function StatusBadge({ status }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{status.replace('_', ' ')}</span>
}

function Section({ title, children }) {
  return (
    <div className="qd-section">
      <div className="qd-section-title">{title}</div>
      <div className="qd-section-body">{children}</div>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="qd-row">
      <span className="qd-label">{label}</span>
      <span className="qd-value">{value ?? '—'}</span>
    </div>
  )
}

export default function QuoteDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [quote, setQuote] = useState(null)
  const [loading, setLoading] = useState(true)
  const [binding, setBinding] = useState(false)
  const [error, setError] = useState(null)
  const [bindError, setBindError] = useState(null)

  useEffect(() => {
    client.get(`/quotes/${id}`)
      .then(({ data }) => setQuote(data))
      .catch(() => setError('Failed to load quote.'))
      .finally(() => setLoading(false))
  }, [id])

  async function handleBind() {
    setBindError(null)
    setBinding(true)
    try {
      const { data } = await client.post(`/quotes/${id}/bind`)
      navigate(`/policies/${data.id}`)
    } catch (err) {
      const detail = err.response?.data?.detail
      setBindError(typeof detail === 'string' ? detail : 'Failed to bind policy.')
    } finally {
      setBinding(false)
    }
  }

  if (loading) return <div className="page"><p className="text-muted">Loading…</p></div>
  if (error) return <div className="page"><p style={{ color: 'var(--danger)' }}>{error}</p></div>
  if (!quote) return null

  const fb = quote.finance_breakdown
  const v = quote.vehicle
  const address = quote.customer_address
    ? [quote.customer_address.line1, quote.customer_address.city, quote.customer_address.postcode].filter(Boolean).join(', ')
    : null

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="flex items-center gap-2" style={{ marginBottom: '0.25rem' }}>
            <h2 className="page-title">{PRODUCT_LABELS[quote.product] ?? quote.product} Quote</h2>
            <StatusBadge status={quote.status} />
          </div>
          <p className="text-muted">Created {fmtDate(quote.created_at)}</p>
        </div>
        <div className="qd-premium-block">
          <div className="qd-premium-label">
            {fb ? 'Total payable (inc. deposit)' : 'Premium'}
          </div>
          <div className="qd-premium-amount">
            {fb
              ? fmt(Number(fb.total_repayable) + Number(quote.finance_deposit || 0))
              : fmt(quote.calculated_premium)}
          </div>
        </div>
      </div>

      <div className="qd-layout">
        <div className="qd-col">

          <Section title="Customer">
            <Row label="Name" value={quote.customer_name} />
            <Row label="Date of birth" value={quote.customer_dob ? fmtDate(quote.customer_dob) : null} />
            <Row label="Email" value={quote.customer_email} />
            <Row label="Address" value={address} />
          </Section>

          <Section title="Vehicle">
            <Row label="Registration" value={v?.registration} />
            <Row label="Make / Model" value={v?.make && v?.model ? `${v.make} ${v.model}` : null} />
            <Row label="Year" value={v?.year} />
            <Row label="Purchase price" value={v?.purchase_price ? fmt(v.purchase_price) : null} />
            <Row label="Purchase date" value={v?.purchase_date ? fmtDate(v.purchase_date) : null} />
            <Row label="Finance type" value={v?.finance_type} />
          </Section>

        </div>

        <div className="qd-col">

          <Section title="Cover">
            <Row label="Product" value={PRODUCT_LABELS[quote.product] ?? quote.product} />
            <Row label="Term" value={`${quote.term_months} months`} />
            {quote.product_fields?.loan_amount && (
              <Row label="Loan amount" value={fmt(quote.product_fields.loan_amount)} />
            )}
            {quote.product_fields?.tlp_limit && (
              <Row label="Cover limit" value={fmt(quote.product_fields.tlp_limit)} />
            )}
            <Row label="Premium" value={fmt(quote.calculated_premium)} />
          </Section>

          <Section title="Payment">
            <Row label="Payment type" value={quote.payment_type} />
            {fb && (
              <>
                <Row label="Down payment" value={fmt(quote.finance_deposit || 0)} />
                <Row label="Amount financed" value={fmt(fb.financed_amount)} />
                <Row label="Monthly payment" value={`${fmt(fb.monthly_payment)} × ${quote.finance_term_months} months`} />
                <Row label="Finance charge" value={fmt(fb.finance_charge)} />
                <Row label="Representative APR" value={`${fb.apr}%`} />
                <div className="qd-divider" />
                <Row label="Total payable (inc. deposit)" value={fmt(Number(fb.total_repayable) + Number(quote.finance_deposit || 0))} />
              </>
            )}
          </Section>

          {quote.status === 'QUOTED' && (
            <div className="qd-actions">
              {bindError && <div className="qd-bind-error">{bindError}</div>}
              <button
                className="btn btn-primary btn-lg"
                style={{ width: '100%' }}
                onClick={handleBind}
                disabled={binding}
              >
                {binding ? 'Binding policy…' : 'Bind Policy'}
              </button>
              <p className="text-muted" style={{ textAlign: 'center', fontSize: '0.8rem', marginTop: '0.5rem' }}>
                Binding will lock this quote and create a policy record.
              </p>
            </div>
          )}

        </div>
      </div>

      <style>{`
        .qd-layout {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 1.5rem;
          align-items: start;
        }
        @media (max-width: 800px) {
          .qd-layout { grid-template-columns: 1fr; }
        }
        .qd-col { display: flex; flex-direction: column; gap: 1.25rem; }
        .qd-section {
          background: var(--white);
          border: 1px solid var(--grey-200);
          border-radius: var(--radius);
          overflow: hidden;
        }
        .qd-section-title {
          padding: 0.75rem 1.25rem;
          background: var(--grey-50);
          border-bottom: 1px solid var(--grey-200);
          font-size: 0.8125rem;
          font-weight: 700;
          color: var(--grey-500);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .qd-section-body {
          padding: 0.25rem 0;
        }
        .qd-row {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          padding: 0.6rem 1.25rem;
          gap: 1rem;
          border-bottom: 1px solid var(--grey-50);
        }
        .qd-row:last-child { border-bottom: none; }
        .qd-label {
          font-size: 0.8125rem;
          color: var(--grey-500);
          font-weight: 500;
          white-space: nowrap;
        }
        .qd-value {
          font-size: 0.9rem;
          color: var(--grey-900);
          font-weight: 500;
          text-align: right;
        }
        .qd-divider {
          border-top: 1px solid var(--grey-200);
          margin: 0.25rem 1.25rem;
        }
        .qd-premium-block {
          text-align: right;
          background: var(--white);
          border: 1px solid var(--grey-200);
          border-radius: var(--radius);
          padding: 0.75rem 1.25rem;
          box-shadow: var(--shadow-sm);
        }
        .qd-premium-label {
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--grey-500);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .qd-premium-amount {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--brand-primary);
          line-height: 1.2;
        }
        .qd-actions {
          background: var(--white);
          border: 1px solid var(--grey-200);
          border-radius: var(--radius);
          padding: 1.25rem;
        }
        .qd-bind-error {
          background: #fee2e2;
          color: var(--danger);
          border-radius: var(--radius-sm);
          padding: 0.6rem 0.75rem;
          font-size: 0.875rem;
          margin-bottom: 0.75rem;
        }
      `}</style>
    </div>
  )
}
