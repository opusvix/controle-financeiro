import { useState } from "react";
import { api } from "../api";

/** Guarda/recupera a última pasta usada por tarefa (só conveniência; pode falhar em modo privado). */
const lerSalvo = (chave: string) => { try { return localStorage.getItem(chave) ?? ""; } catch { return ""; } };
const salvar = (chave: string, p: string) => { try { localStorage.setItem(chave, p); } catch { /* ignora */ } };

/**
 * Campo "pasta que lembra o último local": a pessoa cola o caminho de uma pasta do próprio
 * computador (o servidor é local), o app lista os arquivos do tipo pedido e ela clica no que quer.
 * O caminho fica guardado (localStorage) por tarefa — na próxima vez já vem preenchido.
 */
export default function SeletorPasta({ chave, extensoes, rotulo, disabled, ocupado, aoEscolher }: {
  chave: string; extensoes: string[]; rotulo: string;
  disabled?: boolean; ocupado?: boolean; aoEscolher: (pasta: string, arquivo: string) => void;
}) {
  const [pasta, setPasta] = useState(() => lerSalvo(chave));
  const [arquivos, setArquivos] = useState<string[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [listando, setListando] = useState(false);

  async function listar() {
    const p = pasta.trim();
    if (!p) { setErro("Cole o caminho da pasta."); return; }
    setListando(true); setErro(null); setArquivos(null);
    try {
      const r = await api.listarArquivos(p, extensoes);
      salvar(chave, p);
      setArquivos(r.arquivos);
      if (!r.arquivos.length) setErro("A pasta não tem arquivos desse tipo.");
    } catch (e) { setErro((e as Error).message); }
    finally { setListando(false); }
  }

  return (
    <div className="cartao-painel espaco sel-pasta">
      <label>{rotulo} <small>(o app guarda a última pasta usada)</small>
        <input type="text" value={pasta} placeholder="D:\..." disabled={disabled}
          onChange={(e) => setPasta(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") listar(); }} />
      </label>
      <button type="button" className="primario" disabled={disabled || listando} onClick={listar}>
        {listando ? "Listando…" : "Listar arquivos"}</button>
      {erro && <p className="erro sel-pasta-erro">{erro}</p>}
      {arquivos && arquivos.length > 0 && (
        <ul className="sel-pasta-lista">
          {arquivos.map((a) => (
            <li key={a}>
              <button type="button" className="sel-pasta-arq" disabled={ocupado}
                onClick={() => aoEscolher(pasta.trim(), a)}>📄 {a}</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
