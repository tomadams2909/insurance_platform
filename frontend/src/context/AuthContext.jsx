import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('token'))
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('user')
    return stored ? JSON.parse(stored) : null
  })
  const [tenantConfig, setTenantConfig] = useState(() => {
    const stored = localStorage.getItem('tenantConfig')
    return stored ? JSON.parse(stored) : null
  })

  function login(userData, accessToken, tenant) {
    localStorage.setItem('token', accessToken)
    localStorage.setItem('user', JSON.stringify(userData))
    localStorage.setItem('tenantConfig', JSON.stringify(tenant))
    setToken(accessToken)
    setUser(userData)
    setTenantConfig(tenant)
  }

  function logout() {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('tenantConfig')
    setToken(null)
    setUser(null)
    setTenantConfig(null)
  }

  return (
    <AuthContext.Provider value={{ token, user, tenantConfig, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
