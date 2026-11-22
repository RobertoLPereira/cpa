import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text
from sqlmodel import Session

from backend.apis.mysql.orm.database_unificado import get_session

NS = {'nfe': "http://" + "www.portalfiscal.inf.br" + "/nfe"}
importa_nfe_router = APIRouter(prefix="/api/v1/retaguarda/importa-nfe", tags=["Retaguarda - Importação NF-e"])


def _get_text(element, path, default=None):
    if element is None:
        return default
    found = element.find(path, NS)
    return found.text.strip() if found is not None and found.text else default


def _agora_iso():
    fuso_br = timezone(timedelta(hours=-3))
    return datetime.now(fuso_br).strftime("%Y-%m-%dT%H:%M:%S%z")[:-2] + ":00"


def _definir_cfop_venda(cfop_compra: str, icms_cst: str) -> str:
    if cfop_compra in ("5401", "5403", "5405", "6401", "6403") or icms_cst in ("60", "500"):
        return "5405"
    return "5102"


def _salvar_produto(session: Session, dados_prod: dict, qtd_somar: float, agora: str):
    row = session.exec(
        text("SELECT id, estoque_atual FROM produto WHERE cprod = :cprod OR (cean IS NOT NULL AND cean != 'SEM GTIN' AND cean = :cean)"),
        params={"cprod": dados_prod["cprod"], "cean": dados_prod["cean"]}
    ).first()

    if row:
        prod_id = row.id
        novo_estoque = float(row.estoque_atual or 0) + qtd_somar
        session.exec(
            text("""
                UPDATE produto SET
                    xprod = :xprod, ncm = :ncm, cest = :cest, cfop_padrao = :cfop_venda,
                    ucom = :unidade, vuncom = :preco_venda, utrib = :unidade, vuntrib = :preco_venda,
                    fator_conversao = :fator_conversao, estoque_atual = :estoque, atualizado_em = :agora
                WHERE id = :id
            """),
            params={**dados_prod, "estoque": novo_estoque, "agora": agora, "id": prod_id}
        )
        return "ATUALIZADO"
    else:
        session.exec(
            text("""
                INSERT INTO produto (
                    id, cprod, cean, xprod, ncm, cest, cbenef, cfop_padrao,
                    ucom, vuncom, ceantrib, utrib, vuntrib,
                    fator_conversao, estoque_atual,
                    icms_orig, icms_cst, icms_picms,
                    pis_cst, pis_ppis, cofins_cst, cofins_pcofins,
                    ibscbs_cst, ibscbs_cclasstrib, ibs_pibsuf, cbs_pcbs,
                    atualizado_em, ind_monofasico
                ) VALUES (
                    :id, :cprod, :cean, :xprod, :ncm, :cest, :cbenef, :cfop_venda,
                    :unidade, :preco_venda, :cean, :unidade, :preco_venda,
                    :fator_conversao, :estoque,
                    :icms_orig, :icms_cst, :icms_picms,
                    :pis_cst, :pis_ppis, :cofins_cst, :cofins_pcofins,
                    :ibscbs_cst, :ibscbs_cclasstrib, :ibs_pibsuf, :cbs_pcbs,
                    :agora, 0
                )
            """),
            params={**dados_prod, "id": str(uuid.uuid4()), "estoque": qtd_somar, "agora": agora}
        )
        return "NOVO"


