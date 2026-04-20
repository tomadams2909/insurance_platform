import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import client from '../api/client'

const ALLOWED_ROLES = ['TENANT_ADMIN', 'SUPER_ADMIN', 'UNDERWRITER']

function today() {
  return new Date().toISOString().slice(0, 10)
}

function oneYearAgo() {
  const d = new Date()
  d.setFullYear(d.getFullYear() - 1)
  return d.toISOString().slice(0, 10)
}

export default function ReportsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const canAccess = ALLOWED_ROLES.includes(user?.role)

  const [dateFrom, setDateFrom] = useState(oneYearAgo())
  const [dateTo, setDateTo] = useState(today())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  if (!canAccess) {
    navigate('/dashboard')
    return null
  }

  function handleDownload() {
    if (!dateFrom || !dateTo) { setError('Both dates are required.'); return }
    if (dateFrom > dateTo) { setError('Date from must be before date to.'); return }
    setError('')
    setLoading(true)

    client.get('/reports/bdx', {
      params: { date_from: dateFrom, date_to: dateTo },
      responseType: 'blob',
    })
      .then(({ data }) => {
        const url = URL.createObjectURL(data)
        const a = document.createElement('a')
        a.href = url
        a.download = `bdx_${dateFrom}_${dateTo}.xlsx`
        a.click()
        URL.revokeObjectURL(url)
      })
      .catch(() => setError('Failed to generate report. Please try again.'))
      .finally(() => setLoading(false))
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2 className="page-title">Reports</h2>
          <p className="text-muted">Download bordereaux and transaction reports</p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 480 }}>
        <div className="card-header">
          <span style={{ fontWeight: 600 }}>BDX Report</span>
        </div>
        <div className="card-body">
          <p className="text-muted text-sm" style={{ marginBottom: '1.25rem' }}>
            All transactions for your portfolio in the selected date range, including premium, dealer fee, broker commission, and net premium to insurer.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.25rem' }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Date From</label>
              <input
                className="form-input"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Date To</label>
              <input
                className="form-input"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div className="ql-error" style={{ marginBottom: '1rem' }}>{error}</div>
          )}

          <button
            className="btn btn-primary"
            onClick={handleDownload}
            disabled={loading}
          >
            {loading ? 'Generating…' : 'Download BDX (.xlsx)'}
          </button>
        </div>
      </div>
    </div>
  )
}
