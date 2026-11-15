"""Leitura dos PDFs das contas da casa (texto já extraído; o PDF real fica no PC do João)."""
from pathlib import Path

from app.importacao import contas_pdf

AMOSTRA = (Path(__file__).parent / "dados" / "escelsa_amostra.txt").read_text(encoding="utf-8")


def test_le_a_fatura_da_escelsa():
    f = contas_pdf.ler_escelsa(AMOSTRA)
    assert (f.referencia, f.vencimento, f.total_centavos) == ("2026-09", "2026-10-13", 10216)
    fc = f.ficha
    assert fc["consumo"] == 224
    assert round(fc["kwh_compensado"]) == 174           # créditos da Solar (só TUSD, sem repetir a TE)
    assert fc["bandeira"] == "amarela"
    assert fc["bandeira_centavos"] == 548 - 400           # adicional menos a parte abatida
    assert (fc["cip_centavos"], fc["terceiros_centavos"]) == (2791, 671)
    assert fc["multa_juros_centavos"] is None
    assert ("2025-09", 192.0, 8808) in f.historico


def test_sem_bandeira_e_verde_e_multa_soma():
    t = AMOSTRA.replace("Adicional Bandeira", "Outro item") + \
        "\n Multa por atraso   2,04 0,00000000\n Juros de mora   0,68 0,00000000\n"
    fc = contas_pdf.ler_escelsa(t).ficha
    assert fc["bandeira"] == "verde" and fc["bandeira_centavos"] is None
    assert fc["multa_juros_centavos"] == 272


