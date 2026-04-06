import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { login }    = useAuth()
  const navigate     = useNavigate()
  const [email, setEmail]   = useState('')
  const [senha, setSenha]   = useState('')
  const [erro, setErro]     = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErro('')
    setLoading(true)
    try {
      await login(email, senha)
      navigate('/')
    } catch (err) {
      setErro(err.response?.data?.detail || 'E-mail ou senha incorretos.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.box}>
        <div style={styles.logo}>Darf<span style={{color:'var(--accent)'}}>FX</span></div>
        <p style={styles.sub}>Entre na sua conta</p>

        {erro && <div style={styles.erro}>{erro}</div>}

        <form onSubmit={handleSubmit} style={styles.form}>
          <div>
            <label style={styles.label}>E-mail</label>
            <input
              type="email" value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="seu@email.com" required
            />
          </div>
          <div>
            <label style={styles.label}>Senha</label>
            <input
              type="password" value={senha}
              onChange={e => setSenha(e.target.value)}
              placeholder="••••••••" required
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            style={{ width:'100%', marginTop:8 }}
            disabled={loading}
          >
            {loading ? <span className="spinner" /> : 'Entrar'}
          </button>
        </form>

        <p style={styles.footer}>
          Não tem conta? <Link to="/register">Criar conta grátis</Link>
        </p>
      </div>
    </div>
  )
}

const styles = {
  page: {
    minHeight:'100vh', display:'flex',
    alignItems:'center', justifyContent:'center',
    padding:16,
  },
  box: {
    width:'100%', maxWidth:400,
    background:'var(--surface)',
    border:'1px solid var(--border)',
    borderRadius:20, padding:40,
  },
  logo: {
    fontFamily:'Syne', fontWeight:800,
    fontSize:28, marginBottom:8,
  },
  sub: { color:'var(--muted)', fontSize:15, marginBottom:24 },
  form: { display:'flex', flexDirection:'column', gap:16 },
  label: { display:'block', fontSize:13, color:'var(--muted)', marginBottom:6 },
  erro: {
    background:'rgba(255,77,109,0.1)',
    border:'1px solid var(--danger)',
    color:'var(--danger)',
    padding:'10px 14px', borderRadius:8,
    fontSize:13, marginBottom:16,
  },
  footer: { textAlign:'center', marginTop:24, fontSize:14, color:'var(--muted)' },
}
