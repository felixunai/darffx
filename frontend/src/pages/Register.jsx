import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Register() {
  const { register } = useAuth()
  const navigate     = useNavigate()
  const [nome, setNome]     = useState('')
  const [email, setEmail]   = useState('')
  const [senha, setSenha]   = useState('')
  const [erro, setErro]     = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (senha.length < 6) { setErro('Senha deve ter ao menos 6 caracteres.'); return }
    setErro('')
    setLoading(true)
    try {
      await register(email, senha, nome)
      navigate('/')
    } catch (err) {
      setErro(err.response?.data?.detail || 'Erro ao criar conta.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.box}>
        <div style={styles.logo}>Darf<span style={{color:'var(--accent)'}}>FX</span></div>
        <p style={styles.sub}>Crie sua conta gratuita</p>

        {erro && <div style={styles.erro}>{erro}</div>}

        <form onSubmit={handleSubmit} style={styles.form}>
          <div>
            <label style={styles.label}>Nome</label>
            <input value={nome} onChange={e => setNome(e.target.value)} placeholder="Seu nome" />
          </div>
          <div>
            <label style={styles.label}>E-mail</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="seu@email.com" required />
          </div>
          <div>
            <label style={styles.label}>Senha</label>
            <input type="password" value={senha} onChange={e => setSenha(e.target.value)} placeholder="mínimo 6 caracteres" required />
          </div>
          <button type="submit" className="btn btn-primary" style={{width:'100%',marginTop:8}} disabled={loading}>
            {loading ? <span className="spinner" /> : 'Criar conta grátis'}
          </button>
        </form>

        <p style={styles.footer}>
          Já tem conta? <Link to="/login">Entrar</Link>
        </p>
      </div>
    </div>
  )
}

const styles = {
  page:  { minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', padding:16 },
  box:   { width:'100%', maxWidth:400, background:'var(--surface)', border:'1px solid var(--border)', borderRadius:20, padding:40 },
  logo:  { fontFamily:'Syne', fontWeight:800, fontSize:28, marginBottom:8 },
  sub:   { color:'var(--muted)', fontSize:15, marginBottom:24 },
  form:  { display:'flex', flexDirection:'column', gap:16 },
  label: { display:'block', fontSize:13, color:'var(--muted)', marginBottom:6 },
  erro:  { background:'rgba(255,77,109,0.1)', border:'1px solid var(--danger)', color:'var(--danger)', padding:'10px 14px', borderRadius:8, fontSize:13, marginBottom:16 },
  footer:{ textAlign:'center', marginTop:24, fontSize:14, color:'var(--muted)' },
}
