# Cupons: como entram no app

## NFC-e com QR (PERIM, Padaria Ideal…)
1. Em **Cupons › 1**, envie a foto do cupom. O app lê o QR e mostra **Abrir na SEFAZ**.
2. No navegador, resolva o captcha. Quando a lista de itens aparecer, aperte **Ctrl+S** e salve.
3. Em **Cupons › 2**, escolha o `.html` salvo. Revise as categorias, escolha a conta ou o cartão e lance.

São dados oficiais da nota. A soma dos itens é conferida com o "Valor a pagar", e a chave de
acesso impede lançar a mesma nota duas vezes.

## Pedido sem QR (Frescor, comprovantes)
Peça ao Claude no projeto: "lê os pedidos da pasta Notas". Ele gera um `.json` neste formato,
que entra pelo mesmo **Cupons › 2**:

```json
{
  "origem": "foto",
  "tipo_documento": "pedido",
  "emitente": {"nome": "FRESCOR", "cnpj": null, "cidade": "Vila Velha", "uf": "ES"},
  "numero": "1234",
  "emissao": "2026-10-28T10:15:00",
  "itens": [
    {"descricao": "TOMATE ITALIANO", "codigo": null, "quantidade_milesimos": 850, "unidade": "KG",
     "preco_unitario_centavos": 799, "valor_total_centavos": 679, "desconto_centavos": 0}
  ],
  "desconto_centavos": 0,
  "valor_pagar_centavos": 679
}
```

Regras: dinheiro em centavos (inteiro), quantidade em milésimos (0,850 kg = 850; 2 un = 2000).
Desconto só no total é rateado entre os itens, proporcional ao valor.

## Aprendizado de categorias
Na próxima compra, cada item já vem com a categoria sugerida. A busca segue esta ordem:
1. O mesmo código na mesma loja.
2. A mesma descrição em qualquer loja.
3. A categoria mais usada na loja.
