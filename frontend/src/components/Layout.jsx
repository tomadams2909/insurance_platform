import NavBar from './NavBar'
import { useBranding } from '../hooks/useBranding'

export default function Layout({ children }) {
  useBranding()
  return (
    <div style={{ minHeight: '100vh', background: 'var(--brand-bg)' }}>
      <NavBar />
      <main>{children}</main>
    </div>
  )
}
