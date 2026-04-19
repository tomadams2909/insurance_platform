import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import client from '../api/client'

const PRODUCT_LABELS = {
  TYRE_ESSENTIAL: 'Tyre Essential', TYRE_PLUS: 'Tyre Plus',
  COSMETIC: 'Cosmetic', GAP: 'GAP', VRI: 'VRI', TLP: 'TLP',
}

const TX_COLOURS = {
  BIND: 'var(--info)', ISSUE: 'var(--success)',
  ENDORSEMENT: 'var(--warning)', CANCELLATION: 'var(--danger)',
  REINSTATEMENT: 'var(--success)',
}

const DOC_LABELS = {
  POLICY_SCHEDULE: 'Policy Schedule', ENDORSEMENT_CERTIFICATE: 'Endorsement Certificate',
  CANCELLATION_NOTICE: 'Cancellation Notice', REINSTATEMENT_NOTICE: 'Reinstatement Notice',
  FINANCE_AGREEMENT: 'Finance Agreement',
}

function fmt(value) {
  return Number(value).toLocaleString('en-GB', { style: 'currency', currency: 'GBP' })
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

function fmtDateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function StatusBadge({ status }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{status}</span>
}

function Section({ title, children }) {
  return (
    <div className="pd-section">
      <div className="pd-section-title">{title}</div>
      <div className="pd-section-body">{children}</div>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="pd-row">
      <span className="pd-label">{label}</span>
      <span className="pd-value">{value ?? '—'}</span>
    </div>
  )
}

function Modal({ title, onClose, children }) {
  return (
    <div className="pd-modal-backdrop" onClick={onClose}>
      <div className="pd-modal" onClick={(e) => e.stopPropagation()}>
        <div className="pd-modal-header">
          <span className="pd-modal-title">{title}</span>
          <button className="pd-modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="pd-modal-body">{children}</div>
      </div>
    </div>
  )
}

function addMonths(dateStr, months) {
  const d = new Date(dateStr)
  d.setMonth(d.getMonth() + months)
  return d.toISOString().slice(0, 10)
}

function proRataRefund(premium, inceptionDate, expiryDate, cancellationDate) {
  const total = new Date(expiryDate) - new Date(inceptionDate)
  const remaining = new Date(expiryDate) - new Date(cancellationDate)
  if (remaining <= 0) return 0
  return Number(premium) * (remaining / total)
}

export default function PolicyDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [policy, setPolicy] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [documents, setDocuments] = useState([])
  const [tab, setTab] = useState('details')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [modal, setModal] = useState(null) // 'issue' | 'endorse' | 'cancel' | 'reinstate'
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState(null)

  // Endorse form
  const [endorseFields, setEndorseFields] = useState({ customer_name: '', customer_email: '', customer_address_line1: '', customer_address_city: '', customer_address_postcode: '', reason: '' })
  // Cancel form
  const [cancelForm, setCancelForm] = useState({ reason: '', cancellation_date: new Date().toISOString().slice(0, 10) })
  // Reinstate form
  const [reinstateForm, setReinstateForm] = useState({ reinstatement_date: new Date().toISOString().slice(0, 10) })

  const fetchAll = useCallback(() => {
    setLoading(true)
    Promise.all([
      client.get(`/policies/${id}`),
      client.get(`/policies/${id}/transactions`),
      client.get(`/policies/${id}/documents`),
    ])
      .then(([p, t, d]) => {
        setPolicy(p.data)
        setTransactions(t.data)
        setDocuments(d.data)
      })
      .catch(() => setError('Failed to load policy.'))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => { fetchAll() }, [fetchAll])

  function openModal(name) {
    setActionError(null)
    if (name === 'endorse' && policy) {
      const cd = policy.policy_data || {}
      const customer = cd.customer || {}
      const addr = customer.address || {}
      setEndorseFields({
        customer_name: customer.name || '',
        customer_email: customer.email || '',
        customer_address_line1: addr.line1 || '',
        customer_address_city: addr.city || '',
        customer_address_postcode: addr.postcode || '',
        reason: '',
      })
    }
    setModal(name)
  }

  async function handleIssue() {
    setActionLoading(true)
    setActionError(null)
    try {
      await client.post(`/policies/${id}/issue`)
      setModal(null)
      fetchAll()
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to issue policy.')
    } finally {
      setActionLoading(false)
    }
  }

  async function handleEndorse() {
    setActionLoading(true)
    setActionError(null)
    try {
      const changed_fields = {}
      const orig = policy.policy_data?.customer || {}
      if (endorseFields.customer_name && endorseFields.customer_name !== orig.name)
        changed_fields.customer_name = endorseFields.customer_name
      if (endorseFields.customer_email && endorseFields.customer_email !== orig.email)
        changed_fields.customer_email = endorseFields.customer_email
      if (endorseFields.customer_address_line1 || endorseFields.customer_address_city || endorseFields.customer_address_postcode)
        changed_fields.customer_address = {
          line1: endorseFields.customer_address_line1,
          city: endorseFields.customer_address_city,
          postcode: endorseFields.customer_address_postcode,
        }
      if (!Object.keys(changed_fields).length) {
        setActionError('No fields have been changed.')
        setActionLoading(false)
        return
      }
      await client.post(`/policies/${id}/endorse`, { changed_fields, reason: endorseFields.reason })
      setModal(null)
      fetchAll()
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to endorse policy.')
    } finally {
      setActionLoading(false)
    }
  }

  async function handleCancel() {
    setActionLoading(true)
    setActionError(null)
    try {
      await client.post(`/policies/${id}/cancel`, {
        reason: cancelForm.reason,
        cancellation_date: cancelForm.cancellation_date,
      })
      setModal(null)
      fetchAll()
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to cancel policy.')
    } finally {
      setActionLoading(false)
    }
  }

  async function handleReinstate() {
    setActionLoading(true)
    setActionError(null)
    try {
      await client.post(`/policies/${id}/reinstate`, {
        reinstatement_date: reinstateForm.reinstatement_date,
      })
      setModal(null)
      fetchAll()
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to reinstate policy.')
    } finally {
      setActionLoading(false)
    }
  }

  async function downloadDocument(docId, filename) {
    const response = await client.get(`/documents/${docId}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  if (loading) return <div className="page"><p className="text-muted">Loading…</p></div>
  if (error) return <div className="page"><p style={{ color: 'var(--danger)' }}>{error}</p></div>
  if (!policy) return null

  const cd = policy.policy_data || {}
  const customer = cd.customer || {}
  const vehicle = cd.vehicle || {}
  const fb = cd.finance_breakdown
  const address = customer.address
    ? [customer.address.line1, customer.address.city, customer.address.postcode].filter(Boolean).join(', ')
    : null

  const estimatedRefund = policy.status === 'ISSUED'
    ? proRataRefund(policy.premium, policy.inception_date, policy.expiry_date, cancelForm.cancellation_date)
    : 0

  const newExpiry = addMonths(reinstateForm.reinstatement_date, policy.term_months)

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="flex items-center gap-2" style={{ marginBottom: '0.25rem' }}>
            <h2 className="page-title">{policy.policy_number}</h2>
            <StatusBadge status={policy.status} />
          </div>
          <p className="text-muted">
            {PRODUCT_LABELS[policy.product] ?? policy.product} · {fmtDate(policy.inception_date)} – {fmtDate(policy.expiry_date)}
          </p>
        </div>
        <div className="flex gap-2">
          {policy.status === 'BOUND' && (
            <button className="btn btn-primary" onClick={() => openModal('issue')}>Issue Policy</button>
          )}
          {policy.status === 'ISSUED' && (
            <>
              <button className="btn btn-secondary" onClick={() => openModal('endorse')}>Endorse</button>
              <button className="btn btn-danger" onClick={() => openModal('cancel')}>Cancel</button>
            </>
          )}
          {policy.status === 'CANCELLED' && (
            <button className="btn btn-primary" onClick={() => openModal('reinstate')}>Reinstate</button>
          )}
        </div>
      </div>

      <div className="pd-tabs">
        {['details', 'transactions', 'documents'].map((t) => (
          <button key={t} className={`pd-tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
            {t === 'transactions' && transactions.length > 0 && <span className="pd-tab-count">{transactions.length}</span>}
            {t === 'documents' && documents.length > 0 && <span className="pd-tab-count">{documents.length}</span>}
          </button>
        ))}
      </div>

      {tab === 'details' && (
        <div className="pd-layout">
          <div className="pd-col">
            <Section title="Customer">
              <Row label="Name" value={customer.name} />
              <Row label="Email" value={customer.email} />
              <Row label="Address" value={address} />
            </Section>

            <Section title="Vehicle">
              <Row label="Registration" value={vehicle.registration} />
              <Row label="Make / Model" value={vehicle.make && vehicle.model ? `${vehicle.make} ${vehicle.model}` : null} />
              <Row label="Year" value={vehicle.year} />
              <Row label="Purchase price" value={vehicle.purchase_price ? fmt(vehicle.purchase_price) : null} />
              <Row label="Purchase date" value={vehicle.purchase_date ? fmtDate(vehicle.purchase_date) : null} />
              <Row label="Finance type" value={vehicle.finance_type} />
            </Section>
          </div>

          <div className="pd-col">
            <Section title="Cover">
              <Row label="Product" value={PRODUCT_LABELS[policy.product] ?? policy.product} />
              <Row label="Term" value={`${policy.term_months} months`} />
              <Row label="Inception" value={fmtDate(policy.inception_date)} />
              <Row label="Expiry" value={fmtDate(policy.expiry_date)} />
              {cd.product_fields?.loan_amount && <Row label="Loan amount" value={fmt(cd.product_fields.loan_amount)} />}
              {cd.product_fields?.tlp_limit && <Row label="Cover limit" value={fmt(cd.product_fields.tlp_limit)} />}
              <Row label="Premium" value={fmt(policy.premium)} />
            </Section>

            <Section title="Payment">
              <Row label="Payment type" value={policy.payment_type} />
              {fb ? (
                <>
                  <Row label="Down payment" value={fmt(cd.finance_deposit || 0)} />
                  <Row label="Amount financed" value={fmt(fb.financed_amount)} />
                  <Row label="Monthly payment" value={`${fmt(fb.monthly_payment)} × ${cd.finance_term_months} months`} />
                  <Row label="Finance charge" value={fmt(fb.finance_charge)} />
                  <Row label="Representative APR" value={`${fb.apr}%`} />
                  <div className="pd-divider" />
                  <Row label="Total payable (inc. deposit)" value={fmt(Number(fb.total_repayable) + Number(cd.finance_deposit || 0))} />
                </>
              ) : (
                <Row label="Premium" value={fmt(policy.premium)} />
              )}
            </Section>

            {cd.dealer && (
              <Section title="Fee Disclosure">
                <Row label="Dealer" value={cd.dealer.name} />
                <Row label="Dealer fee" value={policy.dealer_fee ? fmt(policy.dealer_fee) : null} />
                <Row label="Broker commission" value={policy.broker_commission ? fmt(policy.broker_commission) : null} />
                <Row label="Net premium to insurer" value={
                  policy.broker_commission != null
                    ? fmt(Number(policy.premium) - Number(policy.broker_commission))
                    : null
                } />
              </Section>
            )}
          </div>
        </div>
      )}

      {tab === 'transactions' && (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Date</th>
                  <th>Description</th>
                  <th className="text-right">Premium</th>
                  <th className="text-right">Broker comm.</th>
                </tr>
              </thead>
              <tbody>
                {transactions.length === 0 && (
                  <tr><td colSpan="5" className="ql-empty">No transactions</td></tr>
                )}
                {transactions.map((tx) => (
                  <tr key={tx.id} style={{ cursor: 'default' }}>
                    <td>
                      <span className="pd-tx-badge" style={{ background: TX_COLOURS[tx.transaction_type] }}>
                        {tx.transaction_type}
                      </span>
                    </td>
                    <td>{fmtDateTime(tx.created_at)}</td>
                    <td>{tx.description}</td>
                    <td className="text-right" style={{
                      color: tx.premium_delta > 0 ? 'var(--success)' : tx.premium_delta < 0 ? 'var(--danger)' : 'var(--grey-500)',
                      fontWeight: tx.premium_delta ? 600 : 400,
                    }}>
                      {tx.premium_delta != null ? `${tx.premium_delta > 0 ? '+' : ''}${fmt(tx.premium_delta)}` : '—'}
                    </td>
                    <td className="text-right" style={{
                      color: tx.broker_commission_delta > 0 ? 'var(--success)' : tx.broker_commission_delta < 0 ? 'var(--danger)' : 'var(--grey-500)',
                      fontWeight: tx.broker_commission_delta ? 600 : 400,
                    }}>
                      {tx.broker_commission_delta != null ? `${tx.broker_commission_delta > 0 ? '+' : ''}${fmt(tx.broker_commission_delta)}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'documents' && (
        <div className="card">
          <div className="pd-doc-list">
            {documents.length === 0 && (
              <p className="text-muted" style={{ padding: '2rem', textAlign: 'center' }}>No documents yet</p>
            )}
            {documents.map((doc) => (
              <div key={doc.id} className="pd-doc-row">
                <div>
                  <div className="pd-doc-name">{DOC_LABELS[doc.document_type] ?? doc.document_type}</div>
                  <div className="text-muted">{fmtDateTime(doc.created_at)}</div>
                </div>
                <button className="btn btn-secondary btn-sm"
                  onClick={() => downloadDocument(doc.id, doc.filename)}>
                  Download PDF
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Modals ─────────────────────────────────────────────────────── */}

      {modal === 'issue' && (
        <Modal title="Issue Policy" onClose={() => setModal(null)}>
          <p style={{ marginBottom: '1rem', color: 'var(--grey-700)' }}>
            Issuing this policy will generate the policy schedule document and mark it as active.
          </p>
          {actionError && <div className="pd-action-error">{actionError}</div>}
          <div className="pd-modal-footer">
            <button className="btn btn-secondary" onClick={() => setModal(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={handleIssue} disabled={actionLoading}>
              {actionLoading ? 'Issuing…' : 'Confirm Issue'}
            </button>
          </div>
        </Modal>
      )}

      {modal === 'endorse' && (
        <Modal title="Endorse Policy" onClose={() => setModal(null)}>
          <p className="text-muted" style={{ marginBottom: '1rem' }}>Update customer details. Leave unchanged fields as-is.</p>
          <div className="pd-modal-form">
            <div className="form-group">
              <label className="form-label">Customer name</label>
              <input className="form-input" type="text" value={endorseFields.customer_name}
                onChange={(e) => setEndorseFields((f) => ({ ...f, customer_name: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input className="form-input" type="email" value={endorseFields.customer_email}
                onChange={(e) => setEndorseFields((f) => ({ ...f, customer_email: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Address line 1</label>
              <input className="form-input" type="text" value={endorseFields.customer_address_line1}
                onChange={(e) => setEndorseFields((f) => ({ ...f, customer_address_line1: e.target.value }))} />
            </div>
            <div className="pd-two-col">
              <div className="form-group">
                <label className="form-label">City</label>
                <input className="form-input" type="text" value={endorseFields.customer_address_city}
                  onChange={(e) => setEndorseFields((f) => ({ ...f, customer_address_city: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Postcode</label>
                <input className="form-input" type="text" value={endorseFields.customer_address_postcode}
                  onChange={(e) => setEndorseFields((f) => ({ ...f, customer_address_postcode: e.target.value }))} />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Reason <span style={{ color: 'var(--danger)' }}>*</span></label>
              <input className="form-input" type="text" value={endorseFields.reason}
                onChange={(e) => setEndorseFields((f) => ({ ...f, reason: e.target.value }))}
                placeholder="Reason for endorsement" required />
            </div>
          </div>
          {actionError && <div className="pd-action-error">{actionError}</div>}
          <div className="pd-modal-footer">
            <button className="btn btn-secondary" onClick={() => setModal(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={handleEndorse} disabled={actionLoading || !endorseFields.reason}>
              {actionLoading ? 'Saving…' : 'Save Endorsement'}
            </button>
          </div>
        </Modal>
      )}

      {modal === 'cancel' && (
        <Modal title="Cancel Policy" onClose={() => setModal(null)}>
          <div className="pd-modal-form">
            <div className="form-group">
              <label className="form-label">Cancellation date</label>
              <input className="form-input" type="date" value={cancelForm.cancellation_date}
                min={policy.inception_date}
                max={policy.expiry_date}
                onChange={(e) => setCancelForm((f) => ({ ...f, cancellation_date: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Reason <span style={{ color: 'var(--danger)' }}>*</span></label>
              <input className="form-input" type="text" value={cancelForm.reason}
                onChange={(e) => setCancelForm((f) => ({ ...f, reason: e.target.value }))}
                placeholder="Reason for cancellation" required />
            </div>
            <div className="pd-calc-box">
              <span className="text-muted">Estimated refund</span>
              <strong style={{ color: 'var(--success)' }}>{fmt(estimatedRefund)}</strong>
            </div>
          </div>
          {actionError && <div className="pd-action-error">{actionError}</div>}
          <div className="pd-modal-footer">
            <button className="btn btn-secondary" onClick={() => setModal(null)}>Back</button>
            <button className="btn btn-danger" onClick={handleCancel} disabled={actionLoading || !cancelForm.reason}>
              {actionLoading ? 'Cancelling…' : 'Confirm Cancellation'}
            </button>
          </div>
        </Modal>
      )}

      {modal === 'reinstate' && (
        <Modal title="Reinstate Policy" onClose={() => setModal(null)}>
          <div className="pd-modal-form">
            <div className="form-group">
              <label className="form-label">Reinstatement date</label>
              <input className="form-input" type="date" value={reinstateForm.reinstatement_date}
                onChange={(e) => setReinstateForm({ reinstatement_date: e.target.value })} />
            </div>
            <div className="pd-calc-box">
              <span className="text-muted">New expiry date</span>
              <strong>{fmtDate(newExpiry)}</strong>
            </div>
          </div>
          {actionError && <div className="pd-action-error">{actionError}</div>}
          <div className="pd-modal-footer">
            <button className="btn btn-secondary" onClick={() => setModal(null)}>Back</button>
            <button className="btn btn-primary" onClick={handleReinstate} disabled={actionLoading}>
              {actionLoading ? 'Reinstating…' : 'Confirm Reinstatement'}
            </button>
          </div>
        </Modal>
      )}

      <style>{`
        .pd-tabs {
          display: flex;
          gap: 0.25rem;
          margin-bottom: 1.25rem;
          border-bottom: 2px solid var(--grey-200);
        }
        .pd-tab {
          padding: 0.6rem 1.1rem;
          border: none;
          background: none;
          font-size: 0.9rem;
          font-weight: 600;
          color: var(--grey-500);
          cursor: pointer;
          border-bottom: 2px solid transparent;
          margin-bottom: -2px;
          display: flex;
          align-items: center;
          gap: 0.4rem;
          transition: color 0.15s;
        }
        .pd-tab:hover { color: var(--grey-900); }
        .pd-tab.active { color: var(--brand-primary); border-bottom-color: var(--brand-primary); }
        .pd-tab-count {
          background: var(--grey-200);
          color: var(--grey-700);
          border-radius: 999px;
          font-size: 0.7rem;
          padding: 0.1rem 0.45rem;
          font-weight: 700;
        }
        .pd-layout {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 1.5rem;
          align-items: start;
        }
        @media (max-width: 800px) { .pd-layout { grid-template-columns: 1fr; } }
        .pd-col { display: flex; flex-direction: column; gap: 1.25rem; }
        .pd-section {
          background: var(--white);
          border: 1px solid var(--grey-200);
          border-radius: var(--radius);
          overflow: hidden;
        }
        .pd-section-title {
          padding: 0.75rem 1.25rem;
          background: var(--grey-50);
          border-bottom: 1px solid var(--grey-200);
          font-size: 0.8125rem;
          font-weight: 700;
          color: var(--grey-500);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .pd-section-body { padding: 0.25rem 0; }
        .pd-row {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          padding: 0.6rem 1.25rem;
          gap: 1rem;
          border-bottom: 1px solid var(--grey-50);
        }
        .pd-row:last-child { border-bottom: none; }
        .pd-label { font-size: 0.8125rem; color: var(--grey-500); font-weight: 500; white-space: nowrap; }
        .pd-value { font-size: 0.9rem; color: var(--grey-900); font-weight: 500; text-align: right; }
        .pd-divider { border-top: 1px solid var(--grey-200); margin: 0.25rem 1.25rem; }
        .pd-tx-badge {
          display: inline-block;
          padding: 0.2rem 0.55rem;
          border-radius: 999px;
          font-size: 0.7rem;
          font-weight: 700;
          color: white;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .pd-doc-list { display: flex; flex-direction: column; }
        .pd-doc-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 1rem 1.25rem;
          border-bottom: 1px solid var(--grey-100);
        }
        .pd-doc-row:last-child { border-bottom: none; }
        .pd-doc-name { font-weight: 600; font-size: 0.9rem; color: var(--grey-900); margin-bottom: 0.2rem; }
        .pd-modal-backdrop {
          position: fixed; inset: 0;
          background: rgba(0,0,0,0.4);
          display: flex; align-items: center; justify-content: center;
          z-index: 200;
        }
        .pd-modal {
          background: var(--white);
          border-radius: var(--radius-lg);
          box-shadow: var(--shadow-lg);
          width: 100%;
          max-width: 480px;
          overflow: hidden;
        }
        .pd-modal-header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 1rem 1.25rem;
          border-bottom: 1px solid var(--grey-200);
        }
        .pd-modal-title { font-weight: 700; font-size: 1rem; }
        .pd-modal-close { background: none; border: none; font-size: 1rem; cursor: pointer; color: var(--grey-500); }
        .pd-modal-body { padding: 1.25rem; }
        .pd-modal-form { display: flex; flex-direction: column; gap: 0.875rem; margin-bottom: 1rem; }
        .pd-modal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1rem; }
        .pd-two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
        .pd-calc-box {
          display: flex; justify-content: space-between; align-items: center;
          background: var(--grey-50);
          border-radius: var(--radius);
          padding: 0.75rem 1rem;
          font-size: 0.9rem;
        }
        .pd-action-error {
          background: #fee2e2; color: var(--danger);
          border-radius: var(--radius-sm);
          padding: 0.6rem 0.75rem;
          font-size: 0.875rem;
          margin-bottom: 0.75rem;
        }
        .ql-empty { text-align: center; padding: 2rem; color: var(--grey-500); }
      `}</style>
    </div>
  )
}
