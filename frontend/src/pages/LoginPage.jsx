import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import client from '../api/client'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const params = new URLSearchParams()
      params.append('username', email)
      params.append('password', password)
      const { data } = await client.post('/auth/login', params)
      login({ email }, data.access_token, data.tenant)
      navigate('/dashboard')
    } catch {
      setError('Invalid email or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="login-brand-bar" />
          <h1 className="login-title">Insurance Platform</h1>
          <p className="login-subtitle">Sign in to your account</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label className="form-label">Email address</label>
            <input
              className="form-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              className="form-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          {error && <p className="login-error">{error}</p>}

          <button
            className="btn btn-primary btn-lg"
            type="submit"
            disabled={loading}
            style={{ width: '100%', marginTop: '0.5rem' }}
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>

      <style>{`
        .login-page {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--brand-bg);
        }
        .login-card {
          background: var(--white);
          border-radius: var(--radius-lg);
          box-shadow: var(--shadow-lg);
          width: 100%;
          max-width: 420px;
          overflow: hidden;
        }
        .login-brand {
          background: var(--brand-primary);
          padding: 2rem 2rem 1.5rem;
        }
        .login-brand-bar {
          width: 32px;
          height: 4px;
          background: var(--brand-accent);
          border-radius: 2px;
          margin-bottom: 1rem;
        }
        .login-title {
          color: white;
          font-size: 1.375rem;
          font-weight: 700;
          margin-bottom: 0.25rem;
        }
        .login-subtitle {
          color: rgba(255,255,255,0.7);
          font-size: 0.9rem;
        }
        .login-form {
          padding: 1.75rem 2rem 2rem;
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        .login-error {
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
