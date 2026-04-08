import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import api from '../api'

const MSGS_PROGRESSO = [
  '☕ Pegue um café enquanto processamos tudo...',
  '📄 Lendo as operações do extrato...',
  '🏦 Buscando cotações PTAX no Banco Central...',
  '📊 Calculando resultado mensal...',
  '🧮 Aplicando Lei 14.754/2023 (alíquota 15%)...',
  '📈 Verificando carry forward de prejuízos...',
  '✅ Quase lá, finalizando...',
]

export default function Upload() {
  const navigate      = useNavigate()
  const inputRef      = useRef()
  const [arquivo, setArquivo]   = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [loading,    setLoading]   = useState(false)
  const [erro,       setErro]      = useState('')
  const [progresso,  setProgresso] = useState('')
  const [planLimit,  setPlanLimit] = useState(false)
  const [msgIdx,     setMsgIdx]    = useState(0)
  const [elapsed,    setElapsed]   = useState(0)
  const [promo,      setPromo]     = useState(null)

  useEffect(() => {
    api.get('/pagamento/promo').then(r => setPromo(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!loading) { setMsgIdx(0); setElapsed(0); return }
    const msgTimer = setInterval(() => setMsgIdx(i => (i + 1) % MSGS_PROGRESSO.length), 4000)
    const secTimer = setInterval(() => setElapsed(s => s + 1), 1000)
    return () => { clearInterval(msgTimer); clearInterval(secTimer) }
  }, [loading])

  const handleFile = (file) => {
    if (!file?.name.toLowerCase().endsWith('.pdf')) {
      setErro('Por favor envie um arquivo PDF.')
      return
    }
    setErro('')
    setArquivo(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    handleFile(e.dataTransfer.files[0])
  }

  const handleUpload = async () => {
    if (!arquivo) return
    setLoading(true)
    setErro('')
    setProgresso('')
    setPlanLimit(false)

    const form = new FormData()
    form.append('arquivo', arquivo)

    try {
      const { data } = await api.post('/apuracao/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      if (data.meses_limitados) {
        setProgresso(`✅ ${data.total} mês(es) processado(s). Plano gratuito: máximo 2 meses — desbloqueie para ver todos.`)
        setPlanLimit(true)
      } else {
        setProgresso(`✅ ${data.total} mês(es) processado(s)! Redirecionando...`)
        setTimeout(() => navigate('/'), 1500)
      }
    } catch (err) {
      const detail = err.response?.data?.detail || ''
      if (detail.startsWith('PLAN_LIMIT')) {
        setPlanLimit(true)
      } else {
        setErro(detail || 'Erro ao processar o arquivo.')
      }
      setProgresso('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div style={{ maxWidth:600, margin:'0 auto' }}>
        <h1 style={{ fontSize:24, marginBottom:8 }}>Novo Extrato</h1>
        <p style={{ color:'var(--muted)', marginBottom:32 }}>
          Faça o upload do PDF exportado da AvaTrade. O sistema calcula o IR de cada mês automaticamente.
        </p>

        {/* UPLOAD ZONE */}
        <div
          className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            style={{ display:'none' }}
            onChange={e => handleFile(e.target.files[0])}
          />

          {arquivo ? (
            <>
              <div style={{ fontSize:40, marginBottom:12 }}>📄</div>
              <div style={{ fontWeight:600, marginBottom:4 }}>{arquivo.name}</div>
              <div style={{ color:'var(--muted)', fontSize:13 }}>
                {(arquivo.size / 1024).toFixed(0)} KB — clique para trocar
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize:40, marginBottom:12 }}>☁</div>
              <div style={{ fontWeight:600, marginBottom:8 }}>
                Arraste o PDF aqui ou clique para selecionar
              </div>
              <div style={{ color:'var(--muted)', fontSize:13 }}>
                Extrato da AvaTrade (Account Statement PDF)
              </div>
            </>
          )}
        </div>

        {/* COMO EXPORTAR */}
        <div className="card" style={{ marginTop:20, fontSize:13 }}>
          <div style={{ fontWeight:600, marginBottom:10 }}>Como exportar o extrato da AvaTrade:</div>
          <ol style={{ paddingLeft:20, display:'flex', flexDirection:'column', gap:6, color:'var(--muted)' }}>
            <li>Acesse <strong style={{color:'var(--text)'}}>avaoptions.avatrade.com</strong></li>
            <li>Vá em <strong style={{color:'var(--text)'}}>Relatórios → Account Statement</strong></li>
            <li>Selecione o período desejado</li>
            <li>Clique em <strong style={{color:'var(--text)'}}>Exportar PDF</strong></li>
          </ol>
        </div>

        {planLimit && (() => {
          const promoAtiva = promo?.promo_ativa
          const preco = promoAtiva ? promo.preco_brl : 'R$ 69,90'
          const cor   = promoAtiva ? 'var(--warn)' : 'var(--accent)'
          return (
            <div style={{
              background: promoAtiva
                ? 'linear-gradient(135deg,rgba(255,179,71,0.06),rgba(255,120,0,0.04))'
                : 'linear-gradient(135deg,rgba(0,229,160,0.06),rgba(0,149,255,0.06))',
              border:`2px solid ${cor}`, borderRadius:16, padding:24, marginTop:16, textAlign:'center'
            }}>
              {promoAtiva && (
                <div style={{
                  display:'inline-flex', alignItems:'center', gap:6, marginBottom:10,
                  background:'rgba(255,179,71,0.15)', border:'1px solid rgba(255,179,71,0.4)',
                  borderRadius:20, padding:'3px 12px', fontSize:11, fontWeight:700, color:'var(--warn)',
                }}>
                  🏷️ OFERTA ESPECIAL · TEMPO LIMITADO
                </div>
              )}
              <div style={{ fontSize:32, marginBottom:8 }}>🚀</div>
              <h3 style={{ fontSize:17, marginBottom:8, fontFamily:'Syne' }}>
                Desbloqueie o Acesso Completo
              </h3>
              <p style={{ color:'var(--muted)', fontSize:14, marginBottom:16, maxWidth:380, margin:'0 auto 16px' }}>
                Com o{' '}
                <strong style={{color:cor}}>Acesso Completo por {preco}</strong>
                {promoAtiva && <span style={{color:'var(--muted)',fontSize:12,marginLeft:4,textDecoration:'line-through'}}>R$ 69,90</span>}
                {' '}você processa meses ilimitados, vê o imposto exato e exporta o relatório para o IRPF.
                Válido até <strong style={{color:cor}}>31/12/{new Date().getFullYear()}</strong>.
              </p>
              <button
                className="btn btn-primary"
                style={{ padding:'12px 28px', fontSize:15, borderRadius:12, background: promoAtiva ? 'var(--warn)' : undefined, color: promoAtiva ? '#000' : undefined }}
                onClick={() => navigate('/upgrade')}>
                Desbloquear Acesso Completo →
              </button>
              <p style={{ fontSize:11, color:'var(--muted)', marginTop:10 }}>
                Pagamento único · Stripe · Acesso imediato
              </p>
            </div>
          )
        })()}

        {erro && (
          <div style={{ background:'rgba(255,77,109,0.1)', border:'1px solid var(--danger)', color:'var(--danger)', padding:'12px 16px', borderRadius:10, marginTop:16, fontSize:13 }}>
            {erro}
          </div>
        )}

        {loading && (
          <div style={{ background:'rgba(0,229,160,0.07)', border:'1px solid var(--accent)', borderRadius:12, marginTop:16, padding:'16px 20px' }}>
            <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:10 }}>
              <span className="spinner" style={{width:14,height:14,flexShrink:0}} />
              <span style={{ color:'var(--accent)', fontSize:14, fontWeight:500 }}>
                {MSGS_PROGRESSO[msgIdx]}
              </span>
            </div>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
              <div style={{ flex:1, height:4, background:'var(--surface2)', borderRadius:4, marginRight:12, overflow:'hidden' }}>
                <div style={{
                  height:'100%', borderRadius:4, background:'var(--accent)',
                  width: `${Math.min(95, (elapsed / 180) * 100)}%`,
                  transition:'width 1s linear',
                }} />
              </div>
              <span style={{ fontSize:11, color:'var(--muted)', whiteSpace:'nowrap' }}>
                {elapsed < 60 ? `${elapsed}s` : `${Math.floor(elapsed/60)}m${elapsed%60}s`}
                {' · '}{arquivo
                  ? arquivo.size > 3_000_000 ? '~3-4 min' : arquivo.size > 1_500_000 ? '~2-3 min' : '~1-2 min'
                  : '~2-3 min'}
              </span>
            </div>
          </div>
        )}
        {progresso && !loading && !erro && (
          <div style={{ background:'rgba(0,229,160,0.1)', border:'1px solid var(--accent)', color:'var(--accent)', padding:'12px 16px', borderRadius:10, marginTop:16, fontSize:13 }}>
            {progresso}
            {planLimit && (
              <span>
                {' '}ou{' '}
                <button
                  onClick={() => navigate('/')}
                  style={{ background:'none', border:'none', color:'var(--accent)', fontWeight:600, cursor:'pointer', textDecoration:'underline', padding:0, fontSize:'inherit' }}
                >
                  verifique sua apuração no Dashboard
                </button>.
              </span>
            )}
          </div>
        )}

        <div style={{ display:'flex', gap:12, marginTop:24 }}>
          <button className="btn btn-ghost" onClick={() => navigate('/')} disabled={loading}>
            Cancelar
          </button>
          <button
            className="btn btn-primary"
            style={{ flex:1 }}
            onClick={handleUpload}
            disabled={!arquivo || loading}
          >
            {loading ? <><span className="spinner" /> Processando...</> : 'Calcular IR →'}
          </button>
        </div>
      </div>
    </Layout>
  )
}
