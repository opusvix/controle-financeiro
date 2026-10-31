# Controle Financeiro

App web local de finanças pessoais da família: contas, cartões, transações,
leitura de cupons fiscais (NFC-e) item a item e controle de preços.

Roda no próprio PC, aberto no navegador. Os dados ficam num arquivo SQLite
local (`data/financeiro.db`), com backup automático diário.

Plano completo: [Plano — App de Controle Financeiro Pessoal](https://claude.ai/artifact/TehtKtZmdPKTB3LqxiQN3d)

## Como rodar (Windows)

1. Copie `.env.example` para `.env` e ajuste se precisar.
2. Dê dois cliques em `scripts\iniciar.bat`.
   Na primeira vez ele instala as dependências (1 a 2 minutos).
3. O navegador abre em `http://127.0.0.1:8000/docs` (as telas chegam na próxima etapa;
   por enquanto essa página permite testar o servidor).

O servidor só escuta no próprio PC (`127.0.0.1`); ninguém da rede acessa os dados.

## Estrutura

```
backend/
  app/
    migrations/   esquema do banco (SQL numerado)
    services/     regras: faturas, transações, painel, backup, NFC-e
    routers/      API: cadastros, movimento, sistema
    seed.py       categorias e instituições iniciais
  tests/          testes automáticos (pytest)
docs/METRICAS.md  fórmula de cada número do app
scripts/          atalhos para Windows
```

## Decisões importantes

- **Dinheiro em centavos inteiros** (R$ 8,98 = 898). Evita erros de arredondamento.
- **Transação + itens**, como nota fiscal num ERP: um cupom vira uma transação
  com itens, cada item com categoria e produto (base do controle de preços).
- **Pagamento de fatura não é despesa**: a despesa é a compra no cartão.
  Pagar a fatura só tira dinheiro da conta. Assim nada conta em dobro.
- **Backup**: guarda o mais recente de cada um dos últimos 7 dias, 4 semanas e
  12 meses, e copia para o Google Drive. O banco em uso nunca fica dentro do Drive.
- **NFC-e**: o QR Code identifica a nota (CNPJ, série, número) e evita lançar
  a mesma nota duas vezes. Os itens serão lidos da imagem pela IA, porque o
  portal da SEFAZ-ES exige captcha.

## Desenvolvimento

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
```