def test_importa_e_liga_ao_lancamento_pago(cliente, monkeypatch, tmp_path):
    conta = cliente.post("/api/contas", json={"nome": "Itaú", "tipo": "corrente",
        "data_saldo_inicial": "2026-01-01"}).json()["id"]
    t = cliente.post("/api/transacoes", json={"tipo": "despesa", "descricao": "EDP ESCELSA",
        "valor_centavos": 10216, "data": "2026-10-16", "conta_id": conta}).json()[0]
    outra = cliente.post("/api/transacoes", json={"tipo": "despesa", "descricao": "EDP ESCELSA",
        "valor_centavos": 9100, "data": "2026-09-10", "conta_id": conta}).json()[0]
    (tmp_path / "2026-10-13-ESCELSA.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(contas_pdf, "texto_do_pdf", lambda caminho, senha=None: AMOSTRA)
    con = cliente.app.state.con
    _, texto = contas_pdf.executar(con, tmp_path, simular=True)
    assert "fichas a gravar: 1" in texto
    assert cliente.get(f"/api/transacoes/{t['id']}/ficha").json()["gravada"] is False
    contas_pdf.executar(con, tmp_path, simular=False)
    f = cliente.get(f"/api/transacoes/{t['id']}/ficha").json()
    assert f["gravada"] and f["consumo"] == 224 and f["cip_centavos"] == 2791
    assert f["arquivo"] == "2026-10-13-ESCELSA.pdf"
    assert cliente.get(f"/api/transacoes/{outra['id']}/ficha").json()["gravada"] is False
    lista = cliente.get("/api/transacoes?competencia=2026-10").json()
    assert next(x for x in lista if x["id"] == t["id"])["vencimento"] == "2026-10-13"   # 3 dias de atraso
    # editar a ficha pela tela não apaga o que veio do PDF
    cliente.put(f"/api/transacoes/{t['id']}/ficha", json={"tipo": "energia", "consumo": 224,
        "multa_juros_centavos": 120})
    f = cliente.get(f"/api/transacoes/{t['id']}/ficha").json()
    assert f["cip_centavos"] == 2791 and f["multa_juros_centavos"] == 120


SOLAR = (Path(__file__).parent / "dados" / "solar_amostra.txt").read_text(encoding="utf-8")


def test_le_a_cobranca_da_solar():
    f = contas_pdf.ler_solar(SOLAR)
    assert (f.emissor, f.referencia, f.vencimento, f.total_centavos) == ("EDP Solar", "2026-03", "2026-04-06", 21211)
    assert f.ficha["kwh_compensado"] == 245 and f.ficha["consumo"] == 295
    assert f.ficha["desconto_centavos"] == 2357            # a economia declarada (10%)
    assert f.historico == []                                # a série de consumo vem da Escelsa


def test_solar_que_nao_fecha_nao_e_gravada():
    import pytest
    with pytest.raises(ValueError):
        contas_pdf.ler_solar(SOLAR.replace("R$ 23,57", "R$ 13,57"))


def test_pdf_nao_entendido_guarda_o_texto_para_diagnostico(tmp_path, monkeypatch):
    (tmp_path / "x-EDP-SOLAR.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(contas_pdf, "texto_do_pdf", lambda c, s=None: "Solar Digital EDP sem nada")
    import pytest
    with pytest.raises(ValueError):
        contas_pdf.ler(tmp_path / "x-EDP-SOLAR.pdf", diagnostico=tmp_path / "_texto")
    assert (tmp_path / "_texto" / "x-EDP-SOLAR.txt").read_text(encoding="utf-8").startswith("Solar")


def _subir(cliente, nome, conteudo=b"%PDF", senha=None):
    arquivos = [("arquivos", (nome, conteudo, "application/pdf"))]
    dados = {"senha": senha} if senha else None
    return cliente.post("/api/contas-pdf/analisar", files=arquivos, data=dados)


def test_tela_analisa_e_grava_a_ficha(cliente, monkeypatch):
    conta = cliente.post("/api/contas", json={"nome": "Itaú", "tipo": "corrente",
        "data_saldo_inicial": "2026-01-01"}).json()["id"]
    t = cliente.post("/api/transacoes", json={"tipo": "despesa", "descricao": "EDP ESCELSA",
        "valor_centavos": 10216, "data": "2026-10-16", "conta_id": conta}).json()[0]
    monkeypatch.setattr(contas_pdf, "texto_do_pdf", lambda caminho, senha=None: AMOSTRA)

    r = _subir(cliente, "2026-10-13-ESCELSA.pdf").json()
    assert len(r["contas"]) == 1
    c0 = r["contas"][0]
    assert c0["status"] == "ok" and c0["fatura"]["referencia"] == "2026-09"
    assert c0["fatura"]["emissor"] == "EDP Escelsa" and c0["fatura"]["ficha"]["consumo"] == 224
    assert c0["lancamento"]["id"] == t["id"] and c0["lancamento"]["ja_tem_ficha"] is False
    # analisar não grava nada
    assert cliente.get(f"/api/transacoes/{t['id']}/ficha").json()["gravada"] is False

    g = cliente.post("/api/contas-pdf/gravar",
                     json={"itens": [{"fatura": c0["fatura"], "transacao_id": t["id"]}]}).json()
    assert g["gravadas"] == 1
    f = cliente.get(f"/api/transacoes/{t['id']}/ficha").json()
    assert f["gravada"] and f["consumo"] == 224 and f["cip_centavos"] == 2791
    assert f["arquivo"] == "2026-10-13-ESCELSA.pdf"
    lista = cliente.get("/api/transacoes?competencia=2026-10").json()
    assert next(x for x in lista if x["id"] == t["id"])["vencimento"] == "2026-10-13"
    # depois de gravada, a tela avisa que já tem ficha
    assert _subir(cliente, "2026-10-13-ESCELSA.pdf").json()["contas"][0]["lancamento"]["ja_tem_ficha"] is True


def test_tela_sem_lancamento_e_nao_pdf(cliente, monkeypatch):
    monkeypatch.setattr(contas_pdf, "texto_do_pdf", lambda caminho, senha=None: AMOSTRA)
    # não há lançamento de R$ 102,16 no app: lê a fatura, mas sem lançamento para preencher
    r = _subir(cliente, "ESCELSA.pdf").json()
    assert r["contas"][0]["status"] == "ok" and r["contas"][0]["lancamento"] is None
    # arquivo que não é PDF é ignorado (a pasta pode ter outros arquivos)
    arquivos = [("arquivos", ("leia-me.txt", b"nada", "text/plain"))]
    assert cliente.post("/api/contas-pdf/analisar", files=arquivos).json()["contas"] == []


def test_tela_cria_a_despesa_que_falta_e_anexa_a_ficha(cliente, monkeypatch):
    conta = cliente.post("/api/contas", json={"nome": "Itaú", "tipo": "corrente",
        "data_saldo_inicial": "2026-01-01"}).json()["id"]
    monkeypatch.setattr(contas_pdf, "texto_do_pdf", lambda caminho, senha=None: AMOSTRA)
    # nenhum lançamento de R$ 102,16 existe ainda
    c0 = _subir(cliente, "2026-10-13-ESCELSA.pdf").json()["contas"][0]
    assert c0["lancamento"] is None

    # por padrão a despesa criada fica A PAGAR (a conta pode estar a vencer; quem decide é o usuário)
    g = cliente.post("/api/contas-pdf/gravar", json={"itens": [
        {"fatura": c0["fatura"], "criar": {"conta_id": conta}}]}).json()
    assert g["gravadas"] == 1 and g["criadas"] == 1
    lista = cliente.get("/api/transacoes?competencia=2026-10").json()
    nova = next(x for x in lista if x["descricao"] == "EDP Escelsa" and x["valor_centavos"] == 10216)
    assert nova["tipo"] == "despesa" and nova["pago"] == 0 and nova["conta_id"] == conta
    assert nova["data"] == "2026-10-13"                     # datada no vencimento
    f = cliente.get(f"/api/transacoes/{nova['id']}/ficha").json()
    assert f["gravada"] and f["consumo"] == 224


def test_tela_cria_despesa_ja_paga_quando_o_usuario_marca(cliente, monkeypatch):
    conta = cliente.post("/api/contas", json={"nome": "Itaú", "tipo": "corrente",
        "data_saldo_inicial": "2026-01-01"}).json()["id"]
    monkeypatch.setattr(contas_pdf, "texto_do_pdf", lambda caminho, senha=None: AMOSTRA)
    c0 = _subir(cliente, "ESCELSA.pdf").json()["contas"][0]
    cliente.post("/api/contas-pdf/gravar", json={"itens": [
        {"fatura": c0["fatura"], "criar": {"conta_id": conta, "pago": True}}]})
    lista = cliente.get("/api/transacoes?competencia=2026-10").json()
    nova = next(x for x in lista if x["descricao"] == "EDP Escelsa")
    assert nova["pago"] == 1


def test_tela_marca_pdf_protegido_por_senha(cliente, monkeypatch):
    def pede_senha(caminho, senha=None):
        raise PermissionError("protegido por senha")
    monkeypatch.setattr(contas_pdf, "texto_do_pdf", pede_senha)
    assert _subir(cliente, "SOLAR.pdf").json()["contas"][0]["status"] == "senha"


def test_abre_pdf_com_senha_aes256(tmp_path):
    """A EDP Solar protege o PDF com AES-256: precisa da biblioteca cryptography."""
    import pytest
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject
    w = PdfWriter()
    pg = w.add_blank_page(100, 100)
    conteudo = DecodedStreamObject()
    conteudo.set_data(b"")
    pg[NameObject("/Contents")] = w._add_object(conteudo)
    w.encrypt("segredo", algorithm="AES-256")
    pdf = tmp_path / "solar.pdf"
    w.write(pdf)
    assert isinstance(contas_pdf.texto_do_pdf(pdf, "segredo"), str)
    assert isinstance(contas_pdf.texto_do_pdf(pdf, "da-claro;segredo"), str)   # várias senhas
    with pytest.raises(PermissionError):
        contas_pdf.texto_do_pdf(pdf, "errada")
