import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const ICONE = {
  dashboard: '▦',
  upload: '↑',
  sair: '⇥',
}

export default function Layout({ children }) {
  const navigate  = useNavigate()
  const location  = useLocation()
  const { user, logout } = useAuth()

  const nav = (path) => navigate(path)
  const ativo = (path) => location.pathname === path ? 'nav-item active' : 'nav-item'

  return (
    <div className="layout">
      {/* SIDEBAR */}
      <aside className="sidebar">
        <div style={{ marginBottom: 32 }}>
          <div style={{ fontFamily:'Syne',fontWeight:800,fontSize:20 }}>
            Darf<span style={{color:'var(--accent)'}}>FX</span>
          </div>
          <div style={{ fontSize:12, color:'var(--muted)', marginTop:4 }}>
            {user?.email}
          </div>
        </div>

        <nav style={{ display:'flex', flexDirection:'column', gap:4, flex:1 }}>
          <button className={ativo('/')} onClick={() => nav('/')}>
            <span>▦</span> Dashboard
          </button>
          <button className={ativo('/upload')} onClick={() => nav('/upload')}>
            <span>↑</span> Novo Upload
          </button>
        </nav>

        <button
          className="nav-item"
          onClick={() => { logout(); navigate('/login') }}
          style={{ marginTop:'auto', color:'var(--danger)' }}
        >
          <span>⇥</span> Sair
        </button>
      </aside>

      {/* CONTEÚDO */}
      <main className="main-content">
        {children}
      </main>
    </div>
  )
}
