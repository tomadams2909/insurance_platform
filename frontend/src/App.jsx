import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import QuickQuotePage from './pages/QuickQuotePage'
import FullQuotePage from './pages/FullQuotePage'
import QuoteListPage from './pages/QuoteListPage'
import QuoteDetailPage from './pages/QuoteDetailPage'
import PolicyListPage from './pages/PolicyListPage'
import PolicyDetailPage from './pages/PolicyDetailPage'
import DealerManagementPage from './pages/DealerManagementPage'

function ProtectedLayout({ children }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<ProtectedLayout><DashboardPage /></ProtectedLayout>} />
          <Route path="/quotes/quick" element={<ProtectedLayout><QuickQuotePage /></ProtectedLayout>} />
          <Route path="/quotes/new" element={<ProtectedLayout><FullQuotePage /></ProtectedLayout>} />
          <Route path="/quotes" element={<ProtectedLayout><QuoteListPage /></ProtectedLayout>} />
          <Route path="/quotes/:id" element={<ProtectedLayout><QuoteDetailPage /></ProtectedLayout>} />
          <Route path="/policies" element={<ProtectedLayout><PolicyListPage /></ProtectedLayout>} />
          <Route path="/policies/:id" element={<ProtectedLayout><PolicyDetailPage /></ProtectedLayout>} />
          <Route path="/dealers" element={<ProtectedLayout><DealerManagementPage /></ProtectedLayout>} />
          <Route path="*" element={<ProtectedLayout><div className="page"><h2>Page not found</h2></div></ProtectedLayout>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
