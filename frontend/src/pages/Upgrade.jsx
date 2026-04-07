import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Layout from '../components/Layout'
import api from '../api'

const ANO_ATUAL = new Date().getFullYear()

export default function Upgrade() {
  const navigate   = useNavigate()
  const [params]   = useSearchParams()
  const cancelado  = params.get('cancelado')

  const [loading,  setLoading]  = useState(false)
  const [erro,     setErro]     = useState('')
  const [promo,    setPromo]    = useState(null)  // null = carregando

  useEffect(() => {
    if (cancelado) setErro('Pagamento cancelado. Tente novamente quando quiser.')
    api.get('/pagamento/promo')
      .then(r => setPromo(r.data))
      .catch(() => setPromo({ promo_ativa: false, preco_brl: 'R$ 69,90', preco_normal_brl: 'R$ 69,90' }))
  }, [cancelado])

  const pagar = async () => {
    setLoading(true)
    setErro('')
    try {
      const { data } = await api.post('/pagamento/checkout')
      window.location.href = data.checkout_url
    } catch (e) {
      setErro(e.response?.data?.detail || 'Erro ao iniciar pagamento.')
      setLoading(false)
    }
  }

  const precoBrl    = promo?.preco_brl || 'R$ 69,90'
  const precoNormal = promo?.preco_normal_brl || 'R$ 69,90'
  const isPromo     = promo?.promo_ativa === true

  return (
    <Layout>
      <div style={{ maxWidth:620, margin:'0 auto' }}>
        <button onClick={() => navigate(-1)}
          style={{ background:'none', border:'none', color:'var(--muted)', fontSize:13, cursor:'pointer', marginBottom:24, padding:0 }}>
          ← Voltar
        </button>

        {/* HEADER */}
        <div style={{ textAlign:'center', marginBottom:40 }}>
          <div style={{ fontSize:36, marginBottom:12 }}>{isPromo ? '🏷️' : '📊'}</div>
          <h1 style={{ fontSize:26, marginBottom:8, fontFamily:'Syne' }}>
            {isPromo ? 'Oferta Especial — Acesso Completo' : `Acesso Completo DarfFX ${ANO_ATUAL}`}
          </h1>
          <p style={{ color:'var(--muted)', fontSize:15, maxWidth:440, margin:'0 auto' }}>
            Desbloqueie o cálculo oficial e o relatório completo para declarar seu IR Forex no IRPF.
          </p>
        </div>

        {/* CARD PRINCIPAL */}
        <div style={{
          background:'var(--surface)',
          border: `2px solid ${isPromo ? 'var(--warn)' : 'var(--accent)'}`,
          borderRadius:20, padding:32, marginBottom:24,
          boxShadow: isPromo ? '0 0 40px rgba(255,179,71,0.12)' : '0 0 40px rgba(0,229,160,0.08)',
        }}>
          {/* Badge promo */}
          {isPromo && (
            <div style={{
              display:'inline-flex', alignItems:'center', gap:6, marginBottom:16,
              background:'rgba(255,179,71,0.15)', border:'1px solid rgba(255,179,71,0.5)',
              borderRadius:20, padding:'4px 14px', fontSize:12, fontWeight:700,
              color:'var(--warn)', letterSpacing:'0.5px',
            }}>
              🏷️ OFERTA ESPECIAL · TEMPO LIMITADO
            </div>
          )}

          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:24, flexWrap:'wrap', gap:12 }}>
            <div>
              <div style={{ fontSize:12, color: isPromo ? 'var(--warn)' : 'var(--accent)', fontWeight:700, letterSpacing:'1px', marginBottom:6 }}>
                ACESSO COMPLETO {ANO_ATUAL}
              </div>
              <h2 style={{ fontSize:20, fontFamily:'Syne', margin:0 }}>
                Pagamento único · Válido até 31/12/{ANO_ATUAL}
              </h2>
            </div>
            <div style={{ textAlign:'right' }}>
              {isPromo && (
                <div style={{ fontSize:14, color:'var(--muted)', textDecoration:'line-through', marginBottom:2 }}>
                  {precoNormal}
                </div>
              )}
              {!promo ? (
                <div style={{ width:100, height:40, background:'var(--surface2)', borderRadius:8 }} />
              ) : (
                <div style={{ fontSize:36, fontFamily:'Syne', fontWeight:800, color: isPromo ? 'var(--warn)' : 'var(--accent)' }}>
                  {precoBrl}
                </div>
              )}
              <div style={{ fontSize:12, color:'var(--muted)' }}>
                {isPromo ? 'preço promocional · sem assinatura' : 'pague uma vez, sem assinatura'}
              </div>
            </div>
          </div>

          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginBottom:28 }}>
            {[
              ['✓', 'Cálculo oficial do imposto (15%)'],
              ['✓', 'Compensação de prejuízos automática'],
              ['✓', 'Conversão PTAX do Banco Central'],
              ['✓', 'Relatório pronto para declarar no IRPF'],
              ['✓', 'Reprocessamento ilimitado até 31/12'],
              ['✓', 'Suporte por e-mail'],
            ].map(([icon, text], i) => (
              <div key={i} style={{ display:'flex', gap:10, alignItems:'flex-start' }}>
                <span style={{ color: isPromo ? 'var(--warn)' : 'var(--accent)', fontWeight:700, flexShrink:0 }}>{icon}</span>
                <span style={{ fontSize:14, color:'var(--muted)' }}>{text}</span>
              </div>
            ))}
          </div>

          {erro && (
            <div style={{ background:'rgba(255,77,109,0.1)', border:'1px solid var(--danger)',
              color:'var(--danger)', padding:'10px 14px', borderRadius:10, marginBottom:16, fontSize:13 }}>
              {erro}
            </div>
          )}

          <button
            className="btn btn-primary"
            style={{
              width:'100%', padding:'16px', fontSize:16, borderRadius:12,
              background: isPromo ? 'var(--warn)' : undefined,
              borderColor: isPromo ? 'var(--warn)' : undefined,
              color: isPromo ? '#000' : undefined,
            }}
            onClick={pagar}
            disabled={loading || !promo}
          >
            {loading
              ? <><span className="spinner" style={{width:16,height:16}} /> Aguarde...</>
              : `Desbloquear por ${precoBrl} →`}
          </button>

          <p style={{ textAlign:'center', fontSize:12, color:'var(--muted)', marginTop:12 }}>
            Pagamento seguro via Stripe · Cartão de crédito/débito · Acesso imediato
          </p>
        </div>

        {/* GARANTIA */}
        <div style={{
          textAlign:'center', padding:'16px 24px', background:'var(--surface)',
          borderRadius:12, border:'1px solid var(--border)', fontSize:13, color:'var(--muted)',
        }}>
          🔒 Pagamento processado pelo Stripe · Dados protegidos · Acesso ativo até 31/12/{ANO_ATUAL}
        </div>
      </div>
    </Layout>
  )
}
