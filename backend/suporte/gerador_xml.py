import sqlite3
from sqlmodel import Session, text
import xml.etree.ElementTree as ET
from backend.suporte.xml_helpers import NS_NFE, add_el, fmt_2, gerar_chave_acesso, montar_cabecalho
from backend.suporte.xml_itens import montar_itens

def montar_rodape(nfe_root, inf_nfe, nfe, dups, pags):
    # Grupo <total>
    total = ET.SubElement(inf_nfe, "total")
    icms_tot = ET.SubElement(total, "ICMSTot")
    campos_tot = [
        ("vBC", 'vbc'), ("vICMS", 'vicms'), ("vICMSDeson", 'vicmsdeson'),
        ("vFCPUFDest", 'vfcpufdest'), ("vICMSUFRemet", 'vicmsufremet'),
        ("vFCP", 'vfcp'), ("vBCST", 'vbcst'), ("vST", 'vst'),
        ("vFCPST", 'vfcpst'), ("vFCPSTRet", 'vfcpstret'), ("vProd", 'vprod'),
        ("vFrete", 'vfrete'), ("vSeg", 'vseg'), ("vDesc", 'vdesc'),
        ("vII", 'vii'), ("vIPI", 'vipi'), ("vIPIDevol", 'vipidevol'),
        ("vPIS", 'vpis'), ("vCOFINS", 'vcofins'), ("vOutro", 'voutro'), ("vNF", 'vnf')
    ]
    for tag, col in campos_tot:
        add_el(icms_tot, tag, fmt_2(nfe[col]))

    if nfe['vbcibscbs'] and float(nfe['vbcibscbs']) > 0:
        ibscbs_tot = ET.SubElement(total, "IBSCBSTot")
        add_el(ibscbs_tot, "vBCIBSCBS", fmt_2(nfe['vbcibscbs']))
        gibs = ET.SubElement(ibscbs_tot, "gIBS")
        gibsuf = ET.SubElement(gibs, "gIBSUF")
        add_el(gibsuf, "vDif", "0.00")
        add_el(gibsuf, "vDevTrib", "0.00")
        add_el(gibsuf, "vIBSUF", fmt_2(nfe['vibsuf']))
        gibsmun = ET.SubElement(gibs, "gIBSMun")
        add_el(gibsmun, "vDif", "0.00")
        add_el(gibsmun, "vDevTrib", "0.00")
        add_el(gibsmun, "vIBSMun", fmt_2(nfe['vibsmun']))
        add_el(gibs, "vIBS", fmt_2(nfe['vibs']))
        add_el(gibs, "vCredPres", "0.00")
        add_el(gibs, "vCredPresCondSus", "0.00")
        
        gcbs = ET.SubElement(ibscbs_tot, "gCBS")
        add_el(gcbs, "vDif", "0.00")
        add_el(gcbs, "vDevTrib", "0.00")
        add_el(gcbs, "vCBS", fmt_2(nfe['vcbs']))
        add_el(gcbs, "vCredPres", "0.00")
        add_el(gcbs, "vCredPresCondSus", "0.00")
        add_el(total, "vNFTot", fmt_2(nfe['vnf']))

    # Grupo <transp>
    transp = ET.SubElement(inf_nfe, "transp")
    add_el(transp, "modFrete", nfe['modfrete'] or "9")
    if nfe['modelo'] == '55' and nfe['transp_xnome']:
        transporta = ET.SubElement(transp, "transporta")
        add_el(transporta, "CNPJ", nfe['transp_cnpj'])
        add_el(transporta, "xNome", nfe['transp_xnome'])
        add_el(transporta, "IE", nfe['transp_ie'])
        add_el(transporta, "xEnder", nfe['transp_xender'])
        add_el(transporta, "xMun", nfe['transp_xmun'])
        add_el(transporta, "UF", nfe['transp_uf'])

    # Grupo <cobr> (Mod 55)
    if nfe['modelo'] == '55' and dups:
        cobr = ET.SubElement(inf_nfe, "cobr")
        fat = ET.SubElement(cobr, "fat")
        add_el(fat, "nFat", dups[0]['nfat'] or str(nfe['nnf']))
        add_el(fat, "vOrig", fmt_2(nfe['vnf']))
        add_el(fat, "vDesc", "0.00")
        add_el(fat, "vLiq", fmt_2(nfe['vnf']))
        for d in dups:
            dup = ET.SubElement(cobr, "dup")
            add_el(dup, "nDup", d['ndup'])
            add_el(dup, "dVenc", d['dvenc'])
            add_el(dup, "vDup", fmt_2(d['vdup']))

    # Grupo <pag>
    pag = ET.SubElement(inf_nfe, "pag")
    for p in pags:
        det_pag = ET.SubElement(pag, "detPag")
        add_el(det_pag, "indPag", p['indpag'] or "0")
        add_el(det_pag, "tPag", p['tpag'])
        add_el(det_pag, "vPag", fmt_2(p['vpag']))
        if p['tpag'] in ('03', '04', '17') and p['tpintegra']:
            card = ET.SubElement(det_pag, "card")
            add_el(card, "tpIntegra", p['tpintegra'])
            if p['cnpj_credenciadora']:
                add_el(card, "CNPJ", p['cnpj_credenciadora'])
            if p['tband']:
                add_el(card, "tBand", p['tband'])
            if p['caut']:
                add_el(card, "cAut", p['caut'])
    
    if pags and pags[0]['vtroco'] and float(pags[0]['vtroco']) > 0:
        add_el(pag, "vTroco", fmt_2(pags[0]['vtroco']))

    # Grupo <infAdic> e <infNFeSupl>
    if nfe['infcpl']:
        inf_adic = ET.SubElement(inf_nfe, "infAdic")
        add_el(inf_adic, "infCpl", nfe['infcpl'])

    if nfe['modelo'] == '65' and nfe['qrcode']:
        supl = ET.SubElement(nfe_root, "infNFeSupl")
        add_el(supl, "qrCode", nfe['qrcode'])
        add_el(supl, "urlChave", nfe['urlchave'])

