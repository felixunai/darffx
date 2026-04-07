import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import Layout from '../components/Layout'
import api    from '../api'

const MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

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

  const totalImposto = apuracoes.reduce((s, a) => s + (a.imposto_brl || 0), 0)
  const totalGanho   = apuracoes.reduce((s, a) => s + (a.ganho_brl  || 0), 0)
  const pendentes    = apuracoes.filter(a => a.imposto_brl > 0 && !a.darf_pago).length

  const chartData = [...apuracoes]
    .sort((a, b) => a.ano - b.ano || a.mes - b.mes)
    .map(a => ({
      name:   `${MESES[a.mes-1]}/${String(a.ano).slice(2)}`,
      imposto: parseFloat(a.imposto_brl.toFixed(2)),
      ganho:   parseFloat(a.ganho_brl.toFixed(2)),
    }))

  const fmt = (v) => `R$ ${v.toLocaleString('pt-BR', { minimumFractionDigits:2 })}`

  return (
    <Layout>
      {/* HEADER */}
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
          {/* STATS */}
          <div className="grid-4" style={{ marginBottom:24 }}>
            <CardStat label="Total de meses" valor={apuracoes.length} />
            <CardStat label="Ganho total (BRL)" valor={fmt(totalGanho)} cor="var(--accent)" />
            <CardStat label="Imposto total" valor={fmt(totalImposto)} cor="var(--warn)" />
            <CardStat label="DARFs pendentes" valor={pendentes} cor={pendentes > 0 ? 'var(--danger)' : undefined} />
          </div>

          {/* GRÁFICO */}
          {chartData.length > 1 && (
            <div className="card" style={{ marginBottom:24 }}>
              <h3 style={{ marginBottom:20, fontSize:15 }}>Imposto por mês (R$)</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chartData} barSize={28}>
                  <XAxis dataKey="name" tick={{ fill:'var(--muted)', fontSize:12 }} axisLine={false} tickLine={false} />
                  <YAxis hide />
                  <Tooltip
                    contentStyle={{ background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:8, fontSize:13 }}
                    formatter={(v) => [`R$ ${v.toLocaleString('pt-BR',{minimumFractionDigits:2})}`, 'Imposto']}
                    labelStyle={{ color:'var(--muted)' }}
                  />
                  <Bar dataKey="imposto" radius={[6,6,0,0]}>
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={chartData[i].imposto > 0 ? 'var(--warn)' : 'var(--accent)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* TABELA */}
          <div className="card">
            <h3 style={{ marginBottom:20, fontSize:15 }}>Histórico de apurações</h3>
            <table className="tabela">
              <thead>
                <tr>
                  <th>Mês / Ano</th>
                  <th>Resultado (USD)</th>
                  <th>PTAX</th>
                  <th>Resultado (BRL)</th>
                  <th>Imposto</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {apuracoes.map(a => (
                  <tr key={a.id}>
                    <td style={{ fontWeight:600 }}>{MESES[a.mes-1]} / {a.ano}</td>
                    <td style={{ color: a.ganho_usd >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                      {a.ganho_usd >= 0 ? '+' : ''}US$ {a.ganho_usd.toLocaleString('pt-BR',{minimumFractionDigits:2})}
                    </td>
                    <td style={{ color:'var(--muted)' }}>R$ {a.ptax?.toFixed(4) || '—'}</td>
                    <td>{fmt(a.ganho_brl)}</td>
                    <td style={{ fontWeight:600, color: a.imposto_brl > 0 ? 'var(--warn)' : 'var(--accent)' }}>
                      {fmt(a.imposto_brl)}
                    </td>
                    <td>
                      {a.imposto_brl === 0
                        ? <span className="badge badge-green">Isento</span>
                        : a.darf_pago
                          ? <span className="badge badge-blue">Pago</span>
                          : <span className="badge badge-red">Pendente</span>
                      }
                    </td>
                    <td>
                      <div style={{ display:'flex', gap:8 }}>
                        <button
                          className="btn btn-ghost"
                          style={{ padding:'6px 14px', fontSize:12 }}
                          onClick={() => navigate(`/apuracao/${a.id}`)}
                        >
                          Ver
                        </button>
                        <button
                          className="btn btn-ghost"
                          style={{ padding:'6px 14px', fontSize:12, color:'var(--danger)', borderColor:'var(--danger)' }}
                          onClick={() => deletar(a)}
                          disabled={deletando === a.id}
                        >
                          {deletando === a.id ? <span className="spinner" style={{width:12,height:12}} /> : 'Limpar'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
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
