import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { useAuth } from '../context/AuthContext'
import Layout from '../components/Layout'
import api from '../api'

const TIPOS = ['Todos', 'straddle', 'strangle', 'bull_spread', 'bear_spread']
const PARES = ['Todos', 'EUR/USD', 'GBP/USD', 'USD/JPY', 'CAD/USD', 'AUD/USD', 'CHF/USD']

const REC_CONFIG = {
  BUY:        { label: 'COMPRAR', color: '#00E5A0', bg: 'rgba(0,229,160,0.15)' },
  SELL:       { label: 'VENDER',  color: '#FF4C6A', bg: 'rgba(255,76,106,0.15)' },
  BULL_SPREAD:{ label: 'BULL ↑',  color: '#00E5A0', bg: 'rgba(0,229,160,0.15)' },
  BEAR_SPREAD:{ label: 'BEAR ↓',  color: '#FF4C6A', bg: 'rgba(255,76,106,0.15)' },
  NEUTRAL:    { label: 'NEUTRO',  color: '#8E99A8', bg: 'rgba(142,153,168,0.15)' },
}

const TEND_CONFIG = {
  ALTA:    { color: '#00E5A0', label: '↑ ALTA' },
  BAIXA:   { color: '#FF4C6A', label: '↓ BAIXA' },
  LATERAL: { color: '#8E99A8', label: '→ LATERAL' },
}

function Badge({ rec }) {
  const cfg = REC_CONFIG[rec] || REC_CONFIG.NEUTRAL
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
      color: cfg.color, background: cfg.bg,
      border: `1px solid ${cfg.color}40`, whiteSpace: 'nowrap',
    }}>
      {cfg.label}
    </span>
  )
}

function TendBadge({ tend }) {
  const cfg = TEND_CONFIG[tend] || TEND_CONFIG.LATERAL
  return (
    <span style={{ fontSize: 11, fontWeight: 600, color: cfg.color }}>{cfg.label}</span>
  )
}

function fmt(v, dec = 5) {
  if (v == null) return '—'
  return Number(v).toFixed(dec)
}

function fmtPct(v) {
  if (v == null) return '—'
  return `${(Number(v) * 100).toFixed(2)}%`
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function HistoricoModal({ par, tipo, onClose }) {
  const [dados, setDados] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/sinais', { params: { par, tipo, limit: 200 } })
      .then(r => {
        const pts = r.data
          .filter(s => s.iv_media != null)
          .map(s => ({
            dt: new Date(s.criado_em).toLocaleDateString('pt-BR'),
            iv: parseFloat((s.iv_media * 100).toFixed(3)),
            score: s.score,
          }))
          .reverse()
        setDados(pts)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [par, tipo])

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }} onClick={onClose}>
      <div style={{
        background: 'var(--surface)', borderRadius: 12, padding: 24,
        width: 'min(700px, 95vw)', maxHeight: '80vh', overflow: 'auto',
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ fontWeight: 700 }}>{par} — {tipo} — IV histórica (%)</div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 18 }}>✕</button>
        </div>
        {loading ? (
          <div style={{ textAlign: 'center', color: 'var(--muted)', padding: 32 }}>Carregando…</div>
        ) : dados.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--muted)', padding: 32 }}>Sem histórico suficiente.</div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={dados}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="dt" tick={{ fontSize: 11, fill: 'var(--muted)' }} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--muted)' }} unit="%" />
              <Tooltip formatter={(v, n) => [`${v}${n === 'iv' ? '%' : ''}`, n === 'iv' ? 'IV Média' : 'Score']} />
              <Line type="monotone" dataKey="iv" stroke="var(--accent)" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="score" stroke="#FFB347" dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

