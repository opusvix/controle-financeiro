import { useState } from "react";

/** Tela de Ajuda: guia de uso dentro do próprio app.
 *  O mesmo conteúdo vive em docs/GUIA.md (versão para ler fora do app). */

type Secao = { id: string; titulo: string; corpo: JSX.Element };

const SECOES: Secao[] = [
  {
    id: "instalar",
    titulo: "1. Baixar, instalar e abrir",
    corpo: (
      <>
        <p>
          O Controle Financeiro é um programa único: um arquivo chamado{" "}
          <strong>ControleFinanceiro.exe</strong>. Não precisa instalador nem internet para
          funcionar — tudo roda no seu próprio computador.
        </p>
        <ol>
          <li>
            <strong>Baixe</strong> o arquivo <code>ControleFinanceiro.exe</code> pelo link que você
            recebeu (ou pelo botão <em>Baixar</em> da página de divulgação).
          </li>
          <li>
            <strong>Guarde</strong> o arquivo numa pasta sua, por exemplo{" "}
            <code>Documentos\ControleFinanceiro</code>. É nessa pasta que o programa vai criar os
            dados e os backups.
          </li>
          <li>
            <strong>Dê dois cliques</strong> no arquivo. Abre uma janela própria do programa (sem
            navegador e sem a “tela preta” do terminal). A primeira abertura leva alguns segundos.
          </li>
          <li>
            <strong>Aviso do Windows (normal na primeira vez):</strong> ao abrir, pode surgir uma tela
            azul <em>“O Windows protegeu o computador”</em> com <em>“Fornecedor desconhecido”</em>.{" "}
            <strong>Não é vírus</strong> — aparece só porque o programa é novo e ainda não tem uma
            assinatura digital paga. Clique em <strong>Mais informações → Executar assim mesmo</strong>.
            Para o aviso nem aparecer, antes dos dois cliques clique com o botão direito no{" "}
            <code>.exe</code> → <strong>Propriedades</strong> → marque <strong>Desbloquear</strong> →{" "}
            <strong>OK</strong>.
          </li>
        </ol>
        <p className="dica">
          <strong>Requisito:</strong> Windows 10 ou 11 atualizado (já vêm com o componente de janela
          “WebView2” da Microsoft, que o programa usa para desenhar a tela). Para fechar, basta
          fechar a janela — o programa encerra sozinho.
        </p>
        <p className="dica">
          <strong>Dica:</strong> clique com o botão direito no <code>.exe</code> →{" "}
          <em>Enviar para → Área de trabalho (criar atalho)</em> para abrir sempre com um clique.
        </p>
      </>
    ),
  },
  {
    id: "visao",
    titulo: "2. Como o app organiza o dinheiro",
    corpo: (
      <>
        <p>
          Pense como numa planilha bem feita: cada número tem um lugar certo. O app separa{" "}
          <strong>onde</strong> o dinheiro está (contas e cartões) de <strong>o que</strong> você
          fez com ele (transações), e usa <strong>categorias</strong> para os relatórios.
        </p>
        <dl className="guia-dl">
          <dt>Contas</dt>
          <dd>Seu dinheiro de verdade: conta corrente, poupança, carteira. Têm saldo.</dd>
          <dt>Cartões de crédito</dt>
          <dd>Não têm saldo; acumulam compras numa fatura que você paga por uma conta.</dd>
          <dt>Transações</dt>
          <dd>Cada receita ou despesa. É o “fato” do seu controle — a linha que move tudo.</dd>
          <dt>Categorias</dt>
          <dd>Alimentação, Moradia, Saúde… São as “dimensões” que os relatórios somam.</dd>
        </dl>
        <p className="dica">
          Regra de ouro: <strong>pagar a fatura do cartão não é despesa</strong>. A despesa foi a
          compra. Pagar a fatura só move dinheiro da conta para o cartão. Assim nada conta em dobro.
        </p>
      </>
    ),
  },
  {
    id: "contas",
    titulo: "3. Contas e saldos",
    corpo: (
      <>
        <p>
          Na tela <strong>Contas</strong> você cadastra cada conta e informa o{" "}
          <strong>saldo inicial</strong> (o saldo do dia em que começou a usar o app). A partir daí o
          app calcula tudo sozinho.
        </p>
        <dl className="guia-dl">
          <dt>Saldo atual</dt>
          <dd>Saldo inicial + tudo que já foi pago/recebido.</dd>
          <dt>Saldo previsto</dt>
          <dd>Inclui também o que ainda está pendente ou agendado.</dd>
        </dl>
        <p className="dica">
          Se um saldo não bater com o banco, não corrija “na mão” somando um ajuste: procure o
          lançamento que falta ou o saldo inicial errado. O saldo é sempre{" "}
          <strong>calculado</strong>, nunca digitado.
        </p>
      </>
    ),
  },
  {
    id: "transacoes",
    titulo: "4. Lançar transações e parcelas",
    corpo: (
      <>
        <p>
          Na tela <strong>Transações</strong> você lança receitas e despesas. Informe data, valor,
          conta (ou cartão), categoria e se já foi paga.
        </p>
        <ul>
          <li>
            <strong>Despesa no cartão:</strong> escolha o cartão. Ela entra na fatura do mês de
            acordo com a data da compra.
          </li>
          <li>
            <strong>Parcelas:</strong> informe o número de parcelas e o app cria uma em cada mês,
            cada uma caindo na fatura certa.
          </li>
          <li>
            <strong>Filtros:</strong> no topo da tela dá para filtrar por período, conta, categoria e
            situação, igual ao app que você já usa.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "cartoes",
    titulo: "5. Cartões de crédito e faturas",
    corpo: (
      <>
        <p>
          Em <strong>Cartões de crédito</strong> você vê cada cartão e abre a fatura do mês. A
          fatura lista as compras e mostra o total a pagar.
        </p>
        <ul>
          <li>Ao pagar, lance um <strong>“Pagamento de fatura”</strong> saindo da conta — nunca como despesa.</li>
          <li>
            Estorno ou cashback é um <strong>redutor</strong> da despesa (mesma categoria da compra),
            não uma receita.
          </li>
          <li>
            Itens marcados para “ignorar” entram no total a pagar da fatura, mas ficam fora do
            orçamento e dos relatórios.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "cupons",
    titulo: "6. Cupons fiscais e controle de preços",
    corpo: (
      <>
        <p>
          A tela <strong>Cupons</strong> lê a nota fiscal item a item e registra o preço de cada
          produto. Com o tempo, a tela <strong>Preços</strong> mostra quanto cada item custa por
          unidade e onde está mais barato.
        </p>
        <ul>
          <li>Depois de ler o cupom, você confere, ajusta categorias e salva.</li>
          <li>A tela “aprende” a categoria de cada item e o meio de pagamento por loja.</li>
          <li>
            Em <strong>Preços</strong> você acompanha a variação do preço do mesmo produto ao longo
            do tempo — útil para decidir onde comprar.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "conciliacao",
    titulo: "7. Conciliação (banco e fatura)",
    corpo: (
      <>
        <p>
          <strong>Conciliação</strong> compara o que está no app com o extrato do banco (ou com a
          fatura do cartão), para você não esquecer nenhum lançamento.
        </p>
        <ul>
          <li>Exporte o extrato do banco (arquivo <code>.ofx</code>) e suba na tela.</li>
          <li>
            O app separa em quatro grupos: <em>Casados</em>, <em>Só no banco</em> (lançar),{" "}
            <em>Só no app</em> (revisar) e <em>Divergências</em>.
          </li>
          <li>
            Nada é gravado até você clicar em <strong>Aplicar</strong>. Marcar “conferido” é só o
            visto de que bateu — não mexe no saldo.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "relatorios",
    titulo: "8. Dashboard e relatórios",
    corpo: (
      <>
        <p>
          O <strong>Dashboard</strong> é o resumo do mês: receitas, despesas, saldo e para onde o
          dinheiro foi. A tela <strong>Relatórios</strong> aprofunda por período, com taxa de
          poupança e fixas × variáveis.
        </p>
        <ul>
          <li>Troque o mês no seletor do topo.</li>
          <li>Em Relatórios dá para exportar em Excel (4 abas) ou PDF.</li>
        </ul>
      </>
    ),
  },
  {
    id: "backup",
    titulo: "9. Backup e segurança dos dados",
    corpo: (
      <>
        <p>
          Seus dados ficam só no seu computador, num arquivo chamado{" "}
          <code>financeiro.db</code>, na pasta do programa. Ninguém da internet acessa.
        </p>
        <ul>
          <li>
            O app faz <strong>backup automático</strong> ao abrir (se o último tiver mais de 20
            horas) e guarda os últimos 7 dias, 4 semanas e 12 meses.
          </li>
          <li>Em <strong>Configurações</strong> você pode fazer um backup na hora.</li>
          <li>
            Para trocar de computador, leve a pasta inteira (o arquivo <code>.exe</code> e a pasta{" "}
            <code>data</code>).
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "demo",
    titulo: "10. Versão de demonstração",
    corpo: (
      <>
        <p>
          Existe uma versão só para experimentar, com dados de uma família fictícia. Ela mostra o
          selo laranja <strong>“Demonstração”</strong> no menu e tem o botão{" "}
          <strong>“Reiniciar demonstração”</strong>, que devolve tudo ao estado de exemplo.
        </p>
        <p className="dica">
          A demonstração usa um banco separado e <strong>nunca</strong> toca nos seus dados reais.
          Pode mexer à vontade.
        </p>
      </>
    ),
  },
];

export default function Ajuda() {
  const [aberta, setAberta] = useState<string | null>("instalar");

  function irPara(id: string) {
    setAberta(id);
    document.getElementById(`sec-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <>
      <header className="topo">
        <h1>Ajuda</h1>
      </header>

      <section className="guia">
        <div className="cartao-painel guia-intro">
          <p>
            Bem-vindo! Este guia explica, passo a passo, como usar o Controle Financeiro. Comece por{" "}
            <strong>Baixar, instalar e abrir</strong> e vá descendo. Clique num tópico para pular
            para ele.
          </p>
          <nav className="guia-toc">
            {SECOES.map((s) => (
              <a key={s.id} href={`#sec-${s.id}`} onClick={(e) => { e.preventDefault(); irPara(s.id); }}>
                {s.titulo}
              </a>
            ))}
          </nav>
        </div>

        {SECOES.map((s) => (
          <article key={s.id} id={`sec-${s.id}`} className="cartao-painel guia-secao">
            <h2
              className={aberta === s.id ? "guia-h aberta" : "guia-h"}
              onClick={() => setAberta(aberta === s.id ? null : s.id)}
            >
              {s.titulo}
            </h2>
            {aberta === s.id && <div className="guia-corpo">{s.corpo}</div>}
          </article>
        ))}
      </section>
    </>
  );
}
