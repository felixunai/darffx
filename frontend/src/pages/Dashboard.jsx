import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import Layout from '../components/Layout'
import api    from '../api'

const MESES_CURTO = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

const r2     = (v) => Math.round((v || 0) * 100) / 100
const fmtBRL = (v) => `R$ ${r2(v).toLocaleString('pt-BR', { minimumFractionDigits:2, maximumFractionDigits:2 })}`
const fmtUSD = (v) => `US$ ${r2(v).toLocaleString('pt-BR', { minimumFractionDigits:2, maximumFractionDigits:2 })}`
const fmtVenc = (iso) => {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

function CardStat({ label, valor, cor }) {
  return (
    <div className="card" style={{ borderColor: cor ? `${cor}30` : undefined }}>
      <div style={{ fontSize:12, color:'var(--muted)', marginBottom:8, textTransform:'uppercase', letterSpacing:'0.5px' }}>{label}</div>
      <div style={{ fontSize:22, fontFamily:'Syne', fontWeight:800, color: cor || 'var(--text)' }}>{valor}</div>
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [anuais,     setAnuais]     = useState([])
  const [loading,    setLoading]    = useState(true)
  const [deletando,  setDeletando]  = useState(null)
  const [anoSel,     setAnoSel]     = useState(null)   // ano selecionado para gráfico mensal
  const [mesesDetalhe, setMesesDetalhe] = useState([]) // breakdown mensal do ano selecionado
  const [loadingMeses, setLoadingMeses] = useState(false)

  useEffect(() => {
    api.get('/apuracao/anual/')
      .then(r => {
        const lista = Array.isArray(r.data) ? r.data : []
        setAnuais(lista)
        // Seleciona o ano mais recente por padrão
        if (lista.length > 0) {
          const maisRecente = lista.reduce((a, b) => a.ano > b.ano ? a : b).ano
          setAnoSel(maisRecente)
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  // Busca breakdown mensal quando o ano selecionado muda
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

  useEffect(() => {
    if (anoSel) buscarMeses(anoSel)
  }, [anoSel, buscarMeses])

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

  const desbloqueados  = anuais.filter(a => a.desbloqueado)
  const totalImposto   = r2(desbloqueados.reduce((s, a) => s + r2(a.imposto_brl), 0))
  const totalLucro     = r2(anuais.reduce((s, a) => s + r2(a.lucro_brl),    0))
  const totalDepositos = r2(anuais.reduce((s, a) => s + r2(a.depositos_usd),0))
  const totalSaques    = r2(anuais.reduce((s, a) => s + r2(a.saques_usd),   0))
  const pendentes      = desbloqueados.filter(a => r2(a.imposto_brl) > 0 && !a.darf_pago).length

  // Gráfico anual (visão geral)
  const chartAnual = [...anuais].sort((a, b) => a.ano - b.ano).map(a => ({
    name:    String(a.ano),
    imposto: a.desbloqueado ? r2(a.imposto_brl) : 0,
    lucro:   r2(a.lucro_brl),
    ano:     a.ano,
    locked:  !a.desbloqueado,
  }))

  // Gráfico mensal (breakdown do ano selecionado)
  const chartMensal = [...mesesDetalhe]
    .sort((a, b) => a.mes - b.mes)
    .map(m => ({
      name:    MESES_CURTO[m.mes - 1],
      lucro:   r2(m.ganho_brl),
      mes:     m.mes,
      id:      m.id,
    }))

  return (
    <Layout>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:32 }}>
        <div>
          <h1 style={{ fontSize:24, marginBottom:4 }}>Dashboard</h1>
          <p style={{ color:'var(--muted)', fontSize:13 }}>
            Apuração anual — Lei 14.754/2023 · 15% sobre lucro líquido anual
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/upload')}>
          + Novo Extrato
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign:'center', padding:80 }}><span className="spinner" style={{width:32,height:32}} /></div>
      ) : anuais.length === 0 ? (
        <Empty navigate={navigate} />
      ) : (
        <>
          {/* STATS */}
          <div className="grid-4" style={{ marginBottom:24 }}>
            <CardStat label="Anos apurados" valor={anuais.length} />
            <CardStat label="Lucro total (BRL)" valor={fmtBRL(totalLucro)}
              cor={totalLucro >= 0 ? 'var(--accent)' : 'var(--danger)'} />
            <CardStat label="Imposto total" valor={desbloqueados.length > 0 ? fmtBRL(totalImposto) : '🔒 Bloqueado'} cor="var(--warn)" />
            <CardStat label="DARFs pendentes" valor={desbloqueados.length > 0 ? pendentes : '—'}
              cor={pendentes > 0 ? 'var(--danger)' : undefined} />
          </div>

          {/* GRÁFICOS */}
          <div style={{ display:'grid', gridTemplateColumns: anuais.length > 1 ? '1fr 1fr' : '1fr', gap:16, marginBottom:24 }}>
            {/* Gráfico anual */}
            {anuais.length > 1 && (
              <div className="card">
                <h3 style={{ fontSize:14, marginBottom:16 }}>Imposto por ano</h3>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={chartAnual} barSize={36}
                    onClick={(d) => d?.activePayload && setAnoSel(d.activePayload[0]?.payload?.ano)}>
                    <XAxis dataKey="name" tick={{ fill:'var(--muted)', fontSize:12 }} axisLine={false} tickLine={false} />
                    <YAxis hide />
                    <Tooltip
                      contentStyle={{ background:'#1a2235', border:'1px solid rgba(255,255,255,0.12)', borderRadius:8, fontSize:12, color:'#e8edf5' }}
                      formatter={(v) => [fmtBRL(v), 'Imposto']}
                      labelStyle={{ color:'#8899aa' }}
                      itemStyle={{ color:'#e8edf5' }}
                    />
                    <Bar dataKey="imposto" radius={[6,6,0,0]}>
                      {chartAnual.map((e, i) => (
                        <Cell key={i}
                          fill={e.ano === anoSel ? 'var(--accent)' : (e.imposto > 0 ? 'var(--warn)' : '#3ecf8e60')}
                          opacity={e.ano === anoSel ? 1 : 0.7}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <p style={{ fontSize:11, color:'var(--muted)', textAlign:'center', marginTop:8 }}>
                  Clique em um ano para ver o detalhamento mensal
                </p>
              </div>
            )}

            {/* Gráfico mensal do ano selecionado */}
            {anoSel && (
              <div className="card">
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:16 }}>
                  <h3 style={{ fontSize:14, margin:0 }}>
                    Resultado mensal — {anoSel}
                  </h3>
                  {anuais.length > 1 && (
                    <div style={{ display:'flex', gap:6 }}>
                      {anuais.map(a => (
                        <button key={a.ano}
                          onClick={() => setAnoSel(a.ano)}
                          className={`btn ${anoSel === a.ano ? 'btn-primary' : 'btn-ghost'}`}
                          style={{ padding:'3px 10px', fontSize:11 }}>
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
                  <ResponsiveContainer width="100%" height={160}>
                    <BarChart data={chartMensal} barSize={22}>
                      <XAxis dataKey="name" tick={{ fill:'var(--muted)', fontSize:11 }} axisLine={false} tickLine={false} />
                      <YAxis hide />
                      <Tooltip
                        contentStyle={{ background:'#1a2235', border:'1px solid rgba(255,255,255,0.12)', borderRadius:8, fontSize:12, color:'#e8edf5' }}
                        formatter={(v) => [fmtBRL(v), 'Resultado']}
                        labelStyle={{ color:'#8899aa' }}
                        itemStyle={{ color:'#e8edf5' }}
                      />
                      <Bar dataKey="lucro" radius={[4,4,0,0]}>
                        {chartMensal.map((e, i) => (
                          <Cell key={i} fill={e.lucro >= 0 ? 'var(--accent)' : 'var(--danger)'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            )}
          </div>

          {/* TABELA ANUAL */}
          <div className="card" style={{ overflowX:'auto' }}>
            <h3 style={{ marginBottom:20, fontSize:15 }}>Histórico de apurações anuais</h3>
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
                  <th>Venc. DARF</th>
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
                    <td style={{ fontSize:12, color:'var(--muted)' }}>
                      {r2(a.depositos_usd) > 0 ? fmtUSD(a.depositos_usd) : '—'}
                    </td>
                    <td style={{ fontSize:12, color: r2(a.saques_usd) > 0 ? 'var(--danger)' : 'var(--muted)' }}>
                      {r2(a.saques_usd) > 0 ? `-${fmtUSD(a.saques_usd)}` : '—'}
                    </td>
                    {a.desbloqueado ? (
                      <>
                        <td style={{ fontSize:12, color: r2(a.prejuizo_anterior_brl) > 0 ? 'var(--warn)' : 'var(--muted)' }}>
                          {r2(a.prejuizo_anterior_brl) > 0 ? `-${fmtBRL(a.prejuizo_anterior_brl)}` : '—'}
                        </td>
                        <td>{fmtBRL(a.base_tributavel_brl)}</td>
                        <td style={{ fontSize:12 }}>{((a.aliquota || 0.15) * 100).toFixed(0)}%</td>
                        <td style={{ fontWeight:600, color: r2(a.imposto_brl) > 0 ? 'var(--warn)' : 'var(--accent)' }}>
                          {fmtBRL(a.imposto_brl)}
                        </td>
                        <td style={{ fontSize:12, color:'var(--muted)' }}>{fmtVenc(a.vencimento_darf)}</td>
                        <td>
                          {r2(a.imposto_brl) === 0
                            ? <span className="badge badge-green">Isento</span>
                            : a.darf_pago
                              ? <span className="badge badge-blue">Pago</span>
                              : <span className="badge badge-red">Pendente</span>
                          }
                        </td>
                      </>
                    ) : (
                      <>
                        <td colSpan={5} style={{ textAlign:'center' }}>
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
            border:'1px solid var(--border)', fontSize:12, color:'var(--muted)' }}>
            📋 <strong style={{color:'var(--text)'}}>Lei 14.754/2023</strong> — Apuração anual ·
            Alíquota fixa 15% · Sem isenção · Compensação de prejuízos entre anos ·
            Declarar como "Aplicações financeiras no exterior" no IRPF
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
        Faça o upload do seu extrato da AvaTrade para calcular seu IR conforme a Lei 14.754/2023.
      </p>
      <button className="btn btn-primary" onClick={() => navigate('/upload')}>
        Fazer primeiro upload
      </button>
    </div>
  )
}