function ExpandedDetail({ s, onHistorico }) {
  return (
    <tr>
      <td colSpan={14} style={{ padding: 0, background: 'var(--surface2)' }}>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* Strikes recomendados */}
          {s.strikes_recomendados && (
            <div style={{
              background: 'var(--surface)', borderRadius: 8, padding: '10px 14px',
              border: '1px solid var(--border)',
            }}>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Strikes Recomendados
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: 13, color: 'var(--accent)', fontWeight: 700 }}>
                {s.strikes_recomendados}
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            {/* Motivo */}
            {s.motivo && (
              <div style={{
                flex: '1 1 340px', background: 'var(--surface)', borderRadius: 8,
                padding: '10px 14px', border: '1px solid var(--border)',
              }}>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Análise
                </div>
                <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text)' }}>
                  {s.motivo}
                </div>
              </div>
            )}

            {/* Indicadores técnicos */}
            <div style={{
              flex: '0 0 240px', background: 'var(--surface)', borderRadius: 8,
              padding: '10px 14px', border: '1px solid var(--border)',
            }}>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Análise Técnica
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--muted)' }}>Tendência</span>
                  {s.tendencia ? <TendBadge tend={s.tendencia} /> : <span style={{ color: 'var(--muted)' }}>—</span>}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--muted)' }}>RSI 14</span>
                  <span style={{ color: s.rsi_14 > 65 ? '#FF4C6A' : s.rsi_14 < 35 ? '#00E5A0' : 'var(--text)', fontWeight: 600 }}>
                    {s.rsi_14 != null ? s.rsi_14.toFixed(1) : '—'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--muted)' }}>SMA 20</span>
                  <span>{fmt(s.sma20)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--muted)' }}>SMA 50</span>
                  <span>{fmt(s.sma50)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--muted)' }}>BB Width</span>
                  <span style={{ color: s.bb_width != null && s.bb_width < 0.008 ? '#FFB347' : 'var(--text)' }}>
                    {s.bb_width != null ? (s.bb_width * 100).toFixed(3) + '%' : '—'}
                    {s.bb_width != null && s.bb_width < 0.008 && (
                      <span style={{ marginLeft: 4, fontSize: 10, color: '#FFB347' }}>squeeze</span>
                    )}
                  </span>
                </div>
                {s.pc_ratio != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--muted)' }}>P/C Ratio</span>
                    <span>{s.pc_ratio.toFixed(2)}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          <button
            onClick={e => { e.stopPropagation(); onHistorico() }}
            style={{
              alignSelf: 'flex-start', background: 'none',
              border: '1px solid var(--border)', borderRadius: 6,
              padding: '4px 12px', cursor: 'pointer', color: 'var(--muted)', fontSize: 12,
            }}
          >
            IV histórica →
          </button>
        </div>
      </td>
    </tr>
  )
}

