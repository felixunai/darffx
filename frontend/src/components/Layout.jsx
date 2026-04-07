import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Layout({ children }) {
  const navigate  = useNavigate()
  const location  = useLocation()
  const { user, logout } = useAuth()

  const ativo = (path) => location.pathname === path ? 'nav-item active' : 'nav-item'

  return (
    <div className="layout">
      <aside className="sidebar">
        <div style={{ marginBottom: 32 }}>
          <div style={{ fontFamily:'Syne',fontWeight:800,fontSize:20 }}>
            Darf<span style={{color:'var(--accent)'}}>FX</span>
          </div>
          <div style={{ fontSize:12, color:'var(--muted)', marginTop:4 }}>
            {user?.email}
          </div>
          {user?.plano && (
            <div style={{
              fontSize:10, marginTop:6, padding:'2px 8px', borderRadius:20, display:'inline-block',
              background: user.plano === 'free' ? 'var(--surface2)' : 'var(--accent)20',
              color: user.plano === 'free' ? 'var(--muted)' : 'var(--accent)',
              border: `1px solid ${user.plano === 'free' ? 'var(--border)' : 'var(--accent)40'}`,
              textTransform:'uppercase', letterSpacing:'0.5px', fontWeight:600,
            }}>
              {user.plano}
            </div>
          )}
        </div>

        <nav style={{ display:'flex', flexDirection:'column', gap:4, flex:1 }}>
          <button className={ativo('/')} onClick={() => navigate('/')}>
            <span>▦</span> Dashboard
          </button>
          <button className={ativo('/upload')} onClick={() => navigate('/upload')}>
            <span>↑</span> Novo Upload
          </button>
          {user?.is_admin && (
            <button className={ativo('/admin')} onClick={() => navigate('/admin')}>
              <span>⚙</span> Admin
            </button>
          )}
        </nav>

        <button
          className="nav-item"
          onClick={() => { logout(); navigate('/login') }}
          style={{ marginTop:'auto', color:'var(--danger)' }}
        >
          <span>⇥</span> Sair
        </button>
      </aside>

      <main className="main-content">
        {children}
      </main>
    </div>
  )
}
