import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import api    from '../api'

export default function Upload() {
  const navigate      = useNavigate()
  const inputRef      = useRef()
  const [arquivo, setArquivo]   = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [loading, setLoading]   = useState(false)
  const [erro, setErro]         = useState('')
  const [progresso, setProgresso] = useState('')

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
    setProgresso('Lendo o extrato...')

    const form = new FormData()
    form.append('arquivo', arquivo)

    try {
      setProgresso('Buscando PTAX no Banco Central...')
      const { data } = await api.post('/apuracao/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setProgresso(`${data.total} mês(es) processado(s)!`)
      setTimeout(() => navigate('/'), 1200)
    } catch (err) {
      setErro(err.response?.data?.detail || 'Erro ao processar o arquivo.')
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

        {erro && (
          <div style={{ background:'rgba(255,77,109,0.1)', border:'1px solid var(--danger)', color:'var(--danger)', padding:'12px 16px', borderRadius:10, marginTop:16, fontSize:13 }}>
            {erro}
          </div>
        )}

        {progresso && !erro && (
          <div style={{ background:'rgba(0,229,160,0.1)', border:'1px solid var(--accent)', color:'var(--accent)', padding:'12px 16px', borderRadius:10, marginTop:16, fontSize:13, display:'flex', alignItems:'center', gap:10 }}>
            {loading && <span className="spinner" style={{width:14,height:14}} />}
            {progresso}
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
