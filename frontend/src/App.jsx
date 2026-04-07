import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Login    from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Upload   from './pages/Upload'
import Apuracao from './pages/Apuracao'
import Admin    from './pages/Admin'

function RotaProtegida({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100vh'}}><span className="spinner" /></div>
  return user ? children : <Navigate to="/login" replace />
}

function RotaAdmin({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100vh'}}><span className="spinner" /></div>
  if (!user) return <Navigate to="/login" replace />
  if (!user.is_admin) return <Navigate to="/" replace />
  return children
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login"    element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/" element={<RotaProtegida><Dashboard /></RotaProtegida>} />
      <Route path="/upload"   element={<RotaProtegida><Upload /></RotaProtegida>} />
      <Route path="/apuracao/:id" element={<RotaProtegida><Apuracao /></RotaProtegida>} />
      <Route path="/admin"    element={<RotaAdmin><Admin /></RotaAdmin>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
