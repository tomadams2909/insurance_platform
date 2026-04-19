import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import client from '../api/client'

const PRODUCT_OPTIONS = [
  { value: '', label: 'All Products (default)' },
  { value: 'TYRE_ESSENTIAL', label: 'Tyre Essential' },
  { value: 'TYRE_PLUS', label: 'Tyre Plus' },
  { value: 'COSMETIC', label: 'Cosmetic' },
  { value: 'GAP', label: 'GAP' },
  { value: 'VRI', label: 'VRI' },
  { value: 'TLP', label: 'TLP' },
]

const PRODUCT_LABELS = {
  TYRE_ESSENTIAL: 'Tyre Essential', TYRE_PLUS: 'Tyre Plus',
  COSMETIC: 'Cosmetic', GAP: 'GAP', VRI: 'VRI', TLP: 'TLP',
}

function fmt(rate, type) {
  if (type === 'FLAT_FEE') {
    return `£${Number(rate).toFixed(2)} flat`
  }
  return `${Number(rate).toFixed(2)}%`
}

function Modal({ title, onClose, children }) {
  return (
    <div className="dm-backdrop" onClick={onClose}>
      <div className="dm-modal" onClick={(e) => e.stopPropagation()}>
        <div className="dm-modal-header">
          <span className="dm-modal-title">{title}</span>
          <button className="dm-modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="dm-modal-body">{children}</div>
      </div>
    </div>
  )
}

function Field({ label, required, children }) {
  return (
    <div className="form-group">
      <label className="form-label">{label}{required && <span className="dm-req"> *</span>}</label>
      {children}
    </div>
  )
}

