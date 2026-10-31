# Dicionário de métricas

Cada número do app tem **uma** fórmula, usada em todas as telas. No Mobills o
card "Despesas" (R$ 5.906,77) e o gráfico "Despesas por categoria"
(R$ 6.084,40) mostravam valores diferentes na mesma tela; aqui isso não acontece.

| Métrica | Fórmula | Observação |
| --- | --- | --- |
| Saldo da conta (atual) | saldo inicial + efeito das transações **pagas** desde a data do saldo inicial | Efeito: receita +, despesa −, transferência −/+, pagamento de fatura −, ajuste ± |
| Saldo da conta (previsto) | igual ao atual, incluindo as **pendentes** | |
| Saldo disponível | soma do saldo atual das contas marcadas "compõe saldo disponível" | É o "caixa": corrente, carteira. Investimentos ficam de fora |
| Patrimônio | soma do saldo atual de todas as contas ativas | Caixa + investimentos |
| Receitas do mês | receitas com data no mês (pagas e pendentes), sem as ignoradas | |
| Despesas do mês | despesas + despesas de cartão com **data da compra** no mês, sem as ignoradas | Regime de competência. Pagamento de fatura e transferências **não** entram |
| Despesas por categoria | mesma base de "Despesas do mês", agrupada pela categoria-mãe; compras com itens usam a categoria de cada item (valor líquido) | A soma do gráfico é igual ao card |
| Fatura do mês (cartão) | despesas de cartão cuja fatura tem competência (mês do vencimento) igual ao mês | |
| Limite disponível | limite − (todas as compras no cartão − todos os pagamentos de fatura) | |
| Preço líquido unitário | (valor do item − desconto do item) ÷ quantidade | View `v_preco` |

## Regra da fatura

Compra **no dia do fechamento ou depois** vai para a fatura seguinte. O
vencimento é o primeiro dia de vencimento depois do fechamento. Dia 31 em
meses mais curtos vira o último dia do mês.
