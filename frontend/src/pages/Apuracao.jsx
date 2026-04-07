import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import api    from '../api'

const MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
               'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

const r2     = (v) => Math.round((v || 0) * 100) / 100
const fmtBRL = (v) => `R$ ${r2(v).toLocaleString('pt-BR', { minimumFractionDigits:2, maximumFractionDigits:2 })}`
const fmtUSD = (v) => `US$ ${r2(v).toLocaleString('pt-BR', { minimumFractionDigits:2, maximumFractionDigits:2 })}`

const TIPO_COR = {
  CLOSED:     'var(--accent)',
  OPENED:     'var(--muted)',
  DEPOSIT:    '#60a5fa',
  WITHDRAWAL: 'var(--danger)',
}
const TIPO_LABEL = {
  CLOSED:     'Fechado',
  OPENED:     'Aberto',
  DEPOSIT:    'Depósito',
  WITHDRAWAL: 'Saque',
}

export default function Apuracao() {
  const { id }   = useParams()
  const navigate = useNavigate()
  const [dados,    setDados]    = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [ptaxEdit, setPtaxEdit] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [deletando,setDeletando]= useState(false)
  const [filtroTipo, setFiltroTipo] = useState('todos')

  useEffect(() => {
    api.get(`/apuracao/${id}`)
      .then(r => { setDados(r.data); setPtaxEdit(r.data.ptax?.toFixed(4) || '') })
      .catch(() => navigate('/'))
      .finally(() => setLoading(false))
  }, [id])

  const deletar = async () => {
    if (!window.confirm('Excluir este mês? Os dados serão removidos.')) return
    setDeletando(true)
    try {
      await api.delete(`/apuracao/${id}`)
      navigate('/')
    } catch {
      alert('Erro ao excluir.')
      setDeletando(false)
    }
  }

  const salvarPtax = async () => {
    setSalvando(true)
    try {
      const resp = await api.patch(`/apuracao/${id}/ptax?ptax=${ptaxEdit}`)
      setDados(resp.data)
    } finally { setSalvando(false) }
  }

  if (loading) return <Layout><div style={{textAlign:'center',padding:80}}><span className="spinner" style={{width:32,height:32}} /></div></Layout>

  const ops = dados.operacoes || []
  const opsFiltradas = filtroTipo === 'todos' ? ops : ops.filter(o => o.tipo === filtroTipo)
  const tiposPresentes = [...new Set(ops.map(o => o.tipo))]

  const totalTrading = r2(ops.filter(o => ['CLOSED','OPENED'].includes(o.tipo)).reduce((s, o) => s + r2(o.valor_usd), 0))
  const totalDepositos = r2(ops.filter(o => o.tipo === 'DEPOSIT').reduce((s, o) => s + r2(o.valor_usd), 0))
  const totalSaques = r2(ops.filter(o => o.tipo === 'WITHDRAWAL').reduce((s, o) => s + r2(o.valor_usd), 0))

  return (
    <Layout>
      <div style={{ maxWidth:860, margin:'0 auto' }}>
        {/* HEADER */}
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:32, flexWrap:'wrap', gap:12 }}>
          <div>
            <button onClick={() => navigate(-1)}
              style={{ background:'none',border:'none',color:'var(--muted)',fontSize:13,cursor:'pointer',marginBottom:8,padding:0 }}>
              ← Voltar
            </button>
            <h1 style={{ fontSize:24 }}>{MESES[dados.mes-1]} / {dados.ano}</h1>
            <p style={{ color:'var(--muted)', fontSize:12, marginTop:2 }}>
              Detalhe mensal — breakdown da apuração anual
            </p>
          </div>
          <button
            className="btn btn-ghost"
            style={{ color:'var(--danger)', borderColor:'var(--danger)', padding:'8px 16px', fontSize:12 }}
            onClick={deletar} disabled={deletando}>
            {deletando ? <span className="spinner" style={{width:14,height:14}} /> : 'Excluir mês'}
          </button>
        </div>

        {/* CARDS */}
        <div className="grid-4" style={{ marginBottom:24 }}>
          <div className="card">
            <div style={s.label}>Resultado trading (USD)</div>
            <div style={{ ...s.valor, color: r2(dados.ganho_usd) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
              {r2(dados.ganho_usd) >= 0 ? '+' : ''}{fmtUSD(dados.ganho_usd)}
            </div>
          </div>
          <div className="card">
            <div style={s.label}>PTAX aplicado</div>
            <div style={s.valor}>R$ {dados.ptax ? r2(dados.ptax).toFixed(4) : '—'}</div>
          </div>
          <div className="card">
            <div style={s.label}>Resultado (BRL)</div>
            <div style={{ ...s.valor, color: r2(dados.ganho_brl) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
              {fmtBRL(dados.ganho_brl)}
            </div>
          </div>
          <div className="card">
            <div style={s.label}>Depósitos / Saques</div>
            <div style={{ fontSize:14, fontWeight:700, marginTop:4 }}>
              <span style={{ color:'#60a5fa' }}>+{fmtUSD(dados.depositos_usd)}</span>
              <span style={{ color:'var(--muted)', margin:'0 6px' }}>/</span>
              <span style={{ color:'var(--danger)' }}>-{fmtUSD(dados.saques_usd)}</span>
            </div>
          </div>
        </div>

        {/* PTAX MANUAL */}
        {(!dados.ptax || dados.ptax === 0) && (
          <div className="card" style={{ marginBottom:24, borderColor:'rgba(255,179,71,0.3)' }}>
            <div style={{ fontWeight:600, marginBottom:8 }}>⚠️ PTAX não encontrado automaticamente</div>
            <p style={{ color:'var(--muted)', fontSize:13, marginBottom:16 }}>
              Informe o PTAX de fechamento do último dia útil do mês consultando o{' '}
              <a href="https://www.bcb.gov.br/conversao" target="_blank" rel="noreferrer">Banco Central</a>.
            </p>
            <div style={{ display:'flex', gap:12 }}>
              <input type="number" step="0.0001" value={ptaxEdit}
                onChange={e => setPtaxEdit(e.target.value)} placeholder="Ex: 5.7842"
                style={{ maxWidth:200 }} />
              <button className="btn btn-primary" onClick={salvarPtax} disabled={salvando}>
                {salvando ? <span className="spinner" /> : 'Salvar PTAX'}
              </button>
            </div>
          </div>
        )}

        {/* TABELA DE OPERAÇÕES */}
        {ops.length > 0 && (
          <div className="card">
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:16, flexWrap:'wrap', gap:8 }}>
              <h3 style={{ fontSize:15, margin:0 }}>
                Lançamentos do mês ({ops.length})
              </h3>
              {/* Filtro por tipo */}
              <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
                {['todos', ...tiposPresentes].map(t => (
                  <button key={t}
                    onClick={() => setFiltroTipo(t)}
                    className={`btn ${filtroTipo === t ? 'btn-primary' : 'btn-ghost'}`}
                    style={{ padding:'4px 10px', fontSize:11, color: t !== 'todos' && filtroTipo !== t ? TIPO_COR[t] : undefined }}>
                    {t === 'todos' ? 'Todos' : TIPO_LABEL[t] || t}
                  </button>
                ))}
              </div>
            </div>

            {/* Mini resumo */}
            <div style={{ display:'flex', gap:16, marginBottom:16, flexWrap:'wrap' }}>
              <div style={{ fontSize:12, color:'var(--muted)' }}>
                Trading: <strong style={{ color: totalTrading >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                  {totalTrading >= 0 ? '+' : ''}{fmtUSD(totalTrading)}
                </strong>
              </div>
              {totalDepositos > 0 && (
                <div style={{ fontSize:12, color:'var(--muted)' }}>
                  Depósitos: <strong style={{ color:'#60a5fa' }}>+{fmtUSD(totalDepositos)}</strong>
                </div>
              )}
              {totalSaques !== 0 && (
                <div style={{ fontSize:12, color:'var(--muted)' }}>
                  Saques: <strong style={{ color:'var(--danger)' }}>{fmtUSD(totalSaques)}</strong>
                </div>
              )}
            </div>

            <div style={{ overflowX:'auto' }}>
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Adj. No</th>
                    <th>Data</th>
                    <th>Tipo</th>
                    <th>Descrição</th>
                    <th style={{ textAlign:'right' }}>Valor (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  {opsFiltradas.map((op, i) => (
                    <tr key={i}>
                      <td style={{ color:'var(--muted)', fontSize:11 }}>{op.adj_no || '—'}</td>
                      <td style={{ fontSize:12 }}>
                        {op.data ? new Date(op.data).toLocaleDateString('pt-BR') : '—'}
                      </td>
                      <td>
                        <span style={{
                          fontSize:10, padding:'2px 8px', borderRadius:20, fontWeight:600,
                          background: `${TIPO_COR[op.tipo] || 'var(--muted)'}20`,
                          color: TIPO_COR[op.tipo] || 'var(--muted)',
                          border: `1px solid ${TIPO_COR[op.tipo] || 'var(--muted)'}40`,
                        }}>
                          {TIPO_LABEL[op.tipo] || op.tipo}
                        </span>
                      </td>
                      <td style={{ fontSize:11, color:'var(--muted)', maxWidth:220, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                        {op.descricao || '—'}
                      </td>
                      <td style={{ textAlign:'right', fontWeight:600, fontSize:13,
                        color: r2(op.valor_usd) >= 0 ? 'var(--accent)' : 'var(--danger)' }}>
                        {r2(op.valor_usd) >= 0 ? '+' : ''}{fmtUSD(op.valor_usd)}
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
  label: { fontSize:12, color:'var(--muted)', marginBottom:8, textTransform:'uppercase', letterSpacing:'0.5px' },
  valor: { fontSize:20, fontFamily:'Syne', fontWeight:800 },
}
