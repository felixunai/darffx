import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [enviado, setEnviado] = useState(false)
  const [erro, setErro] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setErro('')
    try {
      await api.post('/auth/recuperar-senha', { email })
      setEnviado(true)
    } catch (err) {
      setErro(err.response?.data?.detail || 'Erro ao enviar e-mail.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
      <div style={{ width:'100%', maxWidth:400, background:'var(--surface)', border:'1px solid var(--border)', borderRadius:20, padding:40 }}>
        <div style={{ fontFamily:'Syne', fontWeight:800, fontSize:28, marginBottom:8 }}>
          Darf<span style={{color:'var(--accent)'}}>FX</span>
        </div>
        <p style={{ color:'var(--muted)', fontSize:15, marginBottom:24 }}>Recuperar senha</p>

        {enviado ? (
          <div style={{ textAlign:'center', padding:'16px 0' }}>
            <div style={{ fontSize:40, marginBottom:12 }}>📧</div>
            <h3 style={{ marginBottom:8 }}>E-mail enviado!</h3>
            <p style={{ color:'var(--muted)', fontSize:14, marginBottom:24 }}>
              Se o e-mail existir em nossa base, você receberá as instruções em instantes. Verifique sua caixa de spam.
            </p>
            <Link to="/login" style={{ color:'var(--accent)', fontSize:14 }}>← Voltar para o login</Link>
          </div>
        ) : (
          <>
            {erro && (
              <div style={{ background:'rgba(255,77,109,0.1)', border:'1px solid var(--danger)', color:'var(--danger)', padding:'10px 14px', borderRadius:8, fontSize:13, marginBottom:16 }}>
                {erro}
              </div>
            )}
            <form onSubmit={handleSubmit} style={{ display:'flex', flexDirection:'column', gap:16 }}>
              <div>
                <label style={{ display:'block', fontSize:13, color:'var(--muted)', marginBottom:6 }}>E-mail da conta</label>
                <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="seu@email.com" required />
              </div>
              <button type="submit" className="btn btn-primary" style={{ width:'100%' }} disabled={loading}>
                {loading ? <span className="spinner" /> : 'Enviar instruções'}
              </button>
            </form>
            <p style={{ textAlign:'center', marginTop:24, fontSize:14, color:'var(--muted)' }}>
              <Link to="/login">← Voltar para o login</Link>
            </p>
          </>
        )}
      </div>
    </div>
  )
}
