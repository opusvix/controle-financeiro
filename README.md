# Controle Financeiro

App de **finanças pessoais da família**: contas, cartões de crédito, transações,
leitura de cupons fiscais (NFC-e) item a item e controle de preços — tudo rodando
no seu próprio computador, com os dados num arquivo local.

Pode ser usado de duas formas:

- **Aplicativo (`.exe`)** — uma janela própria do Windows, sem navegador. É assim que
  o usuário final usa.
- **App web local** — o mesmo app aberto no navegador em `http://127.0.0.1:8000/`,
  útil durante o desenvolvimento.

> 📘 **Como usar o app:** veja o [Guia de Uso](docs/GUIA.md) (o mesmo também aparece
> dentro do app, no menu **Ajuda**).
> 🧮 **De onde vem cada número:** [docs/METRICAS.md](docs/METRICAS.md).
> 🧾 **Cupons fiscais:** [docs/CUPONS.md](docs/CUPONS.md).

---

## Para quem só quer usar (Windows)

1. Baixe o arquivo **`ControleFinanceiro.exe`** (pelo link recebido ou pela página de
   divulgação).
2. Coloque numa pasta sua, por exemplo `Documentos\ControleFinanceiro`.
3. Dê **dois cliques**. Abre uma janela própria do programa. A primeira abertura cria
   as pastas `data` (banco) e `BackUp` ao lado do `.exe`.

Requisito: **Windows 10 ou 11** atualizado (já trazem o WebView2 da Microsoft). O
servidor só escuta no próprio PC (`127.0.0.1`); ninguém da rede acessa os dados.
Passo a passo completo no [Guia de Uso](docs/GUIA.md#1-baixar-instalar-e-abrir).

---

## Para quem desenvolve

### Rodar como app web local

1. Copie `backend/.env.example` para `backend/.env` e ajuste se precisar.
2. Dê dois cliques em `scripts\iniciar.bat` (na primeira vez instala as dependências,
   1 a 2 minutos) e abra `http://127.0.0.1:8000/`.
3. Opcional: `scripts\criar_atalho.bat` cria o atalho **Controle Financeiro** na Área de
   Trabalho (abre escondido, sem janela preta). **O atalho se atualiza sozinho:** ao abrir,
   verifica se há versão nova no GitHub e, se houver, baixa e recompila antes de abrir — mesmo
   que o app já esteja aberto (ele fecha, atualiza e reabre). Quando já está em dia, abre na hora.
4. Para desligar: `scripts\parar.bat`. Para atualizar na mão (sem abrir), ainda há o
   `scripts\atualizar.bat`, que desliga sozinho antes de atualizar.

### Gerar o aplicativo (`.exe`)

`scripts\gerar_exe.bat` faz tudo sozinho (prepara o Python, instala as bibliotecas,
compila as telas e empacota com o PyInstaller). Ao final, o programa fica em
`dist\ControleFinanceiro.exe`. Esse passo é feito **uma vez por quem publica** — o
usuário final só recebe o `.exe` pronto.

### Rodar os testes

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
```

---

## Como funciona por dentro

```
backend/
  app/
    migrations/   esquema do banco (SQL numerado, 001…013)
    services/     regras: faturas, transações, painel, backup, NFC-e, energia…
    routers/      API: cadastros, movimento, sistema
    seed.py       categorias e instituições iniciais
    seed_demo.py  dados fictícios do modo demonstração
    desktop.py    abre o app numa janela nativa (PyWebView)
  tests/          testes automáticos (pytest)
frontend/
  src/telas/      uma tela por arquivo (Dashboard, Contas, Transações, Ajuda…)
  src/api.ts      cliente da API
docs/             GUIA.md (uso), METRICAS.md (fórmulas), CUPONS.md (NFC-e)
scripts/          atalhos .bat/.vbs para Windows
controle-financeiro.spec   receita do PyInstaller (gera o .exe)
```

**Tecnologias:** backend FastAPI + SQLite (migrações SQL numeradas); frontend React +
Vite + TypeScript; empacotamento com PyWebView + PyInstaller.

### Decisões importantes

- **Dinheiro em centavos inteiros** (R$ 8,98 = 898). Evita erros de arredondamento.
- **Transação + itens**, como nota fiscal num ERP: um cupom vira uma transação com
  itens, cada item com categoria e produto (base do controle de preços).
- **Pagamento de fatura não é despesa**: a despesa é a compra no cartão. Pagar a fatura
  só tira dinheiro da conta — assim nada conta em dobro.
- **Saldo é calculado**, nunca digitado: saldo inicial + lançamentos pagos.
- **Backup**: guarda o mais recente de cada um dos últimos 7 dias, 4 semanas e 12 meses,
  e copia para o Google Drive. O banco em uso nunca fica dentro do Drive.
- **NFC-e**: o QR Code identifica a nota (CNPJ, série, número) e evita lançar a mesma
  nota duas vezes.

### Modo demonstração

Serve para mostrar o app sem expor dados reais. Ligue com a variável de ambiente
`CF_MODO_DEMO=1` (ou use `scripts\demonstracao.bat`). Nesse modo o app:

- usa um banco **separado** (`financeiro_demo.db`), **nunca** o real;
- semeia dados de uma família fictícia (contas, cartões, faturas, ~3 meses, cupons);
- mostra o selo **Demonstração** e o botão **Reiniciar demonstração** no menu;
- não faz backup e **não** tem cadeado de tempo.

---

## Privacidade

Todos os dados ficam no seu computador, no arquivo `data/financeiro.db`. O app não envia
nada para a internet por conta própria. O arquivo `.env` (com eventuais chaves) nunca vai
para o repositório.