export default function Sinais() {
  const { user } = useAuth()
  const navigate  = useNavigate()
  const isPaid    = user?.plano === 'anual' || user?.plano === 'admin'

  const [sinais, setSinais]           = useState([])
  const [loading, setLoading]         = useState(true)
  const [erro, setErro]               = useState(null)
  const [filtroTipo, setFiltroTipo]   = useState('Todos')
  const [filtroPar, setFiltroPar]     = useState('Todos')
  const [modal, setModal]             = useState(null)   // { par, tipo }
  const [expandedId, setExpandedId]   = useState(null)

  const carregar = useCallback(() => {
    if (!isPaid) return
    setLoading(true)
    setErro(null)
    api.get('/sinais/latest')
      .then(r => setSinais(r.data))
      .catch(() => setErro('Erro ao carregar sinais.'))
      .finally(() => setLoading(false))
  }, [isPaid])

  useEffect(() => { carregar() }, [carregar])

  const filtrados = sinais.filter(s => {
    const okTipo = filtroTipo === 'Todos' || s.tipo_sinal === filtroTipo
    const okPar  = filtroPar  === 'Todos' || s.par === filtroPar
    return okTipo && okPar
  })

  return (
    <Layout>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 16px 40px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 24 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>Sinais de Opções</h1>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>CME · IBKR · FOP</span>
          {isPaid && (
            <button
              onClick={carregar}
              style={{ marginLeft: 'auto', fontSize: 12, padding: '4px 12px',
                       background: 'var(--surface2)', border: '1px solid var(--border)',
                       borderRadius: 8, color: 'var(--text)', cursor: 'pointer' }}
            >
              ↻ Atualizar
            </button>
          )}
        </div>

        {/* Paywall */}
        {!isPaid && (
          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 12, padding: 40, textAlign: 'center',
          }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>📊</div>
            <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 8 }}>Recurso exclusivo</div>
            <div style={{ color: 'var(--muted)', marginBottom: 24 }}>
              Sinais de opções estruturadas (straddle, strangle, bull/bear spread) com Greeks e IV real da CME são exclusivos do plano anual.
            </div>
            <button
              onClick={() => navigate('/upgrade')}
              style={{
                background: 'var(--accent)', color: '#000', fontWeight: 700,
                padding: '10px 28px', borderRadius: 8, border: 'none', cursor: 'pointer',
              }}
            >
              Ver planos
            </button>
          </div>
        )}

        {isPaid && (
          <>
            {/* Filtros */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
              <select
                value={filtroTipo}
                onChange={e => setFiltroTipo(e.target.value)}
                style={{ padding: '6px 12px', borderRadius: 8, background: 'var(--surface)',
                         border: '1px solid var(--border)', color: 'var(--text)', fontSize: 13 }}
              >
                {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <select
                value={filtroPar}
                onChange={e => setFiltroPar(e.target.value)}
                style={{ padding: '6px 12px', borderRadius: 8, background: 'var(--surface)',
                         border: '1px solid var(--border)', color: 'var(--text)', fontSize: 13 }}
              >
                {PARES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
              <span style={{ color: 'var(--muted)', fontSize: 12 }}>
                {filtrados.length} sinal{filtrados.length !== 1 ? 'is' : ''}
              </span>
              <span style={{ color: 'var(--muted)', fontSize: 11, marginLeft: 'auto' }}>
                Clique em uma linha para ver análise completa
              </span>
            </div>

            {loading && <div style={{ textAlign: 'center', color: 'var(--muted)', padding: 48 }}>Carregando sinais…</div>}
            {erro    && <div style={{ textAlign: 'center', color: 'var(--danger)', padding: 24 }}>{erro}</div>}

            {!loading && !erro && filtrados.length === 0 && (
              <div style={{ textAlign: 'center', color: 'var(--muted)', padding: 48 }}>
                Nenhum sinal disponível. O agente local precisa estar rodando com o TWS aberto.
              </div>
            )}

            {!loading && filtrados.length > 0 && (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--muted)', textAlign: 'left' }}>
                      <th style={{ padding: '8px 10px' }}>Par</th>
                      <th style={{ padding: '8px 10px' }}>Tipo</th>
                      <th style={{ padding: '8px 10px' }}>Spot</th>
                      <th style={{ padding: '8px 10px' }}>Strike ATM</th>
                      <th style={{ padding: '8px 10px' }}>Strike OTM</th>
                      <th style={{ padding: '8px 10px' }}>IV Média</th>
                      <th style={{ padding: '8px 10px' }}>IV Rank 30d</th>
                      <th style={{ padding: '8px 10px' }}>Tendência</th>
                      <th style={{ padding: '8px 10px' }}>Delta C/P</th>
                      <th style={{ padding: '8px 10px' }}>Custo</th>
                      <th style={{ padding: '8px 10px' }}>Score</th>
                      <th style={{ padding: '8px 10px' }}>Rec.</th>
                      <th style={{ padding: '8px 10px' }}>Venc.</th>
                      <th style={{ padding: '8px 10px' }}>Atualizado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtrados.map(s => {
                      const isExpanded = expandedId === s.id
                      const hasDetail  = s.motivo || s.strikes_recomendados || s.tendencia
                      return (
                        <>
                          <tr
                            key={s.id}
                            onClick={() => hasDetail && setExpandedId(isExpanded ? null : s.id)}
                            style={{
                              borderBottom: isExpanded ? 'none' : '1px solid var(--border)',
                              verticalAlign: 'middle',
                              cursor: hasDetail ? 'pointer' : 'default',
                              background: isExpanded ? 'var(--surface2)' : 'transparent',
                            }}
                          >
                            <td style={{ padding: '10px 10px', fontWeight: 700 }}>
                              {hasDetail && (
                                <span style={{ marginRight: 6, fontSize: 10, color: 'var(--muted)' }}>
                                  {isExpanded ? '▼' : '▶'}
                                </span>
                              )}
                              {s.par}
                            </td>
                            <td style={{ padding: '10px 10px', color: 'var(--muted)', textTransform: 'capitalize' }}>
                              {s.tipo_sinal.replace('_', ' ')}
                            </td>
                            <td style={{ padding: '10px 10px' }}>{fmt(s.spot_price)}</td>
                            <td style={{ padding: '10px 10px' }}>{fmt(s.strike_principal)}</td>
                            <td style={{ padding: '10px 10px' }}>{s.strike_secundario ? fmt(s.strike_secundario) : '—'}</td>
                            <td style={{ padding: '10px 10px' }}>{fmtPct(s.iv_media)}</td>
                            <td style={{ padding: '10px 10px' }}>
                              {s.iv_rank_30d != null
                                ? <span style={{ color: s.iv_rank_30d > 70 ? '#FF4C6A' : s.iv_rank_30d < 30 ? '#00E5A0' : 'var(--text)' }}>
                                    {s.iv_rank_30d.toFixed(1)}
                                  </span>
                                : <span style={{ color: 'var(--muted)', fontSize: 11 }}>acum.</span>
                              }
                            </td>
                            <td style={{ padding: '10px 10px' }}>
                              {s.tendencia ? <TendBadge tend={s.tendencia} /> : <span style={{ color: 'var(--muted)' }}>—</span>}
                            </td>
                            <td style={{ padding: '10px 10px' }}>
                              {fmt(s.delta_call, 3)} / {fmt(s.delta_put, 3)}
                            </td>
                            <td style={{ padding: '10px 10px' }}>{fmt(s.custo_total, 6)}</td>
                            <td style={{ padding: '10px 10px' }}>
                              <div style={{
                                display: 'inline-block', width: 36, height: 6,
                                background: 'var(--surface2)', borderRadius: 3, overflow: 'hidden',
                              }}>
                                <div style={{
                                  height: '100%', borderRadius: 3,
                                  width: `${s.score || 0}%`,
                                  background: s.recomendacao === 'NEUTRAL' ? 'var(--muted)' : 'var(--accent)',
                                }} />
                              </div>
                              <span style={{ marginLeft: 6, fontSize: 11, color: 'var(--muted)' }}>
                                {s.score != null ? s.score.toFixed(0) : '—'}
                              </span>
                            </td>
                            <td style={{ padding: '10px 10px' }}><Badge rec={s.recomendacao} /></td>
                            <td style={{ padding: '10px 10px', fontSize: 11, color: 'var(--muted)' }}>{s.expiracao}</td>
                            <td style={{ padding: '10px 10px', fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                              {fmtDate(s.criado_em)}
                            </td>
                          </tr>
                          {isExpanded && (
                            <ExpandedDetail
                              key={`detail-${s.id}`}
                              s={s}
                              onHistorico={() => setModal({ par: s.par, tipo: s.tipo_sinal })}
                            />
                          )}
                        </>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      {modal && (
        <HistoricoModal par={modal.par} tipo={modal.tipo} onClose={() => setModal(null)} />
      )}
    </Layout>
  )
}