def _processar_conteudo_xml(xml_bytes: bytes, session: Session, fator_margem: float) -> dict:
    root = ET.fromstring(xml_bytes)
    inf_nfe = root.find(".//nfe:infNFe", NS)
    if inf_nfe is None:
        return {"status": "IGNORADO", "motivo": "Arquivo não é uma NF-e válida"}

    chnfe = inf_nfe.attrib.get("Id", "").replace("NFe", "")
    ide = inf_nfe.find("nfe:ide", NS)
    emit = inf_nfe.find("nfe:emit", NS)
    dest = inf_nfe.find("nfe:dest", NS)
    icms_tot = inf_nfe.find(".//nfe:total/nfe:ICMSTot", NS)

    nnf = _get_text(ide, "nfe:nNF", "0")
    fornecedor = _get_text(emit, "nfe:xNome", "FORNECEDOR")
    vnf = float(_get_text(icms_tot, "nfe:vNF", "0"))
    cnpj_dest = _get_text(dest, "nfe:CNPJ") or _get_text(dest, "nfe:CPF")

    # Valida se a nota pertence ao emitente (loja) cadastrado no banco
    loja = session.exec(text("SELECT id, cnpj FROM emitente LIMIT 1")).first()
    if loja and cnpj_dest != loja.cnpj:
        return {"status": "IGNORADO", "nnf": nnf, "fornecedor": fornecedor, "motivo": f"CNPJ Destinatário ({cnpj_dest}) difere da loja"}

    # Trava contra reimportação
    ja_existe = session.exec(text("SELECT id FROM nfe WHERE chnfe = :ch"), params={"ch": chnfe}).first()
    if ja_existe:
        return {"status": "JA_IMPORTADA", "nnf": nnf, "fornecedor": fornecedor, "vnf": vnf, "motivo": "Nota já importada anteriormente"}

    emitente_id = loja.id if loja else str(uuid.uuid4())
    agora = _agora_iso()
    itens_novos = 0
    itens_atualizados = 0

    for det in inf_nfe.findall("nfe:det", NS):
        prod = det.find("nfe:prod", NS)
        imposto = det.find("nfe:imposto", NS)

        cprod_forn = _get_text(prod, "nfe:cProd")
        xprod = _get_text(prod, "nfe:xProd", "")
        ncm = _get_text(prod, "nfe:NCM", "")
        cest = _get_text(prod, "nfe:CEST")
        cbenef = _get_text(prod, "nfe:cBenef")
        cfop_compra = _get_text(prod, "nfe:CFOP", "")

        u_com = _get_text(prod, "nfe:uCom", "UN").upper()
        u_trib = _get_text(prod, "nfe:uTrib", "UN").upper()
        c_ean = _get_text(prod, "nfe:cEAN")
        c_ean_trib = _get_text(prod, "nfe:cEANTrib")

        ean_cx = c_ean if c_ean and c_ean != "SEM GTIN" else None
        ean_un = c_ean_trib if c_ean_trib and c_ean_trib != "SEM GTIN" else None

        q_com = float(_get_text(prod, "nfe:qCom", "1"))
        q_trib = float(_get_text(prod, "nfe:qTrib", "1"))
        v_prod_total = float(_get_text(prod, "nfe:vProd", "0"))

        icms_node = imposto.find(".//nfe:ICMS/*", NS)
        icms_orig = _get_text(icms_node, "nfe:orig", "0")
        icms_cst = _get_text(icms_node, "nfe:CST") or _get_text(icms_node, "nfe:CSOSN") or "102"
        icms_picms = float(_get_text(icms_node, "nfe:pICMS", "0"))

        pis_node = imposto.find(".//nfe:PIS/*", NS)
        pis_cst = _get_text(pis_node, "nfe:CST", "01")
        pis_ppis = float(_get_text(pis_node, "nfe:pPIS", "0"))

        cofins_node = imposto.find(".//nfe:COFINS/*", NS)
        cofins_cst = _get_text(cofins_node, "nfe:CST", "01")
        cofins_pcofins = float(_get_text(cofins_node, "nfe:pCOFINS", "0"))

        ibscbs_node = imposto.find("nfe:IBSCBS", NS)
        ibscbs_cst = _get_text(ibscbs_node, "nfe:CST", "000")
        ibscbs_cclasstrib = _get_text(ibscbs_node, "nfe:cClassTrib", "000001")
        ibs_pibsuf = float(_get_text(ibscbs_node, ".//nfe:pIBSUF", "0"))
        cbs_pcbs = float(_get_text(ibscbs_node, ".//nfe:pCBS", "0"))

        cfop_venda = _definir_cfop_venda(cfop_compra, icms_cst)
        base_trib = {
            "ncm": ncm, "cest": cest, "cbenef": cbenef, "cfop_venda": cfop_venda,
            "icms_orig": icms_orig, "icms_cst": icms_cst, "icms_picms": icms_picms,
            "pis_cst": pis_cst, "pis_ppis": pis_ppis,
            "cofins_cst": cofins_cst, "cofins_pcofins": cofins_pcofins,
            "ibscbs_cst": ibscbs_cst, "ibscbs_cclasstrib": ibscbs_cclasstrib,
            "ibs_pibsuf": ibs_pibsuf, "cbs_pcbs": cbs_pcbs
        }

        fator_conv = round(q_trib / q_com, 4) if q_com > 0 else 1.0
        qtd_total_un = q_com * fator_conv

        if u_com in ("CX", "CD") and ean_cx and ean_un and ean_cx != ean_un:
            custo_un = v_prod_total / qtd_total_un if qtd_total_un > 0 else 0.0
            st1 = _salvar_produto(session, {
                **base_trib, "cprod": cprod_forn, "cean": ean_un,
                "xprod": xprod[:120].upper(), "unidade": u_trib if u_trib not in ("CX", "CD") else "UN",
                "preco_venda": round(custo_un * fator_margem, 2), "fator_conversao": 1.0
            }, qtd_total_un, agora)

            custo_cx = v_prod_total / q_com if q_com > 0 else 0.0
            st2 = _salvar_produto(session, {
                **base_trib, "cprod": f"{cprod_forn}-{u_com}", "cean": ean_cx,
                "xprod": f"{xprod[:110].upper()} ({u_com})", "unidade": u_com,
                "preco_venda": round(custo_cx * fator_margem, 2), "fator_conversao": fator_conv
            }, 0.0, agora)

            itens_novos += (1 if st1 == "NOVO" else 0) + (1 if st2 == "NOVO" else 0)
            itens_atualizados += (1 if st1 == "ATUALIZADO" else 0) + (1 if st2 == "ATUALIZADO" else 0)
        else:
            ean_final = ean_un if (u_com in ("CX", "CD") and ean_un) else (ean_cx or ean_un or "SEM GTIN")
            unidade_final = u_trib if (u_com in ("CX", "CD") and u_trib) else u_com
            custo_unit = v_prod_total / qtd_total_un if qtd_total_un > 0 else 0.0
            st = _salvar_produto(session, {
                **base_trib, "cprod": cprod_forn, "cean": ean_final,
                "xprod": xprod[:120].upper(), "unidade": unidade_final,
                "preco_venda": round(custo_unit * fator_margem, 2), "fator_conversao": fator_conv
            }, qtd_total_un, agora)
            itens_novos += 1 if st == "NOVO" else 0
            itens_atualizados += 1 if st == "ATUALIZADO" else 0

    session.exec(
        text("""
            INSERT INTO nfe (
                id, emitente_id, status_sefaz, sincronizado, chnfe, cuf, cnf, natop,
                modelo, serie, nnf, dhemi, tpnf, iddest, cmunfg, tpimp, tpemis, cdv, tpamb,
                vprod, vnf, modfrete
            ) VALUES (
                :id, :emitente_id, 'AUTORIZADA', 1, :chnfe, :cuf, :cnf, :natop,
                :modelo, :serie, :nnf, :dhemi, '0', :iddest, :cmunfg, :tpimp, :tpemis, :cdv, :tpamb,
                :vprod, :vnf, '0'
            )
        """),
        params={
            "id": str(uuid.uuid4()), "emitente_id": emitente_id, "chnfe": chnfe,
            "cuf": _get_text(ide, "nfe:cUF", "42"), "cnf": _get_text(ide, "nfe:cNF", "00000000"),
            "natop": _get_text(ide, "nfe:natOp", "COMPRA")[:60], "modelo": _get_text(ide, "nfe:mod", "55"),
            "serie": _get_text(ide, "nfe:serie", "1"), "nnf": int(nnf),
            "dhemi": _get_text(ide, "nfe:dhEmi", agora), "iddest": _get_text(ide, "nfe:idDest", "1"),
            "cmunfg": _get_text(ide, "nfe:cMunFG", "4205407"), "tpimp": _get_text(ide, "nfe:tpImp", "1"),
            "tpemis": _get_text(ide, "nfe:tpEmis", "1"), "cdv": _get_text(ide, "nfe:cDV", "0"),
            "tpamb": _get_text(ide, "nfe:tpAmb", "1"),
            "vprod": float(_get_text(icms_tot, "nfe:vProd", "0")), "vnf": vnf
        }
    )

    return {
        "status": "IMPORTADA",
        "nnf": nnf,
        "fornecedor": fornecedor,
        "vnf": vnf,
        "motivo": f"{itens_novos} novo(s), {itens_atualizados} atualizado(s)"
    }


@importa_nfe_router.post("/upload")
async def importar_xmls_compra(
    arquivos: List[UploadFile] = File(...),
    margem_percentual: float = Form(40.0),
    session: Session = Depends(get_session)
):
    fator_margem = 1.0 + (margem_percentual / 100.0)
    resultados = []
    resumo = {"IMPORTADA": 0, "JA_IMPORTADA": 0, "IGNORADO": 0, "ERRO": 0}

    for arq in arquivos:
        if not arq.filename.lower().endswith(".xml"):
            continue
        try:
            conteudo = await arq.read()
            info = _processar_conteudo_xml(conteudo, session, fator_margem)
            session.commit()
            info["arquivo"] = arq.filename
            resultados.append(info)
            resumo[info["status"]] = resumo.get(info["status"], 0) + 1
        except Exception as e:
            session.rollback()
            resumo["ERRO"] += 1
            resultados.append({"arquivo": arq.filename, "status": "ERRO", "motivo": str(e)})

    return {"resumo": resumo, "resultados": resultados}

