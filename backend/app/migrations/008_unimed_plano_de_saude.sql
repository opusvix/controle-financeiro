-- Plano de saúde: a UNIMED veio do Mobills na categoria-mãe "Saúde", junto com farmácia.
--    Passa para "Saúde > Plano de saúde" (fixa), a pedido do João em 03/11/2026.
UPDATE transacao
   SET categoria_id = (SELECT f.id FROM categoria f JOIN categoria m ON m.id = f.pai_id
                        WHERE f.nome = 'Plano de saúde' AND m.nome = 'Saúde' AND f.tipo = 'despesa')
 WHERE upper(trim(descricao)) LIKE 'UNIMED%'
   AND categoria_id = (SELECT id FROM categoria WHERE nome = 'Saúde' AND pai_id IS NULL AND tipo = 'despesa')
   AND EXISTS (SELECT 1 FROM categoria f JOIN categoria m ON m.id = f.pai_id
                WHERE f.nome = 'Plano de saúde' AND m.nome = 'Saúde' AND f.tipo = 'despesa');
