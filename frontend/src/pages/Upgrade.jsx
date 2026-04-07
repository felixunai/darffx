import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Layout from '../components/Layout'
import api from '../api'

const PRECO_RELATORIO = 'R$ 69,00'
const PRECO_ANUAL     = 'R$ 49,00'

export default function Upgrade() {
  const navigate   = useNavigate()
  const [params]   = useSearchParams()
  const ano        = params.get('ano')
  const cancelado  = params.get('cancelado')

  const [loadingRel,  setLoadingRel]  = useState(false)
  const [loadingAnual,setLoadingAnual]= useState(false)
  const [erro, setErro] = useState('')
  const [passo, setPasso] = useState(1)  // 1=relatorio, 2=upsell_anual

  useEffect(() => {
    if (cancelado) setErro('Pagamento cancelado. Tente novamente quando quiser.')
  }, [cancelado])

  const pagarRelatorio = async () => {
    if (!ano) return
    setLoadingRel(true)
    setErro('')
    try {
      const { data } = await api.post(`/pagamento/checkout/relatorio/${ano}`)
      window.location.href = data.checkout_url
    } catch (e) {
      setErro(e.response?.data?.detail || 'Erro ao iniciar pagamento.')
      setLoadingRel(false)
    }
  }

  const pagarAnual = async () => {
    setLoadingAnual(true)
    setErro('')
    try {
      const { data } = await api.post('/pagamento/checkout/anual')
      window.location.href = data.checkout_url
    } catch (e) {
      setErro(e.response?.data?.detail || 'Erro ao iniciar pagamento.')
      setLoadingAnual(false)
    }
  }

  return (
    <Layout>
      <div style={{ maxWidth:680, margin:'0 auto' }}>
        <button onClick={() => navigate(-1)}
          style={{ background:'none', border:'none', color:'var(--muted)', fontSize:13, cursor:'pointer', marginBottom:24, padding:0 }}>
          ← Voltar
        </button>

        {/* HEADER */}
        <div style={{ textAlign:'center', marginBottom:40 }}>
          <div style={{ fontSize:36, marginBottom:12 }}>📊</div>
          <h1 style={{ fontSize:26, marginBottom:8, fontFamily:'Syne' }}>
            {ano ? `Relatório IR Forex ${ano}` : 'Desbloquear Relatório'}
          </h1>
          <p style={{ color:'var(--muted)', fontSize:15, maxWidth:460, margin:'0 auto' }}>
            Você processou o extrato. Desbloqueie agora para ver o cálculo oficial e o relatório completo para o IRPF.
          </p>
        </div>

        {/* CARD PRINCIPAL — RELATÓRIO COMPLETO */}
        <div style={{
          background:'var(--surface)', border:'2px solid var(--accent)',
          borderRadius:20, padding:32, marginBottom:20,
          boxShadow:'0 0 40px rgba(0,229,160,0.08)',
        }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:24, flexWrap:'wrap', gap:12 }}>
            <div>
              <div style={{ fontSize:12, color:'var(--accent)', fontWeight:700, letterSpacing:'1px', marginBottom:6 }}>
                RELATÓRIO COMPLETO
              </div>
              <h2 style={{ fontSize:22, fontFamily:'Syne', margin:0 }}>
                Pagamento único — sem assinatura
              </h2>
            </div>
            <div style={{ textAlign:'right' }}>
              <div style={{ fontSize:36, fontFamily:'Syne', fontWeight:800, color:'var(--accent)' }}>
                {PRECO_RELATORIO}
              </div>
              <div style={{ fontSize:12, color:'var(--muted)' }}>pague uma vez, acesso permanente</div>
            </div>
          </div>

          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginBottom:28 }}>
            {[
              ['✓', 'Cálculo oficial do imposto (15%)'],
              ['✓', 'Compensação de prejuízos automática'],
              ['✓', 'Conversão PTAX do Banco Central'],
              ['✓', 'Relatório pronto para declarar no IRPF'],
            ].map(([icon, text], i) => (
              <div key={i} style={{ display:'flex', gap:10, alignItems:'flex-start' }}>
                <span style={{ color:'var(--accent)', fontWeight:700, flexShrink:0 }}>{icon}</span>
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
            style={{ width:'100%', padding:'16px', fontSize:16, borderRadius:12 }}
            onClick={pagarRelatorio}
            disabled={loadingRel || !ano}
          >
            {loadingRel ? <><span className="spinner" style={{width:16,height:16}} /> Aguarde...</>
              : `Desbloquear por ${PRECO_RELATORIO} →`}
          </button>

          <p style={{ textAlign:'center', fontSize:12, color:'var(--muted)', marginTop:12 }}>
            Pagamento seguro via Stripe · Cartão de crédito/débito
          </p>
        </div>

        {/* SEPARADOR */}
        <div style={{ textAlign:'center', color:'var(--muted)', fontSize:13, marginBottom:20 }}>
          — ou aproveite mais —
        </div>

        {/* UPSELL — ACESSO ANUAL */}
        <div style={{
          background:'var(--surface)', border:'1px solid var(--border)',
          borderRadius:20, padding:28, marginBottom:32,
        }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:20, flexWrap:'wrap', gap:12 }}>
            <div>
              <div style={{ fontSize:11, color:'#a78bfa', fontWeight:700, letterSpacing:'1px', marginBottom:6 }}>
                ACESSO ANUAL
              </div>
              <h2 style={{ fontSize:18, fontFamily:'Syne', margin:0 }}>
                Reprocesse quando quiser por 12 meses
              </h2>
            </div>
            <div style={{ textAlign:'right' }}>
              <div style={{ fontSize:28, fontFamily:'Syne', fontWeight:800, color:'#a78bfa' }}>
                {PRECO_ANUAL}
              </div>
              <div style={{ fontSize:12, color:'var(--muted)' }}>por 12 meses</div>
            </div>
          </div>

          <div style={{ display:'flex', flexWrap:'wrap', gap:12, marginBottom:24 }}>
            {['Reprocessamento ilimitado', 'Histórico completo de todos os anos', 'Relatórios ilimitados'].map((t, i) => (
              <span key={i} style={{
                fontSize:12, padding:'4px 12px', borderRadius:20,
                background:'rgba(167,139,250,0.1)', color:'#a78bfa',
                border:'1px solid rgba(167,139,250,0.3)',
              }}>✓ {t}</span>
            ))}
          </div>

          <button
            className="btn btn-ghost"
            style={{ width:'100%', padding:'12px', fontSize:14, borderRadius:10, borderColor:'#a78bfa', color:'#a78bfa' }}
            onClick={pagarAnual}
            disabled={loadingAnual}
          >
            {loadingAnual ? <><span className="spinner" style={{width:14,height:14}} /> Aguarde...</>
              : `Obter Acesso Anual por ${PRECO_ANUAL} →`}
          </button>
        </div>

        {/* GARANTIA */}
        <div style={{
          textAlign:'center', padding:'16px 24px', background:'var(--surface)',
          borderRadius:12, border:'1px solid var(--border)', fontSize:13, color:'var(--muted)',
        }}>
          🔒 Pagamento processado pelo Stripe · Dados protegidos · Acesso imediato após confirmação
        </div>
      </div>
    </Layout>
  )
}
