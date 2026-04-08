import { useState, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import Layout from '../components/Layout'
import api from '../api'
import { useAuth } from '../context/AuthContext'

const MESES_CURTO = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

const r2     = (v) => Math.round((v || 0) * 100) / 100
const fmtBRL = (v) => `R$ ${r2(v).toLocaleString('pt-BR', { minimumFractionDigits:2, maximumFractionDigits:2 })}`
const fmtUSD = (v) => `US$ ${r2(v).toLocaleString('pt-BR', { minimumFractionDigits:2, maximumFractionDigits:2 })}`
const fmtVenc = (iso) => {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

export default function ApuracaoAnual() {
  const { ano }    = useParams()
  const navigate   = useNavigate()
  const [params]   = useSearchParams()
  const [dados,       setDados]       = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [pagando,     setPagando]     = useState(false)
  const [comprando,   setComprando]   = useState(false)
  const [promo,       setPromo]       = useState(null)
  const { refreshUser } = useAuth()

  useEffect(() => {
    api.get(`/apuracao/anual/${ano}`)
      .then(r => setDados(r.data))
      .catch(() => navigate('/'))
      .finally(() => setLoading(false))
    api.get('/pagamento/promo')
      .then(r => setPromo(r.data))
      .catch(() => setPromo({ promo_ativa: false, preco_brl: 'R$ 69,90' }))
  }, [ano])

  const irParaCheckout = async () => {
    setComprando(true)
    try {
      const { data } = await api.post('/pagamento/checkout')
      window.location.href = data.checkout_url
    } catch (e) {
      alert(e.response?.data?.detail || 'Erro ao iniciar pagamento.')
      setComprando(false)
    }
  }

  // Exibe sucesso de desbloqueio após retorno do Stripe
  const acabouDeDesbloquear = params.get('desbloqueado') === '1'

  // Atualiza plano no contexto após pagamento (webhook pode demorar ~1s)
  useEffect(() => {
    if (acabouDeDesbloquear) {
      const t = setTimeout(() => refreshUser(), 2000)
      return () => clearTimeout(t)
    }
  }, [acabouDeDesbloquear])

  const marcarPago = async () => {
    setPagando(true)
    try {
      await api.patch(`/apuracao/anual/${ano}/pago`)
      setDados(d => ({ ...d, darf_pago: true }))
    } finally { setPagando(false) }
  }

  const desfazerPago = async () => {
    setPagando(true)
    try {
      await api.patch(`/apuracao/anual/${ano}/pendente`)
      setDados(d => ({ ...d, darf_pago: false }))
    } finally { setPagando(false) }
  }

  const exportarPDF = () => window.print()

  if (loading) return <Layout><div style={{textAlign:'center',padding:80}}><span className="spinner" style={{width:32,height:32}} /></div></Layout>

  const desbloqueado = dados.desbloqueado

  return (
    <Layout>
      <div style={{ maxWidth:900, margin:'0 auto' }}>
        {/* HEADER */}
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:32, flexWrap:'wrap', gap:12 }}>
          <div>
            <button onClick={() => navigate('/')} className="no-print"
              style={{ background:'none',border:'none',color:'var(--muted)',fontSize:13,cursor:'pointer',marginBottom:8,padding:0 }}>
              ← Voltar
            </button>
            <h1 style={{ fontSize:26, marginBottom:4 }}>Apuração {ano}</h1>
            <p style={{ color:'var(--muted)', fontSize:13 }}>
              Lei 14.754/2023 · Alíquota fixa 15% · Aplicações financeiras no exterior
            </p>
          </div>
          <div className="no-print" style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
            {desbloqueado && (
              <button className="btn btn-ghost" onClick={exportarPDF}
                style={{ fontSize:13 }}>
                ↓ Exportar PDF
              </button>
            )}
            {desbloqueado && !dados.darf_pago && r2(dados.imposto_brl) > 0 && (
              <button className="btn btn-ghost" onClick={marcarPago} disabled={pagando}>
                {pagando ? <span className="spinner" style={{width:14,height:14}} /> : '✓ Marcar imposto como pago'}
              </button>
            )}
            {desbloqueado && dados.darf_pago && (
              <button className="btn btn-ghost" onClick={desfazerPago} disabled={pagando}
                style={{ color:'var(--muted)', fontSize:13 }}>
                {pagando ? <span className="spinner" style={{width:14,height:14}} /> : '↩ Desfazer — voltar para A pagar'}
              </button>
            )}
          </div>
        </div>

        {/* BANNER DESBLOQUEIO SUCESSO */}
        {acabouDeDesbloquear && (
          <div className="no-print" style={{
            background:'rgba(0,229,160,0.1)', border:'1px solid var(--accent)',
            borderRadius:12, padding:'16px 20px', marginBottom:24,
            display:'flex', alignItems:'center', gap:12
          }}>
            <span style={{ fontSize:20 }}>🎉</span>
            <div>
              <div style={{ fontWeight:600, color:'var(--accent)' }}>Relatório desbloqueado com sucesso!</div>
              <div style={{ fontSize:13, color:'var(--muted)' }}>Seu pagamento foi confirmado. O relatório completo está disponível abaixo.</div>
            </div>
          </div>
        )}

        {/* CARDS */}
        <div className="grid-4" style={{ marginBottom:24 }}>
          <div className="card">
            <div style={s.label}>Lucro líquido (USD)</div>
            <div style={{ ...s.valor, color: r2(dados.lucro_usd) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
              {r2(dados.lucro_usd) >= 0 ? '+' : ''}{fmtUSD(dados.lucro_usd)}
            </div>
          </div>
          <div className="card">
            <div style={s.label}>Lucro líquido (BRL)</div>
            <div style={{ ...s.valor, color: r2(dados.lucro_brl) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
              {fmtBRL(dados.lucro_brl)}
            </div>
          </div>
          <div className="card" style={{ position:'relative', overflow:'hidden' }}>
            <div style={s.label}>Base tributável</div>
            {desbloqueado
              ? <div style={s.valor}>{fmtBRL(dados.base_tributavel_brl)}</div>
              : <LockedValue />
            }
          </div>
          <div className="card" style={{
            borderColor: desbloqueado && r2(dados.imposto_brl) > 0 ? 'rgba(255,179,71,0.3)' : 'rgba(0,229,160,0.3)',
            position:'relative', overflow:'hidden'
          }}>
            <div style={s.label}>Imposto devido (15%)</div>
            {desbloqueado
              ? <div style={{ ...s.valor, color: r2(dados.imposto_brl) > 0 ? 'var(--warn)' : 'var(--accent)' }}>
                  {fmtBRL(dados.imposto_brl)}
                </div>
              : <LockedValue />
            }
          </div>
        </div>

        {/* PAYWALL (plano free) */}
        {!desbloqueado && (
          <div className="no-print" style={{
            background: promo?.promo_ativa
              ? 'linear-gradient(135deg,rgba(255,179,71,0.06),rgba(255,120,0,0.04))'
              : 'linear-gradient(135deg,rgba(0,229,160,0.05),rgba(0,149,255,0.05))',
            border: `2px solid ${promo?.promo_ativa ? 'var(--warn)' : 'var(--accent)'}`,
            borderRadius:20, padding:32, textAlign:'center', marginBottom:24,
          }}>
            {promo?.promo_ativa && (
              <div style={{
                display:'inline-flex', alignItems:'center', gap:6, marginBottom:14,
                background:'rgba(255,179,71,0.15)', border:'1px solid rgba(255,179,71,0.4)',
                borderRadius:20, padding:'4px 14px', fontSize:12, fontWeight:700, color:'var(--warn)',
              }}>
                🏷️ OFERTA ESPECIAL · TEMPO LIMITADO
              </div>
            )}

            <div style={{ fontSize:36, marginBottom:10 }}>🔒</div>
            <h2 style={{ fontSize:22, marginBottom:8, fontFamily:'Syne' }}>
              Desbloqueie o Relatório Completo
            </h2>
            <p style={{ color:'var(--muted)', fontSize:15, maxWidth:420, margin:'0 auto 20px' }}>
              Você pode ver seu lucro estimado. Para o cálculo oficial do imposto e o relatório
              para declaração, desbloqueie por{' '}
              {promo?.promo_ativa && (
                <span style={{ textDecoration:'line-through', color:'var(--muted)', fontSize:13, marginRight:4 }}>
                  R$ 69,90
                </span>
              )}
              <strong style={{ color: promo?.promo_ativa ? 'var(--warn)' : 'var(--accent)' }}>
                {promo ? promo.preco_brl : 'R$ 69,90'}
              </strong>
              {' '}— pagamento único, sem assinatura.
            </p>

            <div style={{ display:'flex', gap:10, justifyContent:'center', flexWrap:'wrap', marginBottom:22 }}>
              {['Cálculo oficial 15%','PTAX automático','Compensação de prejuízos','Relatório para IRPF'].map((f, i) => (
                <span key={i} style={{
                  fontSize:12, padding:'5px 14px', borderRadius:20,
                  background: promo?.promo_ativa ? 'rgba(255,179,71,0.1)' : 'rgba(0,229,160,0.1)',
                  color: promo?.promo_ativa ? 'var(--warn)' : 'var(--accent)',
                  border: `1px solid ${promo?.promo_ativa ? 'rgba(255,179,71,0.3)' : 'rgba(0,229,160,0.3)'}`,
                }}>✓ {f}</span>
              ))}
            </div>

            <button
              className="btn btn-primary"
              style={{
                padding:'14px 40px', fontSize:16, borderRadius:12,
                background: promo?.promo_ativa ? 'var(--warn)' : undefined,
                borderColor: promo?.promo_ativa ? 'var(--warn)' : undefined,
                color: promo?.promo_ativa ? '#000' : undefined,
                opacity: comprando ? 0.8 : 1,
              }}
              onClick={irParaCheckout}
              disabled={comprando}
            >
              {comprando
                ? <><span className="spinner" style={{width:14,height:14}} /> Aguarde...</>
                : `Desbloquear por ${promo ? promo.preco_brl : 'R$ 69,90'} →`}
            </button>

            <p style={{ fontSize:12, color:'var(--muted)', marginTop:12 }}>
              Pagamento seguro via Stripe · Acesso imediato
            </p>
          </div>
        )}

        {/* BOX DECLARAÇÃO (só se desbloqueado) */}
        {desbloqueado && (
          <div style={{
            background:'var(--surface)', border:`1px solid ${dados.darf_pago ? 'rgba(0,149,255,0.3)' : 'rgba(255,179,71,0.3)'}`,
            borderRadius:16, padding:24, marginBottom:24
          }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', flexWrap:'wrap', gap:16 }}>
              <div>
                <div style={{ fontFamily:'Syne', fontWeight:800, fontSize:17, marginBottom:8 }}>
                  Imposto anual (IRPF) — Aplicações Financeiras no Exterior
                </div>
                <div style={{ fontSize:13, color:'var(--muted)', lineHeight:1.8 }}>
                  <div>• Alíquota: <strong style={{color:'var(--text)'}}>15% fixo</strong> (Lei 14.754/2023)</div>
                  <div>• Declarar como: <strong style={{color:'var(--text)'}}>Aplicações financeiras no exterior</strong></div>
                  <div>• Prazo de entrega: <strong style={{color:'var(--text)'}}>{fmtVenc(dados.vencimento_darf)}</strong></div>
                  <div>• Depósitos: <strong style={{color:'var(--text)'}}>{fmtUSD(dados.depositos_usd)}</strong></div>
                  <div>• Saques: <strong style={{color:'var(--text)'}}>{fmtUSD(dados.saques_usd)}</strong></div>
                </div>
              </div>
              <div style={{ textAlign:'right' }}>
                <div style={{ fontSize:32, fontFamily:'Syne', fontWeight:800, color: dados.darf_pago ? 'var(--accent)' : 'var(--warn)' }}>
                  {fmtBRL(dados.imposto_brl)}
                </div>
                {dados.darf_pago
                  ? <span className="badge badge-blue">✓ Pago</span>
                  : <span className="badge badge-yellow">A pagar</span>
                }
              </div>
            </div>
          </div>
        )}

        {/* BREAKDOWN MENSAL */}
        {dados.meses?.length > 0 && (
          <div className="card" style={{ marginBottom:24 }}>
            <h3 style={{ fontSize:15, marginBottom:20 }}>Breakdown mensal — {ano}</h3>
            {desbloqueado ? (
              <div style={{ overflowX:'auto' }}>
                <table className="tabela">
                  <thead>
                    <tr>
                      <th>Mês</th>
                      <th>Resultado (USD)</th>
                      <th>Resultado (BRL)</th>
                      <th>PTAX</th>
                      <th>Depósitos</th>
                      <th>Saques</th>
                      <th>Operações</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {dados.meses.map(m => (
                      <tr key={m.mes}>
                        <td style={{ fontWeight:600 }}>{MESES_CURTO[m.mes-1]}</td>
                        <td style={{ color: r2(m.ganho_usd) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                          {r2(m.ganho_usd) >= 0 ? '+' : ''}{fmtUSD(m.ganho_usd)}
                        </td>
                        <td style={{ color: r2(m.ganho_brl) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                          {fmtBRL(m.ganho_brl)}
                        </td>
                        <td style={{ color:'var(--muted)', fontSize:12 }}>
                          {m.ptax ? `R$ ${r2(m.ptax).toFixed(4)}` : '—'}
                        </td>
                        <td style={{ fontSize:12, color:'var(--muted)' }}>
                          {r2(m.depositos_usd) > 0 ? fmtUSD(m.depositos_usd) : '—'}
                        </td>
                        <td style={{ fontSize:12, color: r2(m.saques_usd) > 0 ? 'var(--danger)' : 'var(--muted)' }}>
                          {r2(m.saques_usd) > 0 ? `-${fmtUSD(m.saques_usd)}` : '—'}
                        </td>
                        <td style={{ fontSize:12, color:'var(--muted)', textAlign:'center' }}>
                          {m.operacoes_count || 0}
                        </td>
                        <td className="no-print">
                          <button className="btn btn-ghost" style={{ padding:'4px 12px', fontSize:11 }}
                            onClick={() => navigate(`/apuracao/${m.id}`)}>
                            Detalhe
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr style={{ fontWeight:700, borderTop:'2px solid var(--border)', background:'var(--surface2)' }}>
                      <td>TOTAL</td>
                      <td style={{ color: r2(dados.lucro_usd) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>{fmtUSD(dados.lucro_usd)}</td>
                      <td style={{ color: r2(dados.lucro_brl) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>{fmtBRL(dados.lucro_brl)}</td>
                      <td>—</td>
                      <td style={{ fontSize:12 }}>{r2(dados.depositos_usd) > 0 ? fmtUSD(dados.depositos_usd) : '—'}</td>
                      <td style={{ fontSize:12 }}>{r2(dados.saques_usd) > 0 ? `-${fmtUSD(dados.saques_usd)}` : '—'}</td>
                      <td></td><td></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            ) : (
              <div style={{ textAlign:'center', padding:'32px 16px', color:'var(--muted)' }}>
                <div style={{ fontSize:28, marginBottom:8 }}>🔒</div>
                <div style={{ fontSize:14 }}>Detalhe mensal disponível após desbloqueio</div>
              </div>
            )}
          </div>
        )}

      </div>
    </Layout>
  )
}

function LockedValue() {
  return (
    <div style={{ display:'flex', alignItems:'center', gap:8, marginTop:4 }}>
      <span style={{ fontSize:20 }}>🔒</span>
      <span style={{ fontSize:14, color:'var(--muted)' }}>Bloqueado</span>
    </div>
  )
}

const s = {
  label: { fontSize:12, color:'var(--muted)', marginBottom:8, textTransform:'uppercase', letterSpacing:'0.5px' },
  valor: { fontSize:20, fontFamily:'Syne', fontWeight:800 },
}
