import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import api    from '../api'

const MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
               'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

export default function Apuracao() {
  const { id }   = useParams()
  const navigate = useNavigate()
  const [dados,   setDados]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [ptaxEdit, setPtaxEdit] = useState('')
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    api.get(`/apuracao/${id}`)
      .then(r => { setDados(r.data); setPtaxEdit(r.data.ptax?.toFixed(4) || '') })
      .catch(() => navigate('/'))
      .finally(() => setLoading(false))
  }, [id])

  const baixarPdf = async () => {
    const resp = await api.get(`/apuracao/${id}/pdf`, { responseType:'blob' })
    const url  = URL.createObjectURL(resp.data)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `darffx_${dados.ano}_${String(dados.mes).padStart(2,'0')}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  }

  const marcarPago = async () => {
    await api.patch(`/apuracao/${id}/pago`)
    setDados(d => ({ ...d, darf_pago: true }))
  }

  const salvarPtax = async () => {
    setSalvando(true)
    try {
      const resp = await api.patch(`/apuracao/${id}/ptax?ptax=${ptaxEdit}`)
      setDados(resp.data)
    } finally {
      setSalvando(false)
    }
  }

  const fmt = (v) => `R$ ${(v || 0).toLocaleString('pt-BR', { minimumFractionDigits:2 })}`
  const fmtUsd = (v) => `US$ ${(v || 0).toLocaleString('pt-BR', { minimumFractionDigits:2 })}`

  if (loading) return <Layout><div style={{textAlign:'center',padding:80}}><span className="spinner" style={{width:32,height:32}} /></div></Layout>

  return (
    <Layout>
      <div style={{ maxWidth:800, margin:'0 auto' }}>
        {/* HEADER */}
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:32, flexWrap:'wrap', gap:12 }}>
          <div>
            <button
              onClick={() => navigate('/')}
              style={{ background:'none',border:'none',color:'var(--muted)',fontSize:13,cursor:'pointer',marginBottom:8,padding:0 }}
            >
              ← Voltar
            </button>
            <h1 style={{ fontSize:24 }}>{MESES[dados.mes-1]} / {dados.ano}</h1>
          </div>
          <div style={{ display:'flex', gap:10 }}>
            {!dados.darf_pago && dados.imposto_brl > 0 && (
              <button className="btn btn-ghost" onClick={marcarPago}>
                ✓ Marcar DARF como pago
              </button>
            )}
            <button className="btn btn-primary" onClick={baixarPdf}>
              ↓ Baixar Relatório PDF
            </button>
          </div>
        </div>

        {/* CARDS */}
        <div className="grid-4" style={{ marginBottom:24 }}>
          <div className="card">
            <div style={s.cardLabel}>Resultado (USD)</div>
            <div style={{ ...s.cardValor, color: dados.ganho_usd >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
              {dados.ganho_usd >= 0 ? '+' : ''}{fmtUsd(dados.ganho_usd)}
            </div>
          </div>
          <div className="card">
            <div style={s.cardLabel}>PTAX aplicado</div>
            <div style={s.cardValor}>R$ {dados.ptax?.toFixed(4)}</div>
          </div>
          <div className="card">
            <div style={s.cardLabel}>Resultado (BRL)</div>
            <div style={{ ...s.cardValor, color: dados.ganho_brl >= 0 ? 'var(--text)' : 'var(--danger)' }}>
              {fmt(dados.ganho_brl)}
            </div>
          </div>
          <div className="card" style={{ borderColor: dados.imposto_brl > 0 ? 'rgba(255,179,71,0.3)' : 'rgba(0,229,160,0.3)' }}>
            <div style={s.cardLabel}>Imposto DARF</div>
            <div style={{ ...s.cardValor, color: dados.imposto_brl > 0 ? 'var(--warn)' : 'var(--accent)' }}>
              {fmt(dados.imposto_brl)}
            </div>
          </div>
        </div>

        {/* DARF BOX */}
        {dados.imposto_brl > 0 && (
          <div style={{ background:'var(--surface)', border:`1px solid ${dados.darf_pago ? 'rgba(0,149,255,0.3)' : 'rgba(255,179,71,0.3)'}`, borderRadius:16, padding:24, marginBottom:24 }}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap', gap:12 }}>
              <div>
                <div style={{ fontFamily:'Syne', fontWeight:800, fontSize:18, marginBottom:4 }}>
                  DARF — Código 8523
                </div>
                <div style={{ color:'var(--muted)', fontSize:13 }}>
                  Alíquota: {(dados.aliquota * 100).toFixed(0)}%
                  {dados.tem_day_trade ? ' (Day Trade)' : ' (Operação Normal)'}
                </div>
              </div>
              <div style={{ textAlign:'right' }}>
                <div style={{ fontSize:28, fontFamily:'Syne', fontWeight:800, color: dados.darf_pago ? 'var(--accent2)' : 'var(--warn)' }}>
                  {fmt(dados.imposto_brl)}
                </div>
                {dados.darf_pago
                  ? <span className="badge badge-blue">✓ Pago</span>
                  : <span className="badge badge-yellow">Pendente</span>
                }
              </div>
            </div>
          </div>
        )}

        {/* PTAX MANUAL */}
        {(!dados.ptax || dados.ptax === 0) && (
          <div className="card" style={{ marginBottom:24, borderColor:'rgba(255,179,71,0.3)' }}>
            <div style={{ fontWeight:600, marginBottom:8 }}>⚠️ PTAX não encontrado automaticamente</div>
            <p style={{ color:'var(--muted)', fontSize:13, marginBottom:16 }}>
              Informe o PTAX de fechamento do último dia útil do mês consultando o{' '}
              <a href="https://www.bcb.gov.br/conversao" target="_blank" rel="noreferrer">site do Banco Central</a>.
            </p>
            <div style={{ display:'flex', gap:12 }}>
              <input
                type="number" step="0.0001"
                value={ptaxEdit}
                onChange={e => setPtaxEdit(e.target.value)}
                placeholder="Ex: 5.7842"
                style={{ maxWidth:200 }}
              />
              <button className="btn btn-primary" onClick={salvarPtax} disabled={salvando}>
                {salvando ? <span className="spinner" /> : 'Salvar PTAX'}
              </button>
            </div>
          </div>
        )}

        {/* TABELA DE OPERAÇÕES */}
        {dados.operacoes?.length > 0 && (
          <div className="card">
            <h3 style={{ marginBottom:20, fontSize:15 }}>
              Operações CLOSED do mês ({dados.operacoes.length})
            </h3>
            <div style={{ overflowX:'auto' }}>
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Adj. No</th>
                    <th>Data</th>
                    <th>Descrição</th>
                    <th style={{ textAlign:'right' }}>Valor (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  {dados.operacoes.map((op, i) => (
                    <tr key={i}>
                      <td style={{ color:'var(--muted)', fontSize:12 }}>{op.adj_no}</td>
                      <td style={{ fontSize:12 }}>
                        {op.data ? new Date(op.data).toLocaleDateString('pt-BR') : '—'}
                      </td>
                      <td style={{ fontSize:12, color:'var(--muted)' }}>{op.descricao}</td>
                      <td style={{ textAlign:'right', fontWeight:600, color: op.valor_usd >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                        {op.valor_usd >= 0 ? '+' : ''}US$ {op.valor_usd.toLocaleString('pt-BR', { minimumFractionDigits:2 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}

const s = {
  cardLabel: { fontSize:12, color:'var(--muted)', marginBottom:8, textTransform:'uppercase', letterSpacing:'0.5px' },
  cardValor: { fontSize:20, fontFamily:'Syne', fontWeight:800 },
}
