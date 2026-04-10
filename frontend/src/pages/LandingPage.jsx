import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'

const ANO = new Date().getFullYear()

export default function LandingPage() {
  const navigate = useNavigate()
  const [promo, setPromo] = useState(null)
  const [mobile, setMobile] = useState(window.innerWidth <= 768)

  useEffect(() => {
    api.get('/pagamento/promo').then(r => setPromo(r.data)).catch(() => {})
    const onResize = () => setMobile(window.innerWidth <= 768)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const preco     = promo?.promo_ativa ? promo.preco_brl : 'R$ 69,90'
  const precoBase = 'R$ 69,90'

  return (
    <div style={{ background:'var(--bg)', color:'var(--text)', fontFamily:'DM Sans, sans-serif', overflowX:'hidden' }}>
      {/* NAV */}
      <nav style={{
        position:'sticky', top:0, zIndex:100,
        background:'rgba(10,14,23,0.85)', backdropFilter:'blur(12px)',
        borderBottom:'1px solid var(--border)',
        display:'flex', alignItems:'center', justifyContent:'space-between',
        padding: mobile ? '0 16px' : '0 40px', height:64,
      }}>
        <div style={{ fontFamily:'Syne', fontWeight:800, fontSize:22 }}>
          Darf<span style={{color:'var(--accent)'}}>FX</span>
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          <button className="btn btn-ghost" style={{ padding: mobile ? '6px 12px' : '7px 18px', fontSize:14 }}
            onClick={() => navigate('/login')}>Entrar</button>
          {!mobile && (
            <button className="btn btn-primary" style={{ padding:'7px 18px', fontSize:14 }}
              onClick={() => navigate('/register')}>Começar grátis →</button>
          )}
        </div>
      </nav>

      {/* HERO */}
      <section style={{
        minHeight:'90vh', display:'flex', flexDirection:'column',
        alignItems:'center', justifyContent:'center',
        textAlign:'center', padding: mobile ? '60px 20px 40px' : '80px 24px 60px',
        background:'radial-gradient(ellipse 80% 60% at 50% -20%, rgba(0,229,160,0.12) 0%, transparent 70%)',
      }}>
        {/* Badge */}
        <div style={{
          display:'inline-flex', alignItems:'center', gap:8, marginBottom:24,
          background:'rgba(0,229,160,0.1)', border:'1px solid rgba(0,229,160,0.3)',
          borderRadius:20, padding:'6px 16px', fontSize:13, color:'var(--accent)',
        }}>
          <span style={{ width:7, height:7, borderRadius:'50%', background:'var(--accent)', display:'inline-block' }} />
          Lei 14.754/2023 · Vigente desde jan/2024
        </div>

        <h1 style={{
          fontSize: mobile ? '36px' : 'clamp(36px,6vw,72px)',
          fontFamily:'Syne', fontWeight:800,
          lineHeight:1.1, marginBottom:24, maxWidth:820,
        }}>
          Declare seu IR do Forex{' '}
          <span style={{
            background:'linear-gradient(90deg, var(--accent), #0095ff)',
            WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent',
          }}>
            com precisão
          </span>
          {' '}e sem estresse
        </h1>

        <p style={{
          fontSize: mobile ? '16px' : 'clamp(16px,2vw,20px)',
          color:'var(--muted)', maxWidth:560, lineHeight:1.7, marginBottom:40,
        }}>
          O DarfFX calcula automaticamente seu imposto de renda sobre operações
          de Forex da AvaTrade, aplicando a Lei 14.754/2023 com PTAX oficial do
          Banco Central. Copie o extrato, cole no Excel ou Google Planilhas, salve como CSV e pronto.
        </p>

        <div style={{ display:'flex', gap:12, flexWrap:'wrap', justifyContent:'center', marginBottom:56 }}>
          <button className="btn btn-primary" style={{ padding:'14px 32px', fontSize:16, borderRadius:12 }}
            onClick={() => navigate('/register')}>
            Calcular meu IR agora →
          </button>
          {!mobile && (
            <button className="btn btn-ghost" style={{ padding:'14px 32px', fontSize:16, borderRadius:12 }}
              onClick={() => document.getElementById('como-funciona')?.scrollIntoView({behavior:'smooth'})}>
              Ver como funciona
            </button>
          )}
        </div>

        {/* Stats row */}
        <div style={{ display:'grid', gridTemplateColumns: mobile ? '1fr 1fr' : 'repeat(4,auto)', gap: mobile ? '20px 32px' : 40, justifyContent:'center' }}>
          {[
            ['15%', 'Alíquota fixa flat'],
            ['PTAX', 'Banco Central automático'],
            ['Lei 14.754', 'Compliance total'],
            ['CSV', 'Upload simples via planilha'],
          ].map(([v, l]) => (
            <div key={l} style={{ textAlign:'center' }}>
              <div style={{ fontSize:22, fontFamily:'Syne', fontWeight:800, color:'var(--accent)' }}>{v}</div>
              <div style={{ fontSize:12, color:'var(--muted)', marginTop:2 }}>{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* A LEI MUDOU */}
      <section style={{
        padding: mobile ? '48px 20px' : '80px 24px',
        background:'var(--surface)',
        borderTop:'1px solid var(--border)', borderBottom:'1px solid var(--border)',
      }}>
        <div style={{ maxWidth:900, margin:'0 auto', display:'grid', gridTemplateColumns: mobile ? '1fr' : '1fr 1fr', gap: mobile ? 32 : 48, alignItems:'center' }}>
          <div>
            <div style={{ fontSize:12, color:'var(--warn)', fontWeight:700, letterSpacing:'1px', marginBottom:12 }}>
              ATENÇÃO · NOVA LEGISLAÇÃO
            </div>
            <h2 style={{ fontSize: mobile ? '24px' : 'clamp(24px,4vw,36px)', fontFamily:'Syne', marginBottom:16 }}>
              A Lei 14.754/2023 mudou tudo para traders Forex
            </h2>
            <p style={{ color:'var(--muted)', fontSize:15, lineHeight:1.8, marginBottom:16 }}>
              A partir de <strong style={{color:'var(--text)'}}>janeiro de 2024</strong>, todas as aplicações financeiras
              no exterior — incluindo Forex — passam a ter tributação anual com
              <strong style={{color:'var(--accent)'}}> alíquota fixa de 15%</strong>, sem a isenção de R$20.000.
            </p>
            <p style={{ color:'var(--muted)', fontSize:15, lineHeight:1.8 }}>
              Isso significa que você precisa calcular seu lucro anual em reais usando a
              cotação PTAX do Banco Central, compensar prejuízos de meses anteriores e
              declarar como "Aplicações financeiras no exterior" no IRPF.
            </p>
          </div>
          <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
            {[
              ['❌', 'Antes (até 2023)', 'Tributação mensal com isenção de R$20.000. Alíquota progressiva 15-22,5%.'],
              ['✅', 'Agora (Lei 14.754/2023)', 'Apuração ANUAL. Alíquota fixa 15% sobre lucro líquido. Sem isenção. PTAX obrigatório.'],
            ].map(([icon, titulo, desc]) => (
              <div key={titulo} style={{
                background:'var(--surface2)', borderRadius:12, padding:20,
                border:'1px solid var(--border)',
              }}>
                <div style={{ display:'flex', gap:12, alignItems:'flex-start' }}>
                  <span style={{ fontSize:20 }}>{icon}</span>
                  <div>
                    <div style={{ fontWeight:700, marginBottom:4, fontSize:14 }}>{titulo}</div>
                    <div style={{ color:'var(--muted)', fontSize:13, lineHeight:1.6 }}>{desc}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* COMO FUNCIONA */}
      <section id="como-funciona" style={{ padding: mobile ? '56px 20px' : '90px 24px', maxWidth:1000, margin:'0 auto' }}>
        <div style={{ textAlign:'center', marginBottom:60 }}>
          <div style={{ fontSize:12, color:'var(--accent)', fontWeight:700, letterSpacing:'1px', marginBottom:12 }}>SIMPLES E RÁPIDO</div>
          <h2 style={{ fontSize: mobile ? '24px' : 'clamp(24px,4vw,40px)', fontFamily:'Syne' }}>Como funciona em 3 passos</h2>
        </div>

        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(260px,1fr))', gap:24 }}>
          {[
            {
              num: '01', icon: '📋',
              titulo: 'Copie o extrato da AvaTrade',
              desc: 'Acesse o Account Statement na AvaTrade, selecione tudo com Ctrl+A, copie com Ctrl+C e cole em uma planilha Excel ou Google Planilhas. Salve como CSV.',
            },
            {
              num: '02', icon: '⚡',
              titulo: 'Faça o upload do CSV',
              desc: 'Envie o arquivo CSV para o DarfFX. Em segundos lemos cada operação, buscamos a PTAX oficial do Banco Central e calculamos seu IR seguindo a Lei 14.754/2023.',
            },
            {
              num: '03', icon: '📊',
              titulo: 'Relatório pronto para o IRPF',
              desc: 'Receba o imposto anual (IRPF) e o relatório completo pronto para declarar. Disponível no Acesso Completo.',
            },
          ].map((s) => (
            <div key={s.num} style={{
              background:'var(--surface)', border:'1px solid var(--border)',
              borderRadius:16, padding:28, position:'relative', overflow:'hidden',
            }}>
              <div style={{
                position:'absolute', top:16, right:20,
                fontFamily:'Syne', fontWeight:800, fontSize:48,
                color:'rgba(0,229,160,0.06)', lineHeight:1,
              }}>{s.num}</div>
              <div style={{ fontSize:36, marginBottom:16 }}>{s.icon}</div>
              <h3 style={{ fontSize:17, marginBottom:10 }}>{s.titulo}</h3>
              <p style={{ color:'var(--muted)', fontSize:14, lineHeight:1.7 }}>{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section style={{
        padding: mobile ? '48px 20px' : '80px 24px',
        background:'var(--surface)',
        borderTop:'1px solid var(--border)', borderBottom:'1px solid var(--border)',
      }}>
        <div style={{ maxWidth:1000, margin:'0 auto' }}>
          <div style={{ textAlign:'center', marginBottom:56 }}>
            <div style={{ fontSize:12, color:'var(--accent)', fontWeight:700, letterSpacing:'1px', marginBottom:12 }}>FUNCIONALIDADES</div>
            <h2 style={{ fontSize: mobile ? '24px' : 'clamp(24px,4vw,40px)', fontFamily:'Syne' }}>Tudo que você precisa, em um só lugar</h2>
          </div>

          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(240px,1fr))', gap:20 }}>
            {[
              { icon:'🏦', titulo:'PTAX automático', desc:'Busca a cotação oficial do Banco Central do Brasil para cada mês. Sem preocupação com câmbio manual.' },
              { icon:'⚖️', titulo:'Lei 14.754/2023', desc:'Cálculo 100% aderente à nova legislação: alíquota fixa 15%, apuração anual, sem isenção.' },
              { icon:'📉', titulo:'Compensação de prejuízos', desc:'Prejuízos de meses anteriores são automaticamente descontados da base tributável dentro do mesmo ano.' },
              { icon:'📊', titulo:'Dashboard com gráficos', desc:'Visualize seu P&L mensal em barras, evolução acumulada e a composição do capital (depósitos vs lucro real).', destaque: true },
              { icon:'🎯', titulo:'Insights de trading', desc:'Descubra seu melhor e pior mês, taxa de meses lucrativos e sequência atual de resultados positivos ou negativos.', destaque: true },
              { icon:'📈', titulo:'Rentabilidade mensal e anual', desc:'Veja o percentual de retorno sobre seu capital depositado, mês a mês e no acumulado do ano, com barras visuais por período.', destaque: true },
              { icon:'⏰', titulo:'DARF countdown + lembrete', desc:'Contador regressivo até o vencimento que muda de cor conforme a urgência. Receba e-mails automáticos 30, 7 e 1 dia antes.', destaque: true },
              { icon:'📋', titulo:'Relatório para IRPF', desc:'Relatório completo com todas as informações para preencher sua declaração no programa IRPF. Plano pago.' },
              { icon:'📤', titulo:'Exportar PDF e Excel', desc:'Exporte o relatório em PDF ou planilha Excel colorida para guardar ou enviar ao seu contador. Plano pago.', destaque: true },
            ].map((f) => (
              <div key={f.titulo} style={{
                background:'var(--surface2)', borderRadius:12, padding:24,
                border: f.destaque ? '1px solid rgba(0,229,160,0.35)' : '1px solid var(--border)',
                position:'relative',
                boxShadow: f.destaque ? '0 0 16px rgba(0,229,160,0.06)' : 'none',
              }}>
                {f.destaque && (
                  <div style={{
                    position:'absolute', top:12, right:12,
                    background:'rgba(0,229,160,0.15)', color:'var(--accent)',
                    fontSize:10, fontWeight:700, letterSpacing:'0.8px',
                    padding:'2px 8px', borderRadius:20,
                  }}>NOVO</div>
                )}
                <div style={{ fontSize:32, marginBottom:12 }}>{f.icon}</div>
                <h3 style={{ fontSize:15, marginBottom:8 }}>{f.titulo}</h3>
                <p style={{ color:'var(--muted)', fontSize:13, lineHeight:1.7 }}>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section style={{ padding: mobile ? '56px 20px' : '90px 24px', maxWidth:900, margin:'0 auto' }}>
        <div style={{ textAlign:'center', marginBottom:56 }}>
          <div style={{ fontSize:12, color:'var(--accent)', fontWeight:700, letterSpacing:'1px', marginBottom:12 }}>PREÇOS</div>
          <h2 style={{ fontSize: mobile ? '24px' : 'clamp(24px,4vw,40px)', fontFamily:'Syne' }}>Simples e transparente</h2>
          <p style={{ color:'var(--muted)', marginTop:12, fontSize:15 }}>Comece grátis. Pague apenas quando quiser o relatório completo.</p>
        </div>

        <div style={{ display:'grid', gridTemplateColumns: mobile ? '1fr' : '1fr 1fr', gap:24 }}>
          {/* FREE */}
          <div style={{
            background:'var(--surface)', border:'1px solid var(--border)',
            borderRadius:20, padding:32,
          }}>
            <div style={{ fontSize:13, color:'var(--muted)', fontWeight:700, letterSpacing:'1px', marginBottom:16 }}>GRATUITO</div>
            <div style={{ fontSize:42, fontFamily:'Syne', fontWeight:800, marginBottom:4 }}>R$ 0</div>
            <div style={{ color:'var(--muted)', fontSize:13, marginBottom:28 }}>sempre grátis</div>
            {[
              '✓ Upload do CSV AvaTrade',
              '✓ Até 2 meses de análise',
              '✓ Lucro estimado em USD e BRL',
              '✗ Dashboard com gráficos (bloqueado)',
              '✗ Breakdown mensal detalhado (bloqueado)',
              '✗ Imposto calculado (bloqueado)',
              '✗ Relatório para IRPF (bloqueado)',
            ].map((item) => (
              <div key={item} style={{
                fontSize:14, marginBottom:10,
                color: item.startsWith('✗') ? 'var(--muted)' : 'var(--text)',
                opacity: item.startsWith('✗') ? 0.5 : 1,
              }}>{item}</div>
            ))}
            <button className="btn btn-ghost" style={{ width:'100%', marginTop:24, padding:'12px' }}
              onClick={() => navigate('/register')}>
              Criar conta grátis
            </button>
          </div>

          {/* PAGO */}
          <div style={{
            background:'var(--surface)',
            border: promo?.promo_ativa ? '2px solid var(--warn)' : '2px solid var(--accent)',
            borderRadius:20, padding:32, position:'relative',
            boxShadow: promo?.promo_ativa ? '0 0 40px rgba(255,179,71,0.12)' : '0 0 40px rgba(0,229,160,0.1)',
          }}>
            <div style={{
              position:'absolute', top:-13, left:'50%', transform:'translateX(-50%)',
              background: promo?.promo_ativa ? 'var(--warn)' : 'var(--accent)',
              color:'#000', fontWeight:700, fontSize:11,
              padding:'4px 16px', borderRadius:20, letterSpacing:'0.5px', whiteSpace:'nowrap',
            }}>{promo?.promo_ativa ? '🏷️ OFERTA ESPECIAL' : 'MAIS POPULAR'}</div>
            <div style={{ fontSize:13, color: promo?.promo_ativa ? 'var(--warn)' : 'var(--accent)', fontWeight:700, letterSpacing:'1px', marginBottom:16 }}>ACESSO COMPLETO</div>
            <div style={{ display:'flex', alignItems:'baseline', gap:8, marginBottom:4 }}>
              {promo?.promo_ativa && (
                <span style={{ fontSize:20, color:'var(--muted)', textDecoration:'line-through' }}>{precoBase}</span>
              )}
              <div style={{ fontSize:42, fontFamily:'Syne', fontWeight:800, color: promo?.promo_ativa ? 'var(--warn)' : 'var(--accent)' }}>{preco}</div>
            </div>
            <div style={{ color:'var(--muted)', fontSize:13, marginBottom:28 }}>pagamento único · válido até 31/12/{ANO}</div>
            {[
              { label:'✓ Processamento de meses ilimitados' },
              { label:'✓ Cálculo oficial do imposto (15%)' },
              { label:'✓ Breakdown mensal detalhado' },
              { label:'✓ Compensação de prejuízos' },
              { label:'✓ Dashboard completo com gráficos', novo: true },
              { label:'✓ Insights: melhor mês, taxa de acerto, sequência', novo: true },
              { label:'✓ Rentabilidade mensal e anual', novo: true },
              { label:'✓ DARF countdown com lembretes por e-mail', novo: true },
              { label:'✓ Relatório completo para IRPF' },
              { label:'✓ Exportar PDF e Excel', novo: true },
            ].map((item) => (
              <div key={item.label} style={{ fontSize:14, marginBottom:10, color:'var(--text)', display:'flex', alignItems:'center', gap:8 }}>
                {item.label}
                {item.novo && (
                  <span style={{
                    background:'rgba(0,229,160,0.15)', color:'var(--accent)',
                    fontSize:10, fontWeight:700, letterSpacing:'0.8px',
                    padding:'1px 7px', borderRadius:20, flexShrink:0,
                  }}>NOVO</span>
                )}
              </div>
            ))}
            <button
              className="btn btn-primary"
              style={{
                width:'100%', marginTop:24, padding:'12px', fontSize:15,
                background: promo?.promo_ativa ? 'var(--warn)' : undefined,
                color: promo?.promo_ativa ? '#000' : undefined,
              }}
              onClick={() => navigate('/register')}>
              Começar agora →
            </button>
          </div>
        </div>
      </section>

      {/* CTA FINAL */}
      <section style={{
        padding: mobile ? '56px 20px' : '80px 24px',
        background:'linear-gradient(135deg, rgba(0,229,160,0.08) 0%, rgba(0,149,255,0.06) 100%)',
        borderTop:'1px solid var(--border)', textAlign:'center',
      }}>
        <h2 style={{ fontSize: mobile ? '28px' : 'clamp(28px,5vw,48px)', fontFamily:'Syne', marginBottom:16, maxWidth:600, margin:'0 auto 16px' }}>
          Pronto para regularizar seu IR do Forex?
        </h2>
        <p style={{ color:'var(--muted)', fontSize:16, marginBottom:36, maxWidth:480, margin:'0 auto 36px' }}>
          Crie sua conta grátis, faça o upload do CSV e veja seu resultado em segundos.
          Sem cartão de crédito para começar.
        </p>
        <button className="btn btn-primary" style={{ padding:'16px 40px', fontSize:17, borderRadius:14 }}
          onClick={() => navigate('/register')}>
          Criar conta grátis →
        </button>
        <p style={{ color:'var(--muted)', fontSize:12, marginTop:16 }}>
          Sem compromisso · Cancele quando quiser
        </p>
      </section>

      {/* FOOTER */}
      <footer style={{
        padding: mobile ? '24px 20px' : '32px 40px',
        borderTop:'1px solid var(--border)',
        display:'flex', justifyContent:'space-between', alignItems:'center',
        flexWrap:'wrap', gap:12,
      }}>
        <div style={{ fontFamily:'Syne', fontWeight:800, fontSize:18 }}>
          Darf<span style={{color:'var(--accent)'}}>FX</span>
          <span style={{ fontFamily:'DM Sans', fontWeight:400, fontSize:13, color:'var(--muted)', marginLeft:12 }}>
            IR Forex · Lei 14.754/2023
          </span>
        </div>
        <div style={{ fontSize:12, color:'var(--muted)' }}>
          © {ANO} DarfFX · Pagamentos via Stripe · Cotação PTAX · Banco Central do Brasil
        </div>
      </footer>
    </div>
  )
}
