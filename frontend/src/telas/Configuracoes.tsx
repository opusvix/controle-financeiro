import { useState } from "react";
import { api } from "../api";
import { useDados } from "../componentes/useDados";

export default function Configuracoes() {
  const saude = useDados(api.saude);
  const [msg, setMsg] = useState<string | null>(null);

  async function backupAgora() {
    setMsg("Fazendo backup…");
    try {
      const r = await api.backup();
      setMsg(`Backup salvo em ${r.arquivo}${r.copiado_drive ? " e copiado para o Google Drive" : " (Google Drive indisponível)"}.`);
      saude.recarregar();
    } catch (e) { setMsg((e as Error).message); }
  }

  const s = saude.dados;
  return (
    <>
      <header className="topo"><h1>Configurações</h1></header>
      <section className="grade-2">
        <div className="cartao-painel">
          <h3>Backup</h3>
          {s && (
            <dl>
              <dt>Banco de dados</dt><dd className="mono">{s.banco}</dd>
              <dt>Último backup</dt>
              <dd>{s.ultimo_backup ? `${s.ultimo_backup.arquivo} (${s.ultimo_backup.criado_em} UTC)` : "nenhum ainda"}</dd>
              <dt>Cópia no Google Drive</dt><dd>{s.ultimo_backup?.copiado_drive ? "sim" : "não"}</dd>
            </dl>
          )}
          <p className="dica">O backup automático roda ao abrir o app, se o último tiver mais de 20 horas.
            Guarda 7 diários, 4 semanais e 12 mensais.</p>
          <button className="primario" onClick={backupAgora}>Fazer backup agora</button>
          {msg && <p>{msg}</p>}
        </div>
        <div className="cartao-painel">
          <h3>Leitura de cupons</h3>
          <p>{s?.leitura_ia_configurada ? "Chave da IA configurada." :
            "Chave da IA ainda não configurada. Coloque ANTHROPIC_API_KEY no arquivo .env do projeto."}</p>
          <h3 className="espaco">Preferências</h3>
          <p className="vazio">Idioma: português (Brasil) · Moeda: real (R$) · Tema: escuro</p>
        </div>
      </section>
    </>
  );
}
