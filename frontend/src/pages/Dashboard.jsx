import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import Layout from '../components/Layout'
import api    from '../api'

const r2  = (v) => Math.round((v || 0) * 100) / 100
const fmtBRL = (v) => `R$ ${r2(v).toLocaleString('pt-BR', { minimumFractionDigits:2, maximumFractionDigits:2 })}`
const fmtUSD = (v) => `US$ ${r2(v).toLocaleString('pt-BR', { minimumFractionDigits:2, maximumFractionDigits:2 })}`
const fmtVenc = (iso) => {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

function CardStat({ label, valor, cor, sub }) {
  return (
    <div className="card" style={{ borderColor: cor ? `${cor}30` : undefined }}>
      <div style={{ fontSize:12, color:'var(--muted)', marginBottom:8, textTransform:'uppercase', letterSpacing:'0.5px' }}>{label}</div>
      <div style={{ fontSize:22, fontFamily:'Syne', fontWeight:800, color: cor || 'var(--text)' }}>{valor}</div>
      {sub && <div style={{ fontSize:11, color:'var(--muted)', marginTop:4 }}>{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [anuais,   setAnuais]   = useState([])
  const [loading,  setLoading]  = useState(true)
  const [deletando,setDeletando]= useState(null)

  useEffect(() => {
    api.get('/apuracao/anual/')
      .then(r => setAnuais(Array.isArray(r.data) ? r.data : []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const deletar = async (a) => {
    if (!window.confirm(`Excluir toda a apuração de ${a.ano}? Todos os meses serão removidos.`)) return
    setDeletando(a.ano)
    try {
      await api.delete(`/apuracao/anual/${a.ano}`)
      setAnuais(prev => prev.filter(x => x.ano !== a.ano))
    } catch {
      alert('Erro ao excluir. Tente novamente.')
    } finally {
      setDeletando(null)
    }
  }

  const totalImposto  = r2(anuais.reduce((s, a) => s + r2(a.imposto_brl),  0))
  const totalLucro    = r2(anuais.reduce((s, a) => s + r2(a.lucro_brl),    0))
  const totalDepositos= r2(anuais.reduce((s, a) => s + r2(a.depositos_usd),0))
  const totalSaques   = r2(anuais.reduce((s, a) => s + r2(a.saques_usd),   0))
  const pendentes     = anuais.filter(a => r2(a.imposto_brl) > 0 && !a.darf_pago).length

  const chartData = [...anuais]
    .sort((a, b) => a.ano - b.ano)
    .map(a => ({
      name:    String(a.ano),
      imposto: r2(a.imposto_brl),
      lucro:   r2(a.lucro_brl),
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
          <div className="grid-4" style={{ marginBottom:24 }}>
            <CardStat label="Anos apurados" valor={anuais.length} />
            <CardStat
              label="Lucro total (BRL)"
              valor={fmtBRL(totalLucro)}
              cor={totalLucro >= 0 ? 'var(--accent)' : 'var(--danger)'}
            />
            <CardStat label="Imposto total" valor={fmtBRL(totalImposto)} cor="var(--warn)" />
            <CardStat
              label="DARFs pendentes"
              valor={pendentes}
              cor={pendentes > 0 ? 'var(--danger)' : undefined}
            />
          </div>

          {chartData.length > 0 && (
            <div className="card" style={{ marginBottom:24 }}>
              <h3 style={{ marginBottom:20, fontSize:15 }}>Imposto por ano (R$)</h3>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={chartData} barSize={40}>
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
                  <tr key={a.ano}>
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
                    <td style={{ fontSize:12, color:'var(--muted)' }}>
                      {r2(a.saques_usd) > 0 ? fmtUSD(a.saques_usd) : '—'}
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
                          onClick={() => navigate(`/apuracao/anual/${a.ano}`)}>Ver</button>
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
                    <td style={{ fontSize:12 }}>{totalSaques > 0 ? fmtUSD(totalSaques) : '—'}</td>
                    <td>—</td>
                    <td>—</td>
                    <td>15%</td>
                    <td style={{ color:'var(--warn)' }}>{fmtBRL(totalImposto)}</td>
                    <td>—</td>
                    <td>—</td>
                    <td></td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>

          <div style={{ marginTop:16, padding:'12px 16px', background:'var(--surface)', borderRadius:12, border:'1px solid var(--border)', fontSize:12, color:'var(--muted)' }}>
            📋 <strong style={{color:'var(--text)'}}>Lei 14.754/2023</strong> — Apuração anual · Alíquota fixa 15% · Sem isenção ·
            Compensação de prejuízos entre anos · Declarar como "Aplicações financeiras no exterior" no IRPF
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
