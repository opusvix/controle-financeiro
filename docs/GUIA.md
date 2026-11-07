# Guia de Uso — Controle Financeiro

Guia passo a passo para usar o Controle Financeiro. A mesma informação está
dentro do app, no menu **Ajuda**.

- [1. Baixar, instalar e abrir](#1-baixar-instalar-e-abrir)
- [2. Como o app organiza o dinheiro](#2-como-o-app-organiza-o-dinheiro)
- [3. Contas e saldos](#3-contas-e-saldos)
- [4. Lançar transações e parcelas](#4-lançar-transações-e-parcelas)
- [5. Cartões de crédito e faturas](#5-cartões-de-crédito-e-faturas)
- [6. Cupons fiscais e controle de preços](#6-cupons-fiscais-e-controle-de-preços)
- [7. Conciliação (banco e fatura)](#7-conciliação-banco-e-fatura)
- [8. Dashboard e relatórios](#8-dashboard-e-relatórios)
- [9. Backup e segurança dos dados](#9-backup-e-segurança-dos-dados)
- [10. Versão de demonstração](#10-versão-de-demonstração)

---

## 1. Baixar, instalar e abrir

O Controle Financeiro é um programa único: um arquivo chamado
**`ControleFinanceiro.exe`**. Não precisa instalador nem internet para funcionar —
tudo roda no seu próprio computador.

1. **Baixe** o arquivo `ControleFinanceiro.exe` pelo link que você recebeu (ou pelo
   botão **Baixar** da página de divulgação).
2. **Guarde** o arquivo numa pasta sua, por exemplo `Documentos\ControleFinanceiro`.
   É nessa pasta que o programa cria os dados e os backups.
3. **Dê dois cliques** no arquivo. Abre uma janela própria do programa (sem navegador
   e sem a "tela preta" do terminal). A primeira abertura leva alguns segundos.
4. Se o Windows mostrar o aviso azul *"O Windows protegeu o computador"*, clique em
   **Mais informações → Executar assim mesmo**. Isso acontece porque o programa é novo
   e ainda não tem assinatura paga; é seguro.

> **Requisito:** Windows 10 ou 11 atualizado (já trazem o componente de janela
> "WebView2" da Microsoft, que o programa usa para desenhar a tela). Para fechar,
> basta fechar a janela — o programa encerra sozinho.

> **Dica:** clique com o botão direito no `.exe` → *Enviar para → Área de trabalho
> (criar atalho)* para abrir sempre com um clique.

## 2. Como o app organiza o dinheiro

Pense como numa planilha bem feita: cada número tem um lugar certo. O app separa
**onde** o dinheiro está (contas e cartões) de **o que** você fez com ele
(transações), e usa **categorias** para os relatórios.

| Conceito | O que é |
| --- | --- |
| **Contas** | Seu dinheiro de verdade: conta corrente, poupança, carteira. Têm saldo. |
| **Cartões de crédito** | Não têm saldo; acumulam compras numa fatura que você paga por uma conta. |
| **Transações** | Cada receita ou despesa. É o "fato" do seu controle — a linha que move tudo. |
| **Categorias** | Alimentação, Moradia, Saúde… São as "dimensões" que os relatórios somam. |

> **Regra de ouro:** pagar a fatura do cartão **não é despesa**. A despesa foi a
> compra. Pagar a fatura só move dinheiro da conta para o cartão. Assim nada conta
> em dobro.

## 3. Contas e saldos

Na tela **Contas** você cadastra cada conta e informa o **saldo inicial** (o saldo do
dia em que começou a usar o app). A partir daí o app calcula tudo sozinho.

- **Saldo atual** — saldo inicial + tudo que já foi pago/recebido.
- **Saldo previsto** — inclui também o que ainda está pendente ou agendado.

> Se um saldo não bater com o banco, não corrija "na mão" somando um ajuste: procure
> o lançamento que falta ou o saldo inicial errado. O saldo é sempre **calculado**,
> nunca digitado.

## 4. Lançar transações e parcelas

Na tela **Transações** você lança receitas e despesas. Informe data, valor, conta (ou
cartão), categoria e se já foi paga.

- **Despesa no cartão:** escolha o cartão. Ela entra na fatura do mês de acordo com a
  data da compra.
- **Parcelas:** informe o número de parcelas e o app cria uma em cada mês, cada uma
  caindo na fatura certa.
- **Filtros:** no topo da tela dá para filtrar por período, conta, categoria e
  situação.

## 5. Cartões de crédito e faturas

Em **Cartões de crédito** você vê cada cartão e abre a fatura do mês. A fatura lista as
compras e mostra o total a pagar.

- Ao pagar, lance um **"Pagamento de fatura"** saindo da conta — nunca como despesa.
- Estorno ou cashback é um **redutor** da despesa (mesma categoria da compra), não uma
  receita.
- Itens marcados para "ignorar" entram no total a pagar da fatura, mas ficam fora do
  orçamento e dos relatórios.

## 6. Cupons fiscais e controle de preços

A tela **Cupons** lê a nota fiscal item a item e registra o preço de cada produto. Com
o tempo, a tela **Preços** mostra quanto cada item custa por unidade e onde está mais
barato.

- Depois de ler o cupom, você confere, ajusta categorias e salva.
- A tela "aprende" a categoria de cada item e o meio de pagamento por loja.
- Em **Preços** você acompanha a variação do preço do mesmo produto ao longo do tempo —
  útil para decidir onde comprar.

## 7. Conciliação (banco e fatura)

**Conciliação** compara o que está no app com o extrato do banco (ou com a fatura do
cartão), para você não esquecer nenhum lançamento.

- Exporte o extrato do banco (arquivo `.ofx`) e suba na tela.
- O app separa em quatro grupos: *Casados*, *Só no banco* (lançar), *Só no app*
  (revisar) e *Divergências*.
- Nada é gravado até você clicar em **Aplicar**. Marcar "conferido" é só o visto de que
  bateu — não mexe no saldo.

## 8. Dashboard e relatórios

O **Dashboard** é o resumo do mês: receitas, despesas, saldo e para onde o dinheiro foi.
A tela **Relatórios** aprofunda por período, com taxa de poupança e fixas × variáveis.

- Troque o mês no seletor do topo.
- Em Relatórios dá para exportar em Excel (4 abas) ou PDF.

## 9. Backup e segurança dos dados

Seus dados ficam só no seu computador, num arquivo chamado `financeiro.db`, na pasta do
programa. Ninguém da internet acessa.

- O app faz **backup automático** ao abrir (se o último tiver mais de 20 horas) e guarda
  os últimos 7 dias, 4 semanas e 12 meses.
- Em **Configurações** você pode fazer um backup na hora.
- Para trocar de computador, leve a pasta inteira (o arquivo `.exe` e a pasta `data`).

## 10. Versão de demonstração

Existe uma versão só para experimentar, com dados de uma família fictícia. Ela mostra o
selo laranja **"Demonstração"** no menu e tem o botão **"Reiniciar demonstração"**, que
devolve tudo ao estado de exemplo.

> A demonstração usa um banco separado e **nunca** toca nos seus dados reais. Pode mexer
> à vontade.
