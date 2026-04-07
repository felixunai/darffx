import { useState, useEffect } from 'react'
import Layout from '../components/Layout'
import api from '../api'

const PLANOS = ['free', 'pago', 'admin']
const COR_PLANO = { free:'var(--muted)', pago:'var(--accent)', admin:'var(--warn)' }

export default function Admin() {
  const [stats,    setStats]    = useState(null)
  const [users,    setUsers]    = useState([])
  const [loading,  setLoading]  = useState(true)
  const [salvando, setSalvando] = useState(null)
  const [busca,    setBusca]    = useState('')
  const [promo,    setPromo]    = useState(null)
  const [promoPreco, setPromoPreco] = useState('')
  const [salvandoPromo, setSalvandoPromo] = useState(false)

  useEffect(() => {
    Promise.all([
      api.get('/admin/stats'),
      api.get('/admin/users'),
      api.get('/admin/config/promo'),
    ])
      .then(([s, u, p]) => {
        setStats(s.data)
        setUsers(u.data)
        setPromo(p.data)
        setPromoPreco((p.data.preco_centavos / 100).toFixed(2).replace('.', ','))
      })
      .catch(e => alert('Erro ao carregar dados: ' + (e.response?.data?.detail || e.message)))
      .finally(() => setLoading(false))
  }, [])

  const salvarPromo = async (novoAtivo) => {
    setSalvandoPromo(true)
    try {
      const centavos = Math.round(parseFloat(promoPreco.replace(',', '.')) * 100)
      if (isNaN(centavos) || centavos < 100) { alert('Valor inválido.'); return }
      const { data } = await api.patch('/admin/config/promo', {
        ativo: novoAtivo ?? promo.ativo,
        preco_centavos: centavos,
      })
      setPromo(data)
    } catch(e) {
      alert('Erro: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvandoPromo(false)
    }
  }

  const alterarPlano = async (userId, plano) => {
    setSalvando(userId)
    try {
      const { data } = await api.patch(`/admin/users/${userId}/plano`, { plano })
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, ...data } : u))
    } catch(e) {
      alert('Erro: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(null) }
  }

  const toggleAtivo = async (user) => {
    setSalvando(user.id)
    try {
      const { data } = await api.patch(`/admin/users/${user.id}/ativo`, { ativo: !user.ativo })
      setUsers(prev => prev.map(u => u.id === user.id ? { ...u, ...data } : u))
    } catch(e) {
      alert('Erro: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(null) }
  }

  const deletarUser = async (user) => {
    if (!window.confirm(`Excluir permanentemente ${user.email}? Isso removerá todos os dados.`)) return
    setSalvando(user.id)
    try {
      await api.delete(`/admin/users/${user.id}`)
      setUsers(prev => prev.filter(u => u.id !== user.id))
    } catch(e) {
      alert('Erro: ' + (e.response?.data?.detail || e.message))
    } finally {
      setSalvando(null) }
  }

  const fmtData = (iso) => iso ? new Date(iso).toLocaleDateString('pt-BR') : '—'

  const usersFiltrados = users.filter(u =>
    !busca || u.email.toLowerCase().includes(busca.toLowerCase()) ||
    (u.nome || '').toLowerCase().includes(busca.toLowerCase())
  )

  return (
    <Layout>
      <div style={{ marginBottom:32 }}>
        <h1 style={{ fontSize:24, marginBottom:4 }}>Painel Admin</h1>
        <p style={{ color:'var(--muted)', fontSize:14 }}>Gerenciamento de usuários e planos</p>
      </div>

      {loading ? (
        <div style={{ textAlign:'center', padding:80 }}><span className="spinner" style={{width:32,height:32}} /></div>
      ) : (
        <>
          {/* STATS */}
          {stats && (
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(160px,1fr))', gap:16, marginBottom:32 }}>
              <StatCard label="Total usuários" valor={stats.total_users} />
              <StatCard label="Total apurações" valor={stats.total_apuracoes} />
              {Object.entries(stats.por_plano || {}).map(([plano, count]) => (
                <StatCard key={plano} label={`Plano ${plano}`} valor={count} cor={COR_PLANO[plano]} />
              ))}
            </div>
          )}

          {/* BUSCA */}
          <div className="card" style={{ marginBottom:24 }}>
            <input
              type="text"
              placeholder="Buscar por e-mail ou nome..."
              value={busca}
              onChange={e => setBusca(e.target.value)}
              style={{
                width:'100%', background:'var(--surface2)', border:'1px solid var(--border)',
                borderRadius:8, padding:'10px 14px', color:'var(--text)', fontSize:14, boxSizing:'border-box'
              }}
            />
          </div>

          {/* TABELA USUÁRIOS */}
          <div className="card" style={{ overflowX:'auto' }}>
            <h3 style={{ marginBottom:20, fontSize:15 }}>
              Usuários ({usersFiltrados.length})
            </h3>
            <table className="tabela" style={{ minWidth:900 }}>
              <thead>
                <tr>
                  <th>E-mail / Nome</th>
                  <th>Plano</th>
                  <th>Expira em</th>
                  <th>Apurações</th>
                  <th>Cadastro</th>
                  <th>Status</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {usersFiltrados.map(u => (
                  <tr key={u.id} style={{ opacity: u.ativo ? 1 : 0.5 }}>
                    <td>
                      <div style={{ fontWeight:600, fontSize:13 }}>{u.email}</div>
                      {u.nome && <div style={{ fontSize:11, color:'var(--muted)' }}>{u.nome}</div>}
                    </td>
                    <td>
                      <span style={{ color: COR_PLANO[u.plano] || 'var(--muted)', fontWeight:600, fontSize:13 }}>
                        {u.plano?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ fontSize:12, color:'var(--muted)' }}>
                      {u.plano_expiracao
                        ? <span style={{ color: new Date(u.plano_expiracao) < new Date() ? 'var(--danger)' : 'var(--text)' }}>
                            {fmtData(u.plano_expiracao)}
                          </span>
                        : '—'}
                    </td>
                    <td style={{ textAlign:'center' }}>{u.apuracoes_count}</td>
                    <td style={{ fontSize:12, color:'var(--muted)' }}>{fmtData(u.created_at)}</td>
                    <td>
                      <span className={`badge ${u.ativo ? 'badge-green' : 'badge-red'}`}>
                        {u.ativo ? 'Ativo' : 'Inativo'}
                      </span>
                    </td>
                    <td>
                      {salvando === u.id ? (
                        <span className="spinner" style={{width:14,height:14}} />
                      ) : (
                        <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
                          {PLANOS.filter(p => p !== u.plano).map(p => (
                            <button key={p}
                              className="btn btn-ghost"
                              style={{ padding:'4px 10px', fontSize:11, color: COR_PLANO[p] }}
                              onClick={() => alterarPlano(u.id, p)}>
                              → {p}
                            </button>
                          ))}
                          <button
                            className="btn btn-ghost"
                            style={{ padding:'4px 10px', fontSize:11 }}
                            onClick={() => toggleAtivo(u)}>
                            {u.ativo ? 'Desativar' : 'Ativar'}
                          </button>
                          <button
                            className="btn btn-ghost"
                            style={{ padding:'4px 10px', fontSize:11, color:'var(--danger)', borderColor:'var(--danger)' }}
                            onClick={() => deletarUser(u)}>
                            Excluir
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* LEGENDA PLANOS */}
          <div className="card" style={{ marginTop:24 }}>
            <h3 style={{ fontSize:14, marginBottom:16 }}>Planos disponíveis</h3>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))', gap:16 }}>
              <PlanoCard nome="Gratuito" preco="R$ 0" desc="1 upload · lucro estimado · imposto bloqueado" cor={COR_PLANO.free} />
              <PlanoCard nome="Pago" preco="R$ 69,90" desc="Acesso completo · expira 31/12 do ano vigente" cor={COR_PLANO.pago} />
              <PlanoCard nome="Admin" preco="Interno" desc="Acesso total · sem restrições · sem expiração" cor={COR_PLANO.admin} />
            </div>
          </div>

          {/* PLANO PROMOCIONAL */}
          {promo !== null && (
            <div className="card" style={{
              marginTop:24,
              border: promo.ativo ? '2px solid rgba(255,179,71,0.5)' : '1px solid var(--border)',
            }}>
              <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:20, flexWrap:'wrap', gap:12 }}>
                <div>
                  <h3 style={{ fontSize:15, marginBottom:4 }}>🏷️ Plano Promocional</h3>
                  <p style={{ fontSize:13, color:'var(--muted)' }}>
                    Mesmo acesso do plano pago com preço especial.
                    Quando ativo, aparece na página de upgrade para todos os usuários.
                  </p>
                </div>
                <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                  <span style={{
                    fontSize:12, padding:'3px 10px', borderRadius:20, fontWeight:700,
                    background: promo.ativo ? 'rgba(255,179,71,0.15)' : 'var(--surface2)',
                    color: promo.ativo ? 'var(--warn)' : 'var(--muted)',
                    border: `1px solid ${promo.ativo ? 'rgba(255,179,71,0.4)' : 'var(--border)'}`,
                  }}>
                    {promo.ativo ? '● ATIVO' : '○ INATIVO'}
                  </span>
                </div>
              </div>

              <div style={{ display:'flex', alignItems:'flex-end', gap:12, flexWrap:'wrap' }}>
                <div>
                  <label style={{ fontSize:12, color:'var(--muted)', display:'block', marginBottom:6 }}>
                    PREÇO PROMOCIONAL (R$)
                  </label>
                  <input
                    type="text"
                    value={promoPreco}
                    onChange={e => setPromoPreco(e.target.value)}
                    placeholder="39,90"
                    style={{
                      background:'var(--surface2)', border:'1px solid var(--border)',
                      borderRadius:8, padding:'8px 14px', color:'var(--text)',
                      fontSize:16, fontWeight:700, width:120,
                    }}
                  />
                </div>
                <div style={{ display:'flex', gap:8 }}>
                  <button
                    className="btn btn-ghost"
                    style={{ padding:'8px 18px', fontSize:13 }}
                    onClick={() => salvarPromo(promo.ativo)}
                    disabled={salvandoPromo}
                  >
                    {salvandoPromo ? <span className="spinner" style={{width:12,height:12}} /> : 'Salvar valor'}
                  </button>
                  {promo.ativo ? (
                    <button
                      className="btn btn-ghost"
                      style={{ padding:'8px 18px', fontSize:13, color:'var(--danger)', borderColor:'var(--danger)' }}
                      onClick={() => salvarPromo(false)}
                      disabled={salvandoPromo}
                    >
                      Desativar promo
                    </button>
                  ) : (
                    <button
                      className="btn btn-primary"
                      style={{ padding:'8px 18px', fontSize:13, background:'var(--warn)', borderColor:'var(--warn)', color:'#000' }}
                      onClick={() => salvarPromo(true)}
                      disabled={salvandoPromo}
                    >
                      Ativar promo
                    </button>
                  )}
                </div>
              </div>

              {promo.ativo && (
                <div style={{ marginTop:14, padding:'10px 14px', background:'rgba(255,179,71,0.08)', borderRadius:8, fontSize:13, color:'var(--warn)' }}>
                  ⚠️ Promoção ativa — todos os novos clientes verão <strong>{promo.preco_brl}</strong> na página de upgrade.
                </div>
              )}
            </div>
          )}
        </>
      )}
    </Layout>
  )
}

function StatCard({ label, valor, cor }) {
  return (
    <div className="card" style={{ textAlign:'center' }}>
      <div style={{ fontSize:11, color:'var(--muted)', marginBottom:8, textTransform:'uppercase' }}>{label}</div>
      <div style={{ fontSize:28, fontWeight:800, fontFamily:'Syne', color: cor || 'var(--text)' }}>{valor}</div>
    </div>
  )
}

function PlanoCard({ nome, preco, desc, cor }) {
  return (
    <div style={{ padding:16, border:`1px solid ${cor}40`, borderRadius:12, background:`${cor}08` }}>
      <div style={{ fontWeight:700, color: cor, marginBottom:4 }}>{nome}</div>
      <div style={{ fontSize:18, fontWeight:800, marginBottom:4 }}>{preco}</div>
      <div style={{ fontSize:12, color:'var(--muted)' }}>{desc}</div>
    </div>
  )
}