def _row_to_dict(row):
    """Converte o retorno da query SQLAlchemy em dicionário compatível com os helpers."""
    return dict(row._mapping) if row is not None else None

def gerar_xml_nfe(nfe_id: str, session: Session, salvar_arquivo: bool = False) -> str:
    nfe_row = session.exec(text("SELECT * FROM nfe WHERE id = :id"), params={"id": nfe_id}).first()
    if not nfe_row:
        raise ValueError(f"Nota {nfe_id} não encontrada no banco ativo.")
    nfe = _row_to_dict(nfe_row)

    emit_row = session.exec(text("SELECT * FROM emitente WHERE id = :id"), params={"id": nfe['emitente_id']}).first()
    emit = _row_to_dict(emit_row)

    dest = None
    if nfe['destinatario_id']:
        dest_row = session.exec(text("SELECT * FROM destinatario WHERE id = :id"), params={"id": nfe['destinatario_id']}).first()
        dest = _row_to_dict(dest_row)

    itens_rows = session.exec(text("""
        SELECT i.*, imp.* FROM nfe_item i
        LEFT JOIN nfe_item_imposto imp ON imp.nfe_item_id = i.id
        WHERE i.nfe_id = :id ORDER BY i.nitem ASC
    """), params={"id": nfe_id}).all()
    itens = [_row_to_dict(r) for r in itens_rows]

    dups_rows = session.exec(text("SELECT * FROM nfe_duplicata WHERE nfe_id = :id ORDER BY ndup ASC"), params={"id": nfe_id}).all()
    dups = [_row_to_dict(r) for r in dups_rows]

    pags_rows = session.exec(text("SELECT * FROM nfe_pagamento WHERE nfe_id = :id"), params={"id": nfe_id}).all()
    pags = [_row_to_dict(r) for r in pags_rows]

    chnfe, cdv = gerar_chave_acesso(nfe, emit)

    ET.register_namespace('', NS_NFE)
    nfe_root = ET.Element(f"{{{NS_NFE}}}NFe")
    inf_nfe = ET.SubElement(nfe_root, "infNFe", {
        "Id": f"NFe{chnfe}",
        "versao": nfe['versao'] or "4.00"
    })

    montar_cabecalho(inf_nfe, nfe, emit, dest, cdv)
    montar_itens(inf_nfe, itens, nfe['modelo'], crt=emit['crt'], tpamb=nfe['tpamb'])
    montar_rodape(nfe_root, inf_nfe, nfe, dups, pags)

    xml_str = ET.tostring(nfe_root, encoding='unicode')

    # Atualiza chave, dígito verificador e salva o XML gerado na tabela nfe
    session.exec(
        text("UPDATE nfe SET chnfe = :ch, cdv = :dv, xml_completo = :xml WHERE id = :id"),
        params={"ch": chnfe, "dv": cdv, "xml": xml_str, "id": nfe_id}
    )
    session.commit()

    if salvar_arquivo:
        with open(f"NFe{chnfe}-nao-assinada.xml", "w", encoding="utf-8") as f:
            f.write(xml_str)

    return xml_str
