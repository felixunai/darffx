# DarfFX — IR no Forex simplificado

Micro SaaS para traders brasileiros calcularem automaticamente o IR sobre operações Forex na AvaTrade.

---

## Stack

| Camada    | Tecnologia                    | Hospedagem     |
|-----------|-------------------------------|----------------|
| Backend   | Python 3.12 + FastAPI         | Railway (free) |
| Frontend  | React 18 + Vite               | Vercel (free)  |
| Banco     | PostgreSQL                    | Railway (free) |
| OCR       | Tesseract + PyMuPDF           | (no backend)   |
| PTAX      | API oficial Banco Central     | —              |
| Relatório | ReportLab (PDF)               | —              |
| Auth      | JWT + bcrypt                  | —              |

---

## Rodar localmente

### Pré-requisitos

**Backend:**
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-eng

# macOS
brew install tesseract
```

**Python:**
```bash
cd darffx
python -m venv venv
source venv/bin/activate       # Linux/Mac
# venv\Scripts\activate        # Windows

pip install -r backend/requirements.txt

cp .env.example .env
# edite .env com suas credenciais

uvicorn backend.main:app --reload --port 8000
```

Docs: http://localhost:8000/docs

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

---

## Deploy Railway (Backend + Banco)

1. Crie conta em **railway.app**
2. **New Project → Deploy from GitHub**
3. No projeto, adicione **PostgreSQL** como serviço separado
4. No serviço do backend, configure as variáveis de ambiente:
   ```
   DATABASE_URL=<copiado do PostgreSQL no Railway>
   SECRET_KEY=<string aleatória de 32+ chars>
   FRONTEND_URL=https://darffx.vercel.app
   ```
5. O Railway detecta o `Dockerfile` automaticamente — inclui Tesseract
6. Copie a URL pública gerada (ex: `https://darffx-api.up.railway.app`)

---

## Deploy Vercel (Frontend)

1. Crie conta em **vercel.com**
2. **Add New Project → Import Git Repository**
3. Selecione a pasta `frontend` como root directory
4. Framework preset: **Vite**
5. Configure a variável:
   ```
   VITE_API_URL=https://darffx-api.up.railway.app
   ```
6. Deploy

---

## Fluxo do sistema

```
1. Usuário se cadastra / faz login
2. Exporta extrato PDF da AvaTrade (Account Statement)
3. Faz upload no DarfFX
4. Backend:
   a. Rasteriza cada página do PDF com PyMuPDF (200 DPI)
   b. Aplica OCR com Tesseract
   c. Classifica palavras por posição X → reconstrói colunas
   d. Extrai operações CLOSED por mês/ano
   e. Busca PTAX da API do Banco Central (último dia útil do mês)
   f. Calcula ganho líquido em BRL
   g. Aplica alíquota: 15% normal / 20% day trade
   h. Salva no PostgreSQL
5. Usuário vê dashboard com histórico e gráfico
6. Baixa relatório PDF com valor exato do DARF (código 8523)
7. Paga no banco e marca como pago no sistema
```

---

## Regras tributárias implementadas

| Regra | Detalhe |
|-------|---------|
| Vigência | Janeiro/2024 em diante |
| Isenção | Não existe para Forex |
| Alíquota normal | 15% sobre ganho líquido mensal |
| Alíquota day trade | 20% quando há ops abertas e fechadas no mesmo dia |
| Conversão | PTAX de venda do último dia útil do mês (BCB) |
| Código DARF | 8523 |
| Vencimento | Último dia útil do mês seguinte |

---

## Estrutura do projeto

```
darffx/
├── backend/
│   ├── main.py                  # FastAPI app + CORS
│   ├── config.py                # Variáveis de ambiente
│   ├── deps.py                  # DB session, JWT auth
│   ├── models/
│   │   └── database.py          # SQLAlchemy: User, Apuracao, Operacao
│   ├── routers/
│   │   ├── auth.py              # POST /auth/register, /login; GET /me
│   │   └── apuracao.py          # POST /upload; GET /; GET /{id}; GET /{id}/pdf
│   └── services/
│       ├── parser_avatrade.py   # OCR do PDF → lista de Operacao
│       ├── calculo_ir.py        # PTAX BCB + cálculo IR mensal
│       └── gerador_pdf.py       # Relatório PDF com DARF
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Rotas protegidas
│   │   ├── api.js               # Axios com interceptors de token
│   │   ├── context/
│   │   │   └── AuthContext.jsx  # Login, register, logout global
│   │   ├── components/
│   │   │   └── Layout.jsx       # Sidebar + main layout
│   │   └── pages/
│   │       ├── Login.jsx
│   │       ├── Register.jsx
│   │       ├── Dashboard.jsx    # Histórico + gráfico recharts
│   │       ├── Upload.jsx       # Drag & drop do PDF
│   │       └── Apuracao.jsx     # Detalhe + download PDF
│   ├── vite.config.js
│   └── package.json
├── Dockerfile                   # Com Tesseract OCR
├── .env.example
└── README.md
```
