import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function NavBar() {
  const { user, tenantConfig, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  const isAdmin = user?.role === 'TENANT_ADMIN' || user?.role === 'SUPER_ADMIN'
  const canViewReports = isAdmin || user?.role === 'UNDERWRITER'

  return (
    <nav className="navbar">
      <div className="navbar-left">
        {tenantConfig?.logo_url ? (
          <Link to="/dashboard">
            <img
              src={`${import.meta.env.VITE_API_URL}${tenantConfig.logo_url}`}
              alt={tenantConfig.name}
              className="navbar-logo"
            />
          </Link>
        ) : (
          <Link to="/dashboard" className="navbar-brand-name">{tenantConfig?.name || 'Insurance Platform'}</Link>
        )}

        <div className="navbar-links">
          <Link to="/dashboard" className="navbar-link">Dashboard</Link>
          <Link to="/quotes" className="navbar-link">Quotes</Link>
          <Link to="/policies" className="navbar-link">Policies</Link>
          {isAdmin && <Link to="/dealers" className="navbar-link">Dealers</Link>}
          {canViewReports && <Link to="/reports" className="navbar-link">Reports</Link>}
        </div>
      </div>

      <div className="navbar-right">
        <span className="navbar-user">{user?.full_name || user?.email}</span>
        <button className="navbar-logout btn btn-sm" onClick={handleLogout}>
          Sign out
        </button>
      </div>

      <style>{`
        .navbar {
          background: var(--brand-primary);
          padding: 0 1.5rem;
          height: 56px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          position: sticky;
          top: 0;
          z-index: 100;
          box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }
        .navbar-left {
          display: flex;
          align-items: center;
          gap: 2rem;
        }
        .navbar-logo {
          height: 56px;
          width: auto;
        }
        .navbar-brand-name {
          color: white;
          font-weight: 700;
          font-size: 1rem;
          letter-spacing: 0.01em;
        }
        .navbar-links {
          display: flex;
          gap: 0.25rem;
        }
        .navbar-link {
          color: rgba(255,255,255,0.8);
          text-decoration: none;
          padding: 0.4rem 0.75rem;
          border-radius: var(--radius-sm);
          font-size: 0.9rem;
          font-weight: 500;
          transition: background 0.15s, color 0.15s;
        }
        .navbar-link:hover {
          background: rgba(255,255,255,0.12);
          color: white;
        }
        .navbar-right {
          display: flex;
          align-items: center;
          gap: 1rem;
        }
        .navbar-user {
          color: rgba(255,255,255,0.75);
          font-size: 0.875rem;
        }
        .navbar-logout {
          background: rgba(255,255,255,0.15);
          color: white;
          border: 1px solid rgba(255,255,255,0.25);
        }
        .navbar-logout:hover {
          background: rgba(255,255,255,0.25);
        }
      `}</style>
    </nav>
  )
}
