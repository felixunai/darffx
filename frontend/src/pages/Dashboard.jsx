import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import Layout from '../components/Layout'
import api    from '../api'

const MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

const r2 = (v) => Math.round((v || 0) * 100) / 100
const fmtBRL = (v) => `R$ ${r2(v).toLocaleString('pt-BR', { minimumFractionDigits:2, maximumFractionDigits:2 })}`
const fmtUSD = (v) => `US$ ${r2(v).toLocaleString('pt-BR', { minimumFractionDigits:2, maximumFractionDigits:2 })}`
const fmtPct = (v) => `${((v || 0.15) * 100).toFixed(0)}%`
const fmtVenc = (iso) => {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

function CardStat({ label, valor, cor }) {
  return (
    <div className="card" style={{ borderColor: cor ? `${cor}30` : undefined }}>
      <div style={{ fontSize:12, color:'var(--muted)', marginBottom:8, textTransform:'uppercase', letterSpacing:'0.5px' }}>{label}</div>
      <div style={{ fontSize:24, fontFamily:'Syne', fontWeight:800, color: cor || 'var(--text)' }}>{valor}</div>
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [apuracoes, setApuracoes] = useState([])
  const [loading,   setLoading]   = useState(true)
  const [deletando, setDeletando] = useState(null)
  const [anoFiltro, setAnoFiltro] = useState('todos')

  useEffect(() => {
    api.get('/apuracao/')
      .then(r => setApuracoes(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const deletar = async (a) => {
    const label = `${MESES[a.mes-1]}/${a.ano}`
    if (!window.confirm(`Excluir apuração de ${label}? Os dados serão removidos e você poderá fazer novo upload.`)) return
    setDeletando(a.id)
    try {
      await api.delete(`/apuracao/${a.id}`)
      setApuracoes(prev => prev.filter(x => x.id !== a.id))
    } catch {
      alert('Erro ao excluir. Tente novamente.')
    } finally {
      setDeletando(null)
    }
  }

  // Anos disponíveis para filtro
  const anos = [...new Set(apuracoes.map(a => a.ano))].sort((a, b) => b - a)

  // Apurações filtradas (para tabela e totais)
  const filtradas = anoFiltro === 'todos'
    ? apuracoes
    : apuracoes.filter(a => a.ano === Number(anoFiltro))

  const totalImposto  = r2(filtradas.reduce((s, a) => s + r2(a.imposto_brl),  0))
  const totalGanho    = r2(filtradas.reduce((s, a) => s + r2(a.ganho_brl),    0))
  const totalDepositos= r2(filtradas.reduce((s, a) => s + r2(a.depositos_usd),0))
  const totalSaques   = r2(filtradas.reduce((s, a) => s + r2(a.saques_usd),   0))
  const totalCarry    = r2(filtradas.reduce((s, a) => s + r2(a.carry_fwd_brl),0))
  const pendentes     = apuracoes.filter(a => a.imposto_brl > 0 && !a.darf_pago).length

  const chartData = [...filtradas]
    .sort((a, b) => a.ano - b.ano || a.mes - b.mes)
    .map(a => ({
      name:    `${MESES[a.mes-1]}/${String(a.ano).slice(2)}`,
      imposto: r2(a.imposto_brl),
      ganho:   r2(a.ganho_brl),
    }))

  return (
    <Layout>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:32 }}>
        <div>
          <h1 style={{ fontSize:24, marginBottom:4 }}>Dashboard</h1>
          <p style={{ color:'var(--muted)', fontSize:14 }}>Resumo do seu IR no Forex</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/upload')}>
          + Novo Extrato
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign:'center', padding:80 }}><span className="spinner" style={{width:32,height:32}} /></div>
      ) : apuracoes.length === 0 ? (
        <Empty navigate={navigate} />
      ) : (
        <>
          <div className="grid-4" style={{ marginBottom:24 }}>
            <CardStat label="Total de meses" valor={apuracoes.length} />
            <CardStat label="Ganho total (BRL)" valor={fmtBRL(totalGanho)} cor={totalGanho >= 0 ? 'var(--accent)' : 'var(--danger)'} />
            <CardStat label="Imposto total" valor={fmtBRL(totalImposto)} cor="var(--warn)" />
            <CardStat label="DARFs pendentes" valor={pendentes} cor={pendentes > 0 ? 'var(--danger)' : undefined} />
          </div>

          {chartData.length > 1 && (
            <div className="card" style={{ marginBottom:24 }}>
              <h3 style={{ marginBottom:20, fontSize:15 }}>Imposto por mês (R$)</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chartData} barSize={28}>
                  <XAxis dataKey="name" tick={{ fill:'var(--muted)', fontSize:12 }} axisLine={false} tickLine={false} />
                  <YAxis hide />
                  <Tooltip
                    contentStyle={{ background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:8, fontSize:13 }}
                    formatter={(v) => [fmtBRL(v), 'Imposto']}
                    labelStyle={{ color:'var(--muted)' }}
                  />
                  <Bar dataKey="imposto" radius={[6,6,0,0]}>
                    {chartData.map((e, i) => (
                      <Cell key={i} fill={e.imposto > 0 ? 'var(--warn)' : 'var(--accent)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="card" style={{ overflowX:'auto' }}>
            {/* cabeçalho com filtro de ano */}
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:20 }}>
              <h3 style={{ fontSize:15, margin:0 }}>Histórico de apurações</h3>
              <div style={{ display:'flex', gap:8 }}>
                <button
                  onClick={() => setAnoFiltro('todos')}
                  className={`btn ${anoFiltro === 'todos' ? 'btn-primary' : 'btn-ghost'}`}
                  style={{ padding:'4px 12px', fontSize:12 }}
                >
                  Todos
                </button>
                {anos.map(ano => (
                  <button
                    key={ano}
                    onClick={() => setAnoFiltro(String(ano))}
                    className={`btn ${anoFiltro === String(ano) ? 'btn-primary' : 'btn-ghost'}`}
                    style={{ padding:'4px 12px', fontSize:12 }}
                  >
                    {ano}
                  </button>
                ))}
              </div>
            </div>

            <table className="tabela" style={{ minWidth:1000 }}>
              <thead>
                <tr>
                  <th>Mês / Ano</th>
                  <th>Resultado (USD)</th>
                  <th>PTAX</th>
                  <th>Resultado (BRL)</th>
                  <th>Depósitos</th>
                  <th>Saques</th>
                  <th>Carry Fwd</th>
                  <th>Alíquota</th>
                  <th>Imposto</th>
                  <th>Venc. DARF</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {[...filtradas]
                  .sort((a, b) => a.ano - b.ano || a.mes - b.mes)
                  .map(a => (
                  <tr key={a.id}>
                    <td style={{ fontWeight:600 }}>{MESES[a.mes-1]} / {a.ano}</td>
                    <td style={{ color: r2(a.ganho_usd) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                      {r2(a.ganho_usd) >= 0 ? '+' : ''}{fmtUSD(a.ganho_usd)}
                    </td>
                    <td style={{ color:'var(--muted)' }}>
                      {a.ptax ? `R$ ${r2(a.ptax).toFixed(4)}` : '—'}
                    </td>
                    <td style={{ color: r2(a.ganho_brl) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                      {fmtBRL(a.ganho_brl)}
                    </td>
                    <td style={{ color:'var(--muted)', fontSize:12 }}>
                      {r2(a.depositos_usd) > 0 ? fmtUSD(a.depositos_usd) : '—'}
                    </td>
                    <td style={{ color:'var(--muted)', fontSize:12 }}>
                      {r2(a.saques_usd) > 0 ? fmtUSD(a.saques_usd) : '—'}
                    </td>
                    <td style={{ color: r2(a.carry_fwd_brl) > 0 ? 'var(--warn)' : 'var(--muted)', fontSize:12 }}>
                      {r2(a.carry_fwd_brl) > 0 ? `-${fmtBRL(a.carry_fwd_brl)}` : '—'}
                    </td>
                    <td style={{ color:'var(--muted)', fontSize:12 }}>
                      {fmtPct(a.aliquota)}
                      {a.tem_day_trade && <span style={{ color:'var(--warn)', marginLeft:4, fontSize:10 }}>DT</span>}
                    </td>
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
                    <td>
                      <div style={{ display:'flex', gap:8 }}>
                        <button className="btn btn-ghost" style={{ padding:'6px 14px', fontSize:12 }}
                          onClick={() => navigate(`/apuracao/${a.id}`)}>Ver</button>
                        <button
                          className="btn btn-ghost"
                          style={{ padding:'6px 14px', fontSize:12, color:'var(--danger)', borderColor:'var(--danger)' }}
                          onClick={() => deletar(a)} disabled={deletando === a.id}>
                          {deletando === a.id ? <span className="spinner" style={{width:12,height:12}} /> : 'Limpar'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>

              {/* LINHA DE TOTAIS */}
              {filtradas.length > 0 && (
                <tfoot>
                  <tr style={{ fontWeight:700, borderTop:'2px solid var(--border)', background:'var(--surface2)' }}>
                    <td>TOTAL</td>
                    <td>—</td>
                    <td>—</td>
                    <td style={{ color: totalGanho >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                      {fmtBRL(totalGanho)}
                    </td>
                    <td style={{ fontSize:12 }}>{totalDepositos > 0 ? fmtUSD(totalDepositos) : '—'}</td>
                    <td style={{ fontSize:12 }}>{totalSaques > 0 ? fmtUSD(totalSaques) : '—'}</td>
                    <td style={{ fontSize:12 }}>{totalCarry > 0 ? `-${fmtBRL(totalCarry)}` : '—'}</td>
                    <td>—</td>
                    <td style={{ color:'var(--warn)' }}>{fmtBRL(totalImposto)}</td>
                    <td>—</td>
                    <td>—</td>
                    <td></td>
                  </tr>
                </tfoot>
              )}
            </table>
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
        Faça o upload do seu extrato da AvaTrade para calcular seu IR automaticamente.
      </p>
      <button className="btn btn-primary" onClick={() => navigate('/upload')}>
        Fazer primeiro upload
      </button>
    </div>
  )
}
