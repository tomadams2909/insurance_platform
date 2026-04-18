import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import client from '../api/client'

function StatCard({ label, value, colour }) {
  return (
    <div className="stat-card" style={{ borderTop: `3px solid ${colour}` }}>
      <div className="stat-value">{value === null ? '—' : value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

function StatGroup({ title, stats }) {
  return (
    <div className="card stat-group">
      <div className="card-header">
        <span className="page-title" style={{ fontSize: '1rem' }}>{title}</span>
      </div>
      <div className="card-body stat-grid">
        {stats.map((s) => (
          <StatCard key={s.label} label={s.label} value={s.value} colour={s.colour} />
        ))}
      </div>
    </div>
  )
}

async function fetchCount(path, status) {
  const { data } = await client.get(path, { params: { status, page_size: 1 } })
  return data.total
}

export default function DashboardPage() {
  const { user, tenantConfig } = useAuth()
  const navigate = useNavigate()
  const [counts, setCounts] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      fetchCount('/policies', 'BOUND'),
      fetchCount('/policies', 'ISSUED'),
      fetchCount('/policies', 'CANCELLED'),
      fetchCount('/quotes', 'QUICK_QUOTE'),
      fetchCount('/quotes', 'QUOTED'),
    ])
      .then(([bound, issued, cancelled, quickQuote, quoted]) => {
        setCounts({ bound, issued, cancelled, quickQuote, quoted })
      })
      .catch(() => setError('Failed to load dashboard data'))
  }, [])

  const displayName = user?.full_name || user?.email || 'there'
  const tenantName = tenantConfig?.name || user?.tenant?.name || ''

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2 className="page-title">Dashboard</h2>
          <p className="text-muted" style={{ marginTop: '0.25rem' }}>
            Welcome back, {displayName}
            {tenantName && <> · {tenantName}</>}
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-primary" onClick={() => navigate('/quotes/quick')}>
            Quick Quote
          </button>
          <button className="btn btn-primary" onClick={() => navigate('/quotes/new')}>
            Full Quote
          </button>
        </div>
      </div>

      {error && (
        <div className="dash-error">{error}</div>
      )}

      <div className="dash-groups">
        <StatGroup
          title="Policies"
          stats={[
            { label: 'Issued', value: counts?.issued ?? null, colour: 'var(--success)' },
            { label: 'Bound', value: counts?.bound ?? null, colour: 'var(--warning)' },
            { label: 'Cancelled', value: counts?.cancelled ?? null, colour: 'var(--danger)' },
          ]}
        />
        <StatGroup
          title="Quotes"
          stats={[
            { label: 'Quoted', value: counts?.quoted ?? null, colour: 'var(--info)' },
            { label: 'Quick Quote', value: counts?.quickQuote ?? null, colour: 'var(--grey-300)' },
          ]}
        />
      </div>

      <style>{`
        .dash-groups {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }
        .stat-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
          gap: 1rem;
        }
        .stat-card {
          background: var(--grey-50);
          border-radius: var(--radius);
          padding: 1rem 1.25rem;
        }
        .stat-value {
          font-size: 2rem;
          font-weight: 700;
          color: var(--grey-900);
          line-height: 1;
          margin-bottom: 0.35rem;
        }
        .stat-label {
          font-size: 0.8125rem;
          font-weight: 600;
          color: var(--grey-500);
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .dash-error {
          background: #fee2e2;
          color: var(--danger);
          border-radius: var(--radius-sm);
          padding: 0.75rem 1rem;
          font-size: 0.875rem;
          margin-bottom: 1.5rem;
        }
      `}</style>
    </div>
  )
}
