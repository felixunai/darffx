import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList,
  AreaChart, Area, PieChart, Pie,
} from 'recharts'
import Layout from '../components/Layout'
import api from '../api'

const MESES_CURTO = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

const r2     = (v) => Math.round((v || 0) * 100) / 100
const fmtBRL = (v) => `R$ ${r2(v).toLocaleString('pt-BR', { minimumFractionDigits:2, maximumFractionDigits:2 })}`
const fmtUSD = (v) => `US$ ${r2(v).toLocaleString('pt-BR', { minimumFractionDigits:2, maximumFractionDigits:2 })}`
const fmtVenc = (iso) => {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

const fmtCompact = (v) => {
  if (v === null || v === undefined) return ''
  const abs = Math.abs(v)
  const sign = v >= 0 ? '+' : '-'
  if (abs >= 1000) return `${sign}${(abs / 1000).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}k`
  return `${sign}${abs.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}`
}

const fmtCompactBRL = (v) => {
  if (v === null || v === undefined) return ''
  const abs = Math.abs(v)
  const sign = v >= 0 ? '+' : '-'
  if (abs >= 1000) return `${sign}R$${(abs / 1000).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}k`
  return `${sign}R$${abs.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}`
}

const TOOLTIP_STYLE = {
  contentStyle: { background:'#1a2235', border:'1px solid rgba(255,255,255,0.12)', borderRadius:8, fontSize:12, color:'#e8edf5' },
  labelStyle: { color:'#8899aa' },
  itemStyle: { color:'#e8edf5' },
}

function CardStat({ label, valor, cor, sub, mobile }) {
  return (
    <div className="card" style={{ borderColor: cor ? `${cor}30` : undefined, padding: mobile ? '14px' : undefined }}>
      <div style={{ fontSize:10, color:'var(--muted)', marginBottom:6, textTransform:'uppercase', letterSpacing:'0.5px' }}>{label}</div>
      <div style={{
        fontSize: mobile ? 14 : 21,
        fontFamily:'Syne', fontWeight:800,
        color: cor || 'var(--text)', lineHeight:1.2,
        overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap',
      }}>{valor}</div>
      {sub && <div style={{ fontSize:10, color:'var(--muted)', marginTop:4 }}>{sub}</div>}
    </div>
  )
}

function CardInsight({ icon, label, valor, cor, sub, vertical }) {
  return (
    <div className="card" style={{
      display:'flex',
      flexDirection: vertical ? 'column' : 'row',
      gap: vertical ? 8 : 14,
      alignItems: vertical ? 'flex-start' : 'center',
      borderColor: cor ? `${cor}20` : undefined,
      padding: vertical ? '16px' : undefined,
    }}>
      <div style={{ fontSize: vertical ? 22 : 28, flexShrink:0 }}>{icon}</div>
      <div style={{ minWidth:0, width:'100%' }}>
        <div style={{ fontSize:10, color:'var(--muted)', textTransform:'uppercase', letterSpacing:'0.5px', marginBottom:3 }}>{label}</div>
        <div style={{
          fontSize: vertical ? 14 : 17,
          fontFamily:'Syne', fontWeight:800,
          color: cor || 'var(--text)',
          wordBreak:'break-word',
          lineHeight:1.2,
        }}>{valor}</div>
        {sub && <div style={{ fontSize:10, color:'var(--muted)', marginTop:3 }}>{sub}</div>}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [anuais,       setAnuais]       = useState([])
  const [loading,      setLoading]      = useState(true)
  const [deletando,    setDeletando]    = useState(null)
  const [anoSel,       setAnoSel]       = useState(null)
  const [mesesDetalhe, setMesesDetalhe] = useState([])
  const [loadingMeses, setLoadingMeses] = useState(false)
  const [baixandoXlsx,  setBaixandoXlsx]  = useState(false)
  const [mobile,        setMobile]        = useState(window.innerWidth <= 768)
  const [todosOsMeses,  setTodosOsMeses]  = useState([])

  useEffect(() => {
    const onResize = () => setMobile(window.innerWidth <= 768)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    api.get('/apuracao/anual/')
      .then(r => {
        const lista = Array.isArray(r.data) ? r.data : []
        setAnuais(lista)
        if (lista.length > 0) {
          const maisRecente = lista.reduce((a, b) => a.ano > b.ano ? a : b).ano
          setAnoSel(maisRecente)
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const baixarXlsx = async (ano) => {
    setBaixandoXlsx(true)
    try {
      const { data } = await api.get(`/apuracao/anual/${ano}/xlsx`, { responseType: 'blob' })
      const url  = URL.createObjectURL(data)
      const link = document.createElement('a')
      link.href  = url
      link.download = `darffx_${ano}.xlsx`
      link.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('Erro ao exportar. Tente novamente.')
    } finally {
      setBaixandoXlsx(false)
    }
  }

  const buscarMeses = useCallback(async (ano) => {
    setLoadingMeses(true)
    try {
      const { data } = await api.get(`/apuracao/anual/${ano}`)
      setMesesDetalhe(data.meses || [])
    } catch {
      setMesesDetalhe([])
    } finally {
      setLoadingMeses(false)
    }
  }, [])

  const marcarDarfPago = async (ano, pago) => {
    try {
      await api.patch(`/apuracao/anual/${ano}/${pago ? 'pago' : 'pendente'}`)
      setAnuais(prev => prev.map(a => a.ano === ano ? { ...a, darf_pago: pago } : a))
    } catch {
      alert('Erro ao atualizar. Tente novamente.')
    }
  }

  useEffect(() => {
    if (anoSel) {
      setMesesDetalhe([])
      buscarMeses(anoSel)
    }
  }, [anoSel, buscarMeses])

  useEffect(() => {
    if (anuais.length > 1) {
      api.get('/apuracao/meses/todos')
        .then(r => setTodosOsMeses(r.data || []))
        .catch(() => setTodosOsMeses([]))
    }
  }, [anuais.length])

  const deletar = async (a) => {
    if (!window.confirm(`Excluir toda a apuração de ${a.ano}? Todos os meses serão removidos.`)) return
    setDeletando(a.ano)
    try {
      await api.delete(`/apuracao/anual/${a.ano}`)
      setAnuais(prev => prev.filter(x => x.ano !== a.ano))
      if (anoSel === a.ano) setAnoSel(null)
    } catch {
      alert('Erro ao excluir. Tente novamente.')
    } finally {
      setDeletando(null)
    }
  }

  // ── Derivados globais ────────────────────────────────────────────────────
  const desbloqueados    = anuais.filter(a => a.desbloqueado)
  const totalImposto     = r2(desbloqueados.reduce((s, a) => s + r2(a.imposto_brl), 0))
  const totalLucro       = r2(anuais.reduce((s, a) => s + r2(a.lucro_brl), 0))
  const totalLucroUSD    = r2(anuais.reduce((s, a) => s + r2(a.lucro_usd), 0))
  const totalDepositos   = r2(anuais.reduce((s, a) => s + r2(a.depositos_usd), 0))
  const totalSaques      = r2(anuais.reduce((s, a) => s + r2(a.saques_usd), 0))
  const capitalLiqUSD    = r2(totalDepositos - totalSaques)
  const rentTotal        = capitalLiqUSD > 0 ? r2((totalLucroUSD / capitalLiqUSD) * 100) : null
  const impostoPendente  = r2(desbloqueados.filter(a => r2(a.imposto_brl) > 0 && !a.darf_pago).reduce((s, a) => s + r2(a.imposto_brl), 0))
  const anoAtual         = anuais.find(a => a.ano === anoSel)
  const anoSelDesbloqueado = anoAtual?.desbloqueado ?? false

  // ── Gráfico: rentabilidade % por ano ─────────────────────────────────────
  const chartRentAnual = [...anuais].sort((a, b) => a.ano - b.ano).map(a => ({
    name: String(a.ano),
    rent: r2(a.depositos_usd) > 0 ? r2((r2(a.lucro_usd) / r2(a.depositos_usd)) * 100) : null,
    ano:  a.ano,
  }))

  // ── Insights do ano selecionado (derivados de mesesDetalhe) ──────────────
  const mesesOrdenados = [...mesesDetalhe].sort((a, b) =>
    a.ano !== b.ano ? a.ano - b.ano : a.mes - b.mes
  )
  const melhorMes = mesesDetalhe.length > 0
    ? mesesDetalhe.reduce((best, m) => m.ganho_brl > best.ganho_brl ? m : best)
    : null
  const piorMes = mesesDetalhe.length > 0
    ? mesesDetalhe.reduce((worst, m) => m.ganho_brl < worst.ganho_brl ? m : worst)
    : null
  const mesesPositivos = mesesDetalhe.filter(m => m.ganho_brl > 0).length
  const taxaLucro = mesesDetalhe.length > 0
    ? Math.round((mesesPositivos / mesesDetalhe.length) * 100)
    : 0

  // Sequência atual de meses positivos ou negativos
  let streak = 0
  let streakPositivo = true
  if (mesesOrdenados.length > 0) {
    streakPositivo = mesesOrdenados[mesesOrdenados.length - 1].ganho_brl >= 0
    for (let i = mesesOrdenados.length - 1; i >= 0; i--) {
      if ((mesesOrdenados[i].ganho_brl >= 0) === streakPositivo) streak++
      else break
    }
  }

  // ── Gráfico: P&L mensal por barras ───────────────────────────────────────
  const chartMensal = mesesOrdenados.map(m => ({
    name:  MESES_CURTO[m.mes - 1],
    lucro: r2(m.ganho_brl),
    mes:   m.mes,
    id:    m.id,
  }))

  // ── Gráfico: P&L acumulado (AreaChart) ───────────────────────────────────
  const chartCumulativo = mesesOrdenados.reduce((acc, m) => {
    const prev = acc.length > 0 ? acc[acc.length - 1].cumul : 0
    acc.push({ name: MESES_CURTO[m.mes - 1], cumul: r2(prev + m.ganho_brl) })
    return acc
  }, [])

  // ── Gráfico: Depósito vs Lucro (donut) ───────────────────────────────────
  const ptaxMedio = mesesDetalhe.filter(m => m.ptax).length > 0
    ? mesesDetalhe.filter(m => m.ptax).reduce((s, m) => s + m.ptax, 0) / mesesDetalhe.filter(m => m.ptax).length
    : 5.0
  const depositosBRL = r2((anoAtual?.depositos_usd || 0) * ptaxMedio)
  const lucroBRL     = r2(Math.max(0, anoAtual?.lucro_brl || 0))
  const donutData = depositosBRL + lucroBRL > 0 ? [
    { name: 'Depósitos', value: depositosBRL, color: '#0095ff' },
    { name: 'Lucro trading', value: lucroBRL, color: '#00e5a0' },
  ] : []

  // ── Gráfico: imposto por ano ──────────────────────────────────────────────
  const chartAnual = [...anuais].sort((a, b) => a.ano - b.ano).map(a => ({
    name:    String(a.ano),
    imposto: a.desbloqueado ? r2(a.imposto_brl) : 0,
    lucro:   r2(a.lucro_brl),
    ano:     a.ano,
    locked:  !a.desbloqueado,
  }))

  // ── Gráfico: P&L acumulado multi-ano ─────────────────────────────────────
  const chartMultiAno = todosOsMeses.reduce((acc, m) => {
    const prev = acc.length > 0 ? acc[acc.length - 1].cumul : 0
    acc.push({
      name:  `${MESES_CURTO[m.mes - 1]}/${String(m.ano).slice(2)}`,
      cumul: r2(prev + m.ganho_brl),
    })
    return acc
  }, [])

  // ── Rentabilidade ─────────────────────────────────────────────────────────
  const rentBase     = depositosBRL > 0 ? depositosBRL : null
  const rentAnual    = rentBase && anoAtual ? r2((r2(anoAtual.lucro_brl) / rentBase) * 100) : null
  const rentMedia    = rentAnual !== null && mesesDetalhe.length > 0
    ? r2(rentAnual / mesesDetalhe.length) : null
  const rentMensal   = mesesOrdenados.map(m => ({
    nome: MESES_CURTO[m.mes - 1],
    pct:  rentBase ? r2((r2(m.ganho_brl) / rentBase) * 100) : 0,
  }))
  const rentMaxAbs   = rentMensal.length > 0
    ? Math.max(...rentMensal.map(m => Math.abs(m.pct)), 0.01) : 1

  // ── DARF countdown ────────────────────────────────────────────────────────
  const vencDarf   = anoAtual?.vencimento_darf
  const diasDarf   = vencDarf ? Math.ceil((new Date(vencDarf) - new Date()) / 86400000) : null
  const darfUrgente = anoSelDesbloqueado && r2(anoAtual?.imposto_brl) > 0 && !anoAtual?.darf_pago
  const darfCor = diasDarf === null ? null
    : diasDarf < 0   ? 'var(--danger)'
    : diasDarf < 30  ? 'var(--danger)'
    : diasDarf < 60  ? 'var(--warn)'
    : 'var(--accent)'

  return (
    <Layout>
      <div style={{
        display:'flex',
        alignItems: mobile ? 'flex-start' : 'center',
        flexDirection: mobile ? 'column' : 'row',
        justifyContent:'space-between',
        marginBottom:28, gap:12,
      }}>
        <div>
          <h1 style={{ fontSize:24, marginBottom:4 }}>Dashboard</h1>
          <p style={{ color:'var(--muted)', fontSize:13 }}>
            Apuração anual — Lei 14.754/2023 · 15% sobre lucro líquido anual
          </p>
        </div>
        <button className="btn btn-primary"
          style={{ alignSelf: mobile ? 'stretch' : undefined }}
          onClick={() => navigate('/upload')}>
          + Novo Extrato
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign:'center', padding:80 }}><span className="spinner" style={{width:32,height:32}} /></div>
      ) : anuais.length === 0 ? (
        <Empty navigate={navigate} />
      ) : (
        <>
          {/* ── ROW 1: Stats principais ─────────────────────────────────── */}
          <div className="grid-4" style={{ marginBottom:16 }}>
            <CardStat label="Anos apurados" valor={anuais.length} mobile={mobile} />
            <CardStat
              label="Lucro total (BRL)"
              valor={fmtBRL(totalLucro)}
              cor={totalLucro >= 0 ? 'var(--accent)' : 'var(--danger)'}
              mobile={mobile}
            />
            <CardStat
              label="Imposto total"
              valor={desbloqueados.length > 0 ? fmtBRL(totalImposto) : '🔒 Bloqueado'}
              cor="var(--warn)"
              mobile={mobile}
            />
            <CardStat
              label="Imposto a pagar"
              valor={desbloqueados.length > 0 ? fmtBRL(impostoPendente) : '—'}
              cor={impostoPendente > 0 ? 'var(--danger)' : undefined}
              mobile={mobile}
            />
          </div>

          {/* ── DESDE O INÍCIO ──────────────────────────────────────────── */}
          <div style={{ fontSize:11, color:'var(--muted)', fontWeight:700, letterSpacing:'1px', marginBottom:10, marginTop:4 }}>
            DESDE O INÍCIO · {anuais.length} {anuais.length === 1 ? 'ANO' : 'ANOS'} REGISTRADO{anuais.length !== 1 ? 'S' : ''}
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginBottom:24 }}>
            {/* Capital líquido */}
            <div className="card" style={{ borderColor:'rgba(0,149,255,0.25)', padding: mobile ? 14 : undefined }}>
              <div style={{ fontSize:10, color:'var(--muted)', textTransform:'uppercase', letterSpacing:'0.5px', marginBottom:6 }}>Capital líquido</div>
              <div style={{ fontSize: mobile ? 14 : 19, fontFamily:'Syne', fontWeight:800, color:'var(--accent2)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                {fmtUSD(capitalLiqUSD)}
              </div>
              <div style={{ fontSize:10, color:'var(--muted)', marginTop:5, lineHeight:1.6 }}>
                +{fmtUSD(totalDepositos)} dep.{totalSaques > 0 ? ` · -${fmtUSD(totalSaques)} saq.` : ''}
              </div>
            </div>

            {/* Rentabilidade total */}
            <div className="card" style={{
              borderColor: rentTotal !== null ? (rentTotal >= 0 ? 'rgba(0,229,160,0.25)' : 'rgba(255,77,109,0.25)') : undefined,
              padding: mobile ? 14 : undefined,
            }}>
              <div style={{ fontSize:10, color:'var(--muted)', textTransform:'uppercase', letterSpacing:'0.5px', marginBottom:6 }}>Rentabilidade total</div>
              <div style={{ fontSize: mobile ? 14 : 19, fontFamily:'Syne', fontWeight:800, lineHeight:1.2,
                color: rentTotal === null ? 'var(--muted)' : rentTotal >= 0 ? 'var(--accent)' : 'var(--danger)',
              }}>
                {rentTotal === null ? '—'
                  : `${rentTotal >= 0 ? '+' : ''}${rentTotal.toLocaleString('pt-BR', { minimumFractionDigits:1, maximumFractionDigits:1 })}%`}
              </div>
              <div style={{ fontSize:10, color:'var(--muted)', marginTop:5 }}>sobre capital líquido (USD)</div>
            </div>
          </div>

          {/* ── ROW 2: Insights do ano selecionado ──────────────────────── */}
          {mesesDetalhe.length > 0 && anoSelDesbloqueado && (
            <div style={{ display:'grid', gridTemplateColumns: mobile ? '1fr 1fr' : 'repeat(4,1fr)', gap:12, marginBottom:16 }}>
              <CardInsight
                icon="🏆"
                label="Melhor mês"
                valor={melhorMes ? fmtBRL(melhorMes.ganho_brl) : '—'}
                cor="var(--accent)"
                sub={melhorMes ? `${MESES_CURTO[melhorMes.mes - 1]}/${melhorMes.ano || anoSel}` : undefined}
                vertical={mobile}
              />
              <CardInsight
                icon="📉"
                label="Pior mês"
                valor={piorMes ? fmtBRL(piorMes.ganho_brl) : '—'}
                cor={piorMes && piorMes.ganho_brl < 0 ? 'var(--danger)' : 'var(--muted)'}
                sub={piorMes ? `${MESES_CURTO[piorMes.mes - 1]}/${piorMes.ano || anoSel}` : undefined}
                vertical={mobile}
              />
              <CardInsight
                icon="🎯"
                label="Meses lucrativos"
                valor={`${mesesPositivos}/${mesesDetalhe.length}`}
                cor="var(--accent)"
                sub={`${taxaLucro}% de acerto`}
                vertical={mobile}
              />
              <CardInsight
                icon={streakPositivo ? '🔥' : '❄️'}
                label="Sequência atual"
                valor={`${streak} ${streak === 1 ? 'mês' : 'meses'}`}
                cor={streakPositivo ? 'var(--accent)' : 'var(--danger)'}
                sub={streakPositivo ? 'positivos seguidos' : 'negativos seguidos'}
                vertical={mobile}
              />
            </div>
          )}

          {/* ── DARF COUNTDOWN ──────────────────────────────────────────── */}
          {darfUrgente && diasDarf !== null && (
            <div style={{
              background: `rgba(${diasDarf < 30 ? '255,77,109' : diasDarf < 60 ? '255,179,71' : '0,229,160'},0.07)`,
              border:`1px solid ${darfCor}`,
              borderRadius:14,
              padding: mobile ? '14px 16px' : '16px 24px',
              marginBottom:16,
              display:'flex',
              flexDirection: mobile ? 'column' : 'row',
              alignItems: mobile ? 'flex-start' : 'center',
              justifyContent:'space-between',
              gap:12,
            }}>
              <div style={{ display:'flex', alignItems:'center', gap:12 }}>
                <div style={{ textAlign:'center', minWidth: mobile ? 44 : 56, flexShrink:0 }}>
                  <div style={{ fontSize: mobile ? 26 : 32, fontFamily:'Syne', fontWeight:800, color:darfCor, lineHeight:1 }}>
                    {diasDarf < 0 ? '!' : diasDarf}
                  </div>
                  <div style={{ fontSize:10, color:'var(--muted)', marginTop:2 }}>
                    {diasDarf < 0 ? 'VENCIDO' : 'dias'}
                  </div>
                </div>
                <div>
                  <div style={{ fontWeight:700, color:'var(--text)', fontSize: mobile ? 13 : 14 }}>
                    {diasDarf < 0
                      ? 'DARF vencido — regularize o quanto antes'
                      : diasDarf < 30
                      ? 'DARF vence em breve'
                      : `DARF vence em ${fmtVenc(vencDarf)}`}
                  </div>
                  <div style={{ fontSize:11, color:'var(--muted)', marginTop:3, lineHeight:1.5 }}>
                    Imposto: <strong style={{color:darfCor}}>{fmtBRL(anoAtual?.imposto_brl)}</strong>
                    {!mobile && <>{' · '}Declarar como "Aplicações financeiras no exterior"</>}
                  </div>
                </div>
              </div>
              <div style={{ display:'flex', gap:8, width: mobile ? '100%' : undefined, flexWrap:'wrap' }}>
                <button
                  className="btn btn-ghost"
                  style={{ fontSize:12, borderColor:darfCor, color:darfCor, flex: mobile ? 1 : undefined }}
                  onClick={() => navigate(`/apuracao/anual/${anoSel}`)}>
                  Ver detalhes →
                </button>
                <button
                  className="btn btn-ghost"
                  style={{ fontSize:12, borderColor:'var(--accent)', color:'var(--accent)', flex: mobile ? 1 : undefined }}
                  onClick={() => marcarDarfPago(anoSel, true)}>
                  ✓ Marcar como pago
                </button>
              </div>
            </div>
          )}

          {/* ── ROW 3: Gráficos ──────────────────────────────────────────── */}
          {anoSelDesbloqueado && mesesDetalhe.length > 0 && (
            <div style={{ display:'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap:16, marginBottom:16 }}>

              {/* P&L mensal (barras) */}
              <div className="card">
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:16 }}>
                  <h3 style={{ fontSize:14, margin:0 }}>Resultado mensal — {anoSel}</h3>
                  {anuais.length > 1 && (
                    <div style={{ display:'flex', gap:4 }}>
                      {[...anuais].sort((a,b) => a.ano - b.ano).map(a => (
                        <button key={a.ano}
                          onClick={() => setAnoSel(a.ano)}
                          className={`btn ${anoSel === a.ano ? 'btn-primary' : 'btn-ghost'}`}
                          style={{ padding:'3px 9px', fontSize:11 }}>
                          {a.ano}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                {loadingMeses ? (
                  <div style={{ height:160, display:'flex', alignItems:'center', justifyContent:'center' }}>
                    <span className="spinner" />
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={chartMensal} barSize={22} margin={{ top:20, right:4, left:4, bottom:0 }}>
                      <XAxis dataKey="name" tick={{ fill:'#8899aa', fontSize:11 }} axisLine={false} tickLine={false} />
                      <YAxis hide />
                      <Tooltip {...TOOLTIP_STYLE} formatter={(v) => [fmtBRL(v), 'Resultado']} />
                      <Bar dataKey="lucro" radius={[4,4,0,0]}>
                        <LabelList dataKey="lucro" position="top"
                          formatter={fmtCompactBRL}
                          style={{ fontSize:9, fill:'#8899aa' }} />
                        {chartMensal.map((e, i) => (
                          <Cell key={i} fill={e.lucro >= 0 ? '#00e5a0' : '#ff4d6d'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* P&L acumulado (área) */}
              <div className="card">
                <h3 style={{ fontSize:14, marginBottom:16 }}>P&L acumulado — {anoSel}</h3>
                {loadingMeses ? (
                  <div style={{ height:160, display:'flex', alignItems:'center', justifyContent:'center' }}>
                    <span className="spinner" />
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={160}>
                    <AreaChart data={chartCumulativo} margin={{ left:10, right:10, top:4 }}>
                      <defs>
                        <linearGradient id="gradPos" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor="#00e5a0" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="#00e5a0" stopOpacity={0.02} />
                        </linearGradient>
                        <linearGradient id="gradNeg" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor="#ff4d6d" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="#ff4d6d" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="name" tick={{ fill:'#8899aa', fontSize:11 }} axisLine={false} tickLine={false} />
                      <YAxis hide />
                      <Tooltip {...TOOLTIP_STYLE} formatter={(v) => [fmtBRL(v), 'Acumulado']} />
                      <Area
                        type="monotone" dataKey="cumul" strokeWidth={2}
                        stroke={chartCumulativo.length > 0 && chartCumulativo[chartCumulativo.length - 1].cumul >= 0 ? '#00e5a0' : '#ff4d6d'}
                        fill={chartCumulativo.length > 0 && chartCumulativo[chartCumulativo.length - 1].cumul >= 0 ? 'url(#gradPos)' : 'url(#gradNeg)'}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Donut: Depósito vs Lucro */}
              {donutData.length > 0 && (
                <div className="card">
                  <h3 style={{ fontSize:14, marginBottom:3 }}>Composição do capital — {anoSel}</h3>
                  <p style={{ fontSize:11, color:'var(--muted)', marginBottom:4 }}>
                    Depósitos vs lucro de trading
                  </p>
                  {/* Legend HTML manual — evita recharts deslocar o centro e cortar o topo */}
                  <div style={{ display:'flex', justifyContent:'center', gap:18, marginBottom:4 }}>
                    {donutData.map((e) => (
                      <div key={e.name} style={{ display:'flex', alignItems:'center', gap:5, fontSize:11, color:'#8899aa' }}>
                        <div style={{ width:8, height:8, borderRadius:'50%', background:e.color, flexShrink:0 }} />
                        <span>{e.name}</span>
                        <span style={{ color:'var(--text)', fontWeight:600 }}>{fmtBRL(e.value)}</span>
                      </div>
                    ))}
                  </div>
                  <ResponsiveContainer width="100%" height={155}>
                    <PieChart>
                      <Pie
                        data={donutData}
                        cx="50%" cy="50%"
                        innerRadius={42} outerRadius={64}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {donutData.map((e, i) => (
                          <Cell key={i} fill={e.color} />
                        ))}
                      </Pie>
                      <Tooltip {...TOOLTIP_STYLE} formatter={(v, n) => [fmtBRL(v), n]} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Rentabilidade */}
              {rentAnual !== null && rentMensal.length > 0 && (
                <div className="card">
                  <h3 style={{ fontSize:14, marginBottom:2 }}>Rentabilidade — {anoSel}</h3>
                  <p style={{ fontSize:11, color:'var(--muted)', marginBottom:12 }}>
                    Sobre capital depositado ({fmtBRL(rentBase)})
                  </p>
                  <div style={{ display:'flex', gap:10, marginBottom:14 }}>
                    <div style={{ flex:1, background:'var(--surface2)', borderRadius:8, padding:'10px 12px' }}>
                      <div style={{ fontSize:9, color:'var(--muted)', textTransform:'uppercase', letterSpacing:'0.5px', marginBottom:4 }}>Anual</div>
                      <div style={{ fontSize:20, fontFamily:'Syne', fontWeight:800, color: rentAnual >= 0 ? 'var(--accent)' : 'var(--danger)', lineHeight:1 }}>
                        {rentAnual >= 0 ? '+' : ''}{rentAnual.toLocaleString('pt-BR', { minimumFractionDigits:1, maximumFractionDigits:1 })}%
                      </div>
                    </div>
                    <div style={{ flex:1, background:'var(--surface2)', borderRadius:8, padding:'10px 12px' }}>
                      <div style={{ fontSize:9, color:'var(--muted)', textTransform:'uppercase', letterSpacing:'0.5px', marginBottom:4 }}>Média/mês</div>
                      <div style={{ fontSize:20, fontFamily:'Syne', fontWeight:800, color: rentMedia >= 0 ? 'var(--accent)' : 'var(--danger)', lineHeight:1 }}>
                        {rentMedia >= 0 ? '+' : ''}{rentMedia?.toLocaleString('pt-BR', { minimumFractionDigits:1, maximumFractionDigits:1 })}%
                      </div>
                    </div>
                  </div>
                  <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
                    {rentMensal.map(({ nome, pct }) => {
                      const cor = pct >= 0 ? 'var(--accent)' : 'var(--danger)'
                      const largura = `${Math.round((Math.abs(pct) / rentMaxAbs) * 100)}%`
                      return (
                        <div key={nome} style={{ display:'flex', alignItems:'center', gap:8 }}>
                          <div style={{ width:26, fontSize:10, color:'var(--muted)', flexShrink:0 }}>{nome}</div>
                          <div style={{ flex:1, height:6, background:'var(--surface2)', borderRadius:4, overflow:'hidden', minWidth:0 }}>
                            <div style={{ height:'100%', width:largura, background:cor, borderRadius:4, transition:'width 0.4s ease' }} />
                          </div>
                          <div style={{ width:46, fontSize:11, color:cor, fontWeight:700, textAlign:'right', flexShrink:0 }}>
                            {pct >= 0 ? '+' : ''}{pct.toLocaleString('pt-BR', { minimumFractionDigits:1, maximumFractionDigits:1 })}%
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* P&L acumulado multi-ano (Sprint B) */}
              {anuais.length > 1 && chartMultiAno.length > 0 && (
                <div className="card">
                  <h3 style={{ fontSize:14, marginBottom:16 }}>P&L acumulado — todos os anos</h3>
                  <ResponsiveContainer width="100%" height={160}>
                    <AreaChart data={chartMultiAno} margin={{ left:10, right:10, top:4 }}>
                      <defs>
                        <linearGradient id="gradMultiPos" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor="#00e5a0" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="#00e5a0" stopOpacity={0.02} />
                        </linearGradient>
                        <linearGradient id="gradMultiNeg" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor="#ff4d6d" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="#ff4d6d" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="name" tick={{ fill:'#8899aa', fontSize:10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                      <YAxis hide />
                      <Tooltip {...TOOLTIP_STYLE} formatter={(v) => [fmtBRL(v), 'Acumulado']} />
                      <Area type="monotone" dataKey="cumul" strokeWidth={2}
                        stroke={chartMultiAno.length > 0 && chartMultiAno[chartMultiAno.length - 1].cumul >= 0 ? '#00e5a0' : '#ff4d6d'}
                        fill={chartMultiAno.length > 0 && chartMultiAno[chartMultiAno.length - 1].cumul >= 0 ? 'url(#gradMultiPos)' : 'url(#gradMultiNeg)'}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Rentabilidade % por ano (só se múltiplos anos) */}
              {anuais.length > 1 && chartRentAnual.some(d => d.rent !== null) && (
                <div className="card">
                  <h3 style={{ fontSize:14, marginBottom:4 }}>Rentabilidade por ano (%)</h3>
                  <p style={{ fontSize:11, color:'var(--muted)', marginBottom:12 }}>P&L ÷ depósitos de cada ano</p>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={chartRentAnual} barSize={36} margin={{ top:20, right:4, left:4, bottom:0 }}
                      onClick={(d) => d?.activePayload && setAnoSel(d.activePayload[0]?.payload?.ano)}>
                      <XAxis dataKey="name" tick={{ fill:'#8899aa', fontSize:12 }} axisLine={false} tickLine={false} />
                      <YAxis hide />
                      <Tooltip
                        {...TOOLTIP_STYLE}
                        formatter={(v) => v === null ? ['—', 'Rentabilidade'] : [`${v >= 0 ? '+' : ''}${v?.toLocaleString('pt-BR', { minimumFractionDigits:1, maximumFractionDigits:1 })}%`, 'Rentabilidade']}
                      />
                      <Bar dataKey="rent" radius={[6,6,0,0]}>
                        <LabelList dataKey="rent" position="top"
                          formatter={(v) => v === null ? '' : `${v >= 0 ? '+' : ''}${v?.toLocaleString('pt-BR', { minimumFractionDigits:1, maximumFractionDigits:1 })}%`}
                          style={{ fontSize:10, fill:'#8899aa' }} />
                        {chartRentAnual.map((e, i) => (
                          <Cell key={i}
                            fill={e.rent === null ? '#3ecf8e40' : e.rent >= 0 ? '#00e5a0' : '#ff4d6d'}
                            opacity={e.ano === anoSel ? 1 : 0.7}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <p style={{ fontSize:11, color:'var(--muted)', textAlign:'center', marginTop:8 }}>
                    Clique em um ano para ver o detalhamento
                  </p>
                </div>
              )}

              {/* Imposto por ano (só se múltiplos anos) */}
              {anuais.length > 1 && (
                <div className="card">
                  <h3 style={{ fontSize:14, marginBottom:16 }}>Imposto por ano</h3>
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={chartAnual} barSize={36} margin={{ top:20, right:4, left:4, bottom:0 }}
                      onClick={(d) => d?.activePayload && setAnoSel(d.activePayload[0]?.payload?.ano)}>
                      <XAxis dataKey="name" tick={{ fill:'#8899aa', fontSize:12 }} axisLine={false} tickLine={false} />
                      <YAxis hide />
                      <Tooltip {...TOOLTIP_STYLE} formatter={(v) => [fmtBRL(v), 'Imposto']} />
                      <Bar dataKey="imposto" radius={[6,6,0,0]}>
                        <LabelList dataKey="imposto" position="top"
                          formatter={(v) => v > 0 ? fmtCompactBRL(v) : ''}
                          style={{ fontSize:10, fill:'#8899aa' }} />
                        {chartAnual.map((e, i) => (
                          <Cell key={i}
                            fill={e.ano === anoSel ? '#00e5a0' : (e.imposto > 0 ? '#ffb347' : '#3ecf8e60')}
                            opacity={e.ano === anoSel ? 1 : 0.7}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <p style={{ fontSize:11, color:'var(--muted)', textAlign:'center', marginTop:8 }}>
                    Clique em um ano para ver o detalhamento
                  </p>
                </div>
              )}
            </div>
          )}

          {/* ── ROW 4: Tabela anual ──────────────────────────────────────── */}
          <div className="card" style={{ overflowX:'auto', maxWidth:'100%', minWidth:0 }}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:20, flexWrap:'wrap', gap:8 }}>
              <h3 style={{ fontSize:15, margin:0 }}>Histórico de apurações anuais</h3>
              {anoAtual?.desbloqueado && (
                <button
                  className="btn btn-ghost"
                  style={{ fontSize:12, display:'flex', alignItems:'center', gap:6, opacity: baixandoXlsx ? 0.7 : 1 }}
                  onClick={() => baixarXlsx(anoSel)}
                  disabled={baixandoXlsx}>
                  {baixandoXlsx ? <><span className="spinner" style={{width:12,height:12}} /> Gerando...</> : '↓ Exportar Excel ' + anoSel}
                </button>
              )}
            </div>
            <table className="tabela" style={{ minWidth:900 }}>
              <thead>
                <tr>
                  <th>Ano</th>
                  <th>Lucro (USD)</th>
                  <th>Lucro (BRL)</th>
                  <th>Depósitos</th>
                  <th>Saques</th>
                  <th>Prej. Comp.</th>
                  <th>Base IR</th>
                  <th>Alíquota</th>
                  <th>Imposto</th>
                  <th>Prazo IRPF</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {[...anuais].sort((a, b) => a.ano - b.ano).map(a => (
                  <tr key={a.ano}
                    style={{ cursor:'pointer', background: anoSel === a.ano ? 'var(--surface2)' : undefined }}
                    onClick={() => setAnoSel(a.ano)}>
                    <td style={{ fontWeight:700, fontSize:15 }}>{a.ano}</td>
                    <td style={{ color: r2(a.lucro_usd) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                      {r2(a.lucro_usd) >= 0 ? '+' : ''}{fmtUSD(a.lucro_usd)}
                    </td>
                    <td style={{ color: r2(a.lucro_brl) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                      {fmtBRL(a.lucro_brl)}
                    </td>
                    {a.desbloqueado ? (
                      <>
                        <td style={{ fontSize:12, color:'var(--muted)' }}>
                          {r2(a.depositos_usd) > 0 ? fmtUSD(a.depositos_usd) : '—'}
                        </td>
                        <td style={{ fontSize:12, color: r2(a.saques_usd) > 0 ? 'var(--danger)' : 'var(--muted)' }}>
                          {r2(a.saques_usd) > 0 ? `-${fmtUSD(a.saques_usd)}` : '—'}
                        </td>
                        <td style={{ fontSize:12, color: r2(a.prejuizo_anterior_brl) > 0 ? 'var(--warn)' : 'var(--muted)' }}>
                          {r2(a.prejuizo_anterior_brl) > 0 ? `-${fmtBRL(a.prejuizo_anterior_brl)}` : '—'}
                        </td>
                        <td>{fmtBRL(a.base_tributavel_brl)}</td>
                        <td style={{ fontSize:12 }}>{((a.aliquota || 0.15) * 100).toFixed(0)}%</td>
                        <td style={{ fontWeight:600, color: r2(a.imposto_brl) > 0 ? 'var(--warn)' : 'var(--accent)' }}>
                          {fmtBRL(a.imposto_brl)}
                        </td>
                        <td style={{ fontSize:12, color:'var(--muted)' }}>{fmtVenc(a.vencimento_darf)}</td>
                        <td onClick={e => e.stopPropagation()}>
                          {r2(a.imposto_brl) === 0
                            ? <span className="badge badge-green">Isento</span>
                            : a.darf_pago
                              ? (
                                <button
                                  className="badge badge-blue"
                                  style={{ cursor:'pointer', border:'none' }}
                                  title="Clique para marcar como pendente"
                                  onClick={() => marcarDarfPago(a.ano, false)}>
                                  ✓ Pago
                                </button>
                              )
                              : (
                                <button
                                  className="badge badge-red"
                                  style={{ cursor:'pointer', border:'none' }}
                                  title="Clique para marcar como pago"
                                  onClick={() => marcarDarfPago(a.ano, true)}>
                                  A pagar
                                </button>
                              )
                          }
                        </td>
                      </>
                    ) : (
                      <>
                        <td colSpan={7} style={{ textAlign:'center' }}>
                          <span style={{ fontSize:12, color:'var(--muted)' }}>🔒 Relatório bloqueado</span>
                        </td>
                        <td>
                          <span className="badge" style={{ background:'rgba(0,229,160,0.1)', color:'var(--accent)', border:'1px solid rgba(0,229,160,0.3)' }}>Free</span>
                        </td>
                      </>
                    )}
                    <td onClick={e => e.stopPropagation()}>
                      <div style={{ display:'flex', gap:8 }}>
                        {a.desbloqueado ? (
                          <button className="btn btn-ghost" style={{ padding:'6px 14px', fontSize:12 }}
                            onClick={() => navigate(`/apuracao/anual/${a.ano}`)}>Ver</button>
                        ) : (
                          <button className="btn btn-primary" style={{ padding:'6px 14px', fontSize:12 }}
                            onClick={() => navigate(`/apuracao/anual/${a.ano}`)}>Desbloquear</button>
                        )}
                        <button
                          className="btn btn-ghost"
                          style={{ padding:'6px 14px', fontSize:12, color:'var(--danger)', borderColor:'var(--danger)' }}
                          onClick={() => deletar(a)} disabled={deletando === a.ano}>
                          {deletando === a.ano ? <span className="spinner" style={{width:12,height:12}} /> : 'Limpar'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>

              {anuais.length > 1 && (
                <tfoot>
                  <tr style={{ fontWeight:700, borderTop:'2px solid var(--border)', background:'var(--surface2)' }}>
                    <td>TOTAL</td>
                    <td>—</td>
                    <td style={{ color: totalLucro >= 0 ? 'var(--accent)' : 'var(--danger)' }}>{fmtBRL(totalLucro)}</td>
                    <td style={{ fontSize:12 }}>{totalDepositos > 0 ? fmtUSD(totalDepositos) : '—'}</td>
                    <td style={{ fontSize:12, color:'var(--danger)' }}>{totalSaques > 0 ? `-${fmtUSD(totalSaques)}` : '—'}</td>
                    <td>—</td><td>—</td>
                    <td style={{ fontSize:12 }}>15%</td>
                    <td style={{ color:'var(--warn)' }}>{fmtBRL(totalImposto)}</td>
                    <td>—</td><td>—</td><td></td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>

          <div style={{ marginTop:16, padding:'12px 16px', background:'var(--surface)', borderRadius:12,
            border:'1px solid var(--border)', fontSize:12, color:'var(--muted)', lineHeight:1.7 }}>
            📋 <strong style={{color:'var(--text)'}}>Lei 14.754/2023</strong> — Apuração anual · Alíquota fixa 15% · Sem isenção · Compensação de prejuízos entre anos · Declarar como "Aplicações financeiras no exterior" no IRPF
          </div>
        </>
      )}
    </Layout>
  )
}

function Empty({ navigate }) {
  return (
    <div style={{ textAlign:'center', padding:'80px 24px' }}>
      <div style={{ fontSize:48, marginBottom:16 }}>📊</div>
      <h2 style={{ marginBottom:8 }}>Nenhuma apuração ainda</h2>
      <p style={{ color:'var(--muted)', marginBottom:32, maxWidth:400, margin:'0 auto 32px' }}>
        Faça o upload do seu extrato CSV da AvaTrade para calcular seu IR conforme a Lei 14.754/2023.
      </p>
      <button className="btn btn-primary" onClick={() => navigate('/upload')}>
        Fazer primeiro upload
      </button>
    </div>
  )
}