export default function DealerManagementPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const isAdmin = user?.role === 'TENANT_ADMIN' || user?.role === 'SUPER_ADMIN'

  const [dealers, setDealers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Add dealer modal
  const [showAddDealer, setShowAddDealer] = useState(false)
  const [addForm, setAddForm] = useState({ name: '', contact_email: '' })
  const [addLoading, setAddLoading] = useState(false)
  const [addError, setAddError] = useState('')

  // Commission modal
  const [commissionTarget, setCommissionTarget] = useState(null) // dealer object
  const [commForm, setCommForm] = useState({ product: '', commission_type: 'PERCENTAGE', commission_rate: '' })
  const [commLoading, setCommLoading] = useState(false)
  const [commError, setCommError] = useState('')

  const loadDealers = useCallback(() => {
    setLoading(true)
    setError('')
    client.get('/dealers')
      .then(({ data }) => setDealers(data))
      .catch(() => setError('Failed to load dealers.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!isAdmin) { navigate('/dashboard'); return }
    loadDealers()
  }, [isAdmin, navigate, loadDealers])

  function handleAddDealer(e) {
    e.preventDefault()
    if (!addForm.name.trim()) { setAddError('Name is required.'); return }
    setAddLoading(true)
    setAddError('')
    client.post('/dealers', addForm)
      .then(() => {
        setShowAddDealer(false)
        setAddForm({ name: '', contact_email: '' })
        loadDealers()
      })
      .catch((err) => setAddError(err.response?.data?.detail || 'Failed to create dealer.'))
      .finally(() => setAddLoading(false))
  }

  function handleAddCommission(e) {
    e.preventDefault()
    if (!commForm.commission_rate || isNaN(Number(commForm.commission_rate))) {
      setCommError('A valid rate is required.')
      return
    }
    setCommLoading(true)
    setCommError('')
    const payload = {
      product: commForm.product || null,
      commission_type: commForm.commission_type,
      commission_rate: Number(commForm.commission_rate),
    }
    client.post(`/dealers/${commissionTarget.id}/commissions`, payload)
      .then(() => {
        setCommissionTarget(null)
        setCommForm({ product: '', commission_type: 'PERCENTAGE', commission_rate: '' })
        loadDealers()
      })
      .catch((err) => setCommError(err.response?.data?.detail || 'Failed to add commission rate.'))
      .finally(() => setCommLoading(false))
  }

  function handleDeactivateCommission(dealerId, commissionId) {
    client.delete(`/dealers/${dealerId}/commissions/${commissionId}`)
      .then(() => loadDealers())
      .catch(() => setError('Failed to deactivate commission rate.'))
  }

  function handleToggleDealer(dealer) {
    client.patch(`/dealers/${dealer.id}`, { is_active: !dealer.is_active })
      .then(() => loadDealers())
      .catch(() => setError('Failed to update dealer.'))
  }

  if (!isAdmin) return null

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2 className="page-title">Dealer Management</h2>
          <p className="text-muted">Manage dealers and their commission rates</p>
        </div>
        <button className="btn btn-primary" onClick={() => { setAddForm({ name: '', contact_email: '' }); setAddError(''); setShowAddDealer(true) }}>
          Add Dealer
        </button>
      </div>

      {error && <div className="ql-error">{error}</div>}

      {loading ? (
        <div className="card"><div className="card-body"><p className="text-muted">Loading dealers…</p></div></div>
      ) : dealers.length === 0 ? (
        <div className="card"><div className="card-body"><p className="text-muted">No dealers configured yet.</p></div></div>
      ) : (
        <div className="dm-dealer-list">
          {dealers.map((dealer) => (
            <div key={dealer.id} className={`card dm-dealer-card${!dealer.is_active ? ' dm-inactive' : ''}`}>
              <div className="card-header dm-dealer-header">
                <div>
                  <span className="dm-dealer-name">{dealer.name}</span>
                  {!dealer.is_active && <span className="badge badge-cancelled dm-inactive-badge">Inactive</span>}
                  {dealer.contact_email && <span className="text-muted text-sm dm-dealer-email">{dealer.contact_email}</span>}
                </div>
                <div className="flex gap-2">
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => { setCommissionTarget(dealer); setCommForm({ product: '', commission_type: 'PERCENTAGE', commission_rate: '' }); setCommError('') }}
                  >
                    Add Commission Rate
                  </button>
                  <button
                    className={`btn btn-sm ${dealer.is_active ? 'btn-danger' : 'btn-secondary'}`}
                    onClick={() => handleToggleDealer(dealer)}
                  >
                    {dealer.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </div>
              </div>

              <div className="card-body">
                {dealer.commissions && dealer.commissions.filter(c => c.is_active).length > 0 ? (
                  <table className="table-wrap">
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>Type</th>
                        <th>Rate</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {dealer.commissions.filter(c => c.is_active).map((c) => (
                        <tr key={c.id}>
                          <td>{c.product ? PRODUCT_LABELS[c.product] || c.product : <span className="text-muted">All products</span>}</td>
                          <td>{c.commission_type === 'PERCENTAGE' ? 'Percentage' : 'Flat Fee'}</td>
                          <td>{fmt(c.commission_rate, c.commission_type)}</td>
                          <td className="text-right">
                            <button
                              className="btn btn-danger btn-sm"
                              onClick={() => handleDeactivateCommission(dealer.id, c.id)}
                            >
                              Deactivate
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-muted text-sm">No active commission rates.</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showAddDealer && (
        <Modal title="Add Dealer" onClose={() => setShowAddDealer(false)}>
          <form onSubmit={handleAddDealer}>
            <Field label="Dealer Name" required>
              <input
                className="form-input"
                value={addForm.name}
                onChange={(e) => setAddForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="e.g. City Motors Manchester"
              />
            </Field>
            <Field label="Contact Email">
              <input
                className="form-input"
                type="email"
                value={addForm.contact_email}
                onChange={(e) => setAddForm((f) => ({ ...f, contact_email: e.target.value }))}
                placeholder="fleet@example.com"
              />
            </Field>
            {addError && <div className="ql-error">{addError}</div>}
            <div className="dm-modal-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setShowAddDealer(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={addLoading}>
                {addLoading ? 'Creating…' : 'Create Dealer'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {commissionTarget && (
        <Modal title={`Add Commission Rate — ${commissionTarget.name}`} onClose={() => setCommissionTarget(null)}>
          <form onSubmit={handleAddCommission}>
            <Field label="Product">
              <select
                className="form-select"
                value={commForm.product}
                onChange={(e) => setCommForm((f) => ({ ...f, product: e.target.value }))}
              >
                {PRODUCT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Commission Type" required>
              <select
                className="form-select"
                value={commForm.commission_type}
                onChange={(e) => setCommForm((f) => ({ ...f, commission_type: e.target.value }))}
              >
                <option value="PERCENTAGE">Percentage (%)</option>
                <option value="FLAT_FEE">Flat Fee (£)</option>
              </select>
            </Field>
            <Field label={commForm.commission_type === 'PERCENTAGE' ? 'Rate (%)' : 'Rate (£)'} required>
              <input
                className="form-input"
                type="number"
                step="0.01"
                min="0"
                value={commForm.commission_rate}
                onChange={(e) => setCommForm((f) => ({ ...f, commission_rate: e.target.value }))}
                placeholder={commForm.commission_type === 'PERCENTAGE' ? 'e.g. 15.00' : 'e.g. 50.00'}
              />
            </Field>
            {commError && <div className="ql-error">{commError}</div>}
            <div className="dm-modal-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setCommissionTarget(null)}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={commLoading}>
                {commLoading ? 'Saving…' : 'Add Rate'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      <style>{`
        .dm-dealer-list { display: flex; flex-direction: column; gap: 1.25rem; }
        .dm-dealer-card.dm-inactive { opacity: 0.65; }
        .dm-dealer-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem; }
        .dm-dealer-name { font-weight: 600; font-size: 1rem; margin-right: 0.5rem; }
        .dm-inactive-badge { margin-left: 0.25rem; }
        .dm-dealer-email { display: block; margin-top: 0.2rem; }
        .dm-req { color: var(--danger); margin-left: 2px; }
        .dm-modal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.25rem; }
        .dm-backdrop {
          position: fixed; inset: 0;
          background: rgba(0,0,0,0.45);
          display: flex; align-items: center; justify-content: center;
          z-index: 200;
        }
        .dm-modal {
          background: white;
          border-radius: var(--radius);
          box-shadow: 0 8px 32px rgba(0,0,0,0.2);
          width: 100%; max-width: 480px;
          margin: 1rem;
        }
        .dm-modal-header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 1rem 1.25rem;
          border-bottom: 1px solid var(--grey-200);
        }
        .dm-modal-title { font-weight: 600; font-size: 1rem; }
        .dm-modal-close {
          background: none; border: none; cursor: pointer;
          color: var(--grey-500); font-size: 1rem; padding: 0.25rem;
        }
        .dm-modal-close:hover { color: var(--grey-900); }
        .dm-modal-body { padding: 1.25rem; }
        .ql-error {
          background: #fef2f2; border: 1px solid #fecaca;
          color: #b91c1c; border-radius: var(--radius-sm);
          padding: 0.6rem 0.875rem; font-size: 0.875rem;
          margin-bottom: 0.75rem;
        }
      `}</style>
    </div>
  )
}
