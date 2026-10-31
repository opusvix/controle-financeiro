import { useCallback, useEffect, useState } from "react";

/** Carrega dados do servidor e expõe recarregar() para depois de salvar. */
export function useDados<T>(buscar: () => Promise<T>, deps: unknown[] = []) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const recarregar = useCallback(() => {
    buscar().then((d) => { setDados(d); setErro(null); }).catch((e: Error) => setErro(e.message));
  }, deps);
  useEffect(recarregar, [recarregar]);
  return { dados, erro, recarregar };
}
