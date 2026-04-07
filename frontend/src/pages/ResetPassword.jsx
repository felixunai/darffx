import { useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import api from '../api'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') || ''
  const [senha, setSenha] = useState('')
  const [confirmar, setConfirmar] = useState('')
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState('')
  const [ok, setOk] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (senha !== confirmar) { setErro('As senhas não coincidem.'); return }
    if (senha.length < 6) { setErro('A senha deve ter pelo menos 6 caracteres.'); return }
    setLoading(true)
    setErro('')
    try {
      await api.post('/auth/nova-senha', { token, nova_senha: senha })
      setOk(true)
      setTimeout(() => navigate('/login'), 2500)
    } catch (err) {
      setErro(err.response?.data?.detail || 'Link inválido ou expirado.')
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
        <p style={{ color:'var(--muted)', fontSize:15, marginBottom:24 }}>Nova senha</p>

        {ok ? (
          <div style={{ textAlign:'center', padding:'16px 0' }}>
            <div style={{ fontSize:40, marginBottom:12 }}>✅</div>
            <h3 style={{ marginBottom:8 }}>Senha redefinida!</h3>
            <p style={{ color:'var(--muted)', fontSize:14 }}>Redirecionando para o login...</p>
          </div>
        ) : (
          <>
            {!token && <div style={{ color:'var(--danger)', fontSize:14, marginBottom:16 }}>Link inválido. Solicite um novo.</div>}
            {erro && (
              <div style={{ background:'rgba(255,77,109,0.1)', border:'1px solid var(--danger)', color:'var(--danger)', padding:'10px 14px', borderRadius:8, fontSize:13, marginBottom:16 }}>
                {erro}
              </div>
            )}
            <form onSubmit={handleSubmit} style={{ display:'flex', flexDirection:'column', gap:16 }}>
              <div>
                <label style={{ display:'block', fontSize:13, color:'var(--muted)', marginBottom:6 }}>Nova senha</label>
                <input type="password" value={senha} onChange={e => setSenha(e.target.value)}
                  placeholder="Mínimo 6 caracteres" required />
              </div>
              <div>
                <label style={{ display:'block', fontSize:13, color:'var(--muted)', marginBottom:6 }}>Confirmar senha</label>
                <input type="password" value={confirmar} onChange={e => setConfirmar(e.target.value)}
                  placeholder="Repita a senha" required />
              </div>
              <button type="submit" className="btn btn-primary" style={{ width:'100%' }} disabled={loading || !token}>
                {loading ? <span className="spinner" /> : 'Redefinir senha'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
