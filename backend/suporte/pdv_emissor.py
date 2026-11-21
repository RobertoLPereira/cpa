from datetime import datetime, timezone, timedelta
from lxml import etree
from sqlmodel import Session, text

from backend.suporte.gerador_xml import gerar_xml_nfe
from backend.suporte.assinador_sefaz import assinar_xml_nfe, gerar_qrcode_nfce
from backend.suporte.transmissor_sefaz import transmitir_nfe_sefaz

NS_NFE = "http://" + "www.portalfiscal.inf.br" + "/nfe"

def agora_iso():
    fuso_br = timezone(timedelta(hours=-3))
    return datetime.now(fuso_br).strftime('%Y-%m-%dT%H:%M:%S%z')[:-2] + ':00'

def anexar_qrcode_no_xml(xml_assinado_str, url_qrcode, url_chave):
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_assinado_str.encode("utf-8"), parser)
    
    supl_antigo = root.find(f"{{{NS_NFE}}}infNFeSupl")
    if supl_antigo is not None:
        root.remove(supl_antigo)

    supl = etree.SubElement(root, f"{{{NS_NFE}}}infNFeSupl")
    el_qr = etree.SubElement(supl, f"{{{NS_NFE}}}qrCode")
    el_qr.text = etree.CDATA(url_qrcode)
    el_url = etree.SubElement(supl, f"{{{NS_NFE}}}urlChave")
    el_url.text = url_chave

    return etree.tostring(root, encoding="unicode")

def emitir_nota(nfe_id: str, caminho_pfx: str, senha_pfx: str, session: Session):
    # 1. Gera XML base e calcula Chave de Acesso
    xml_base = gerar_xml_nfe(nfe_id, session=session, salvar_arquivo=False)
    
    nfe = dict(session.exec(text("SELECT * FROM nfe WHERE id = :id"), params={"id": nfe_id}).first()._mapping)
    emit = dict(session.exec(text("SELECT * FROM emitente WHERE id = :id"), params={"id": nfe['emitente_id']}).first()._mapping)

    # 2. Assina digitalmente com Certificado A1 (.pfx)
    xml_assinado = assinar_xml_nfe(xml_base, caminho_pfx, senha_pfx)

    # 3. Se for NFC-e (Mod 65), gera e injeta o QR Code 2.00
    if str(nfe['modelo']) == '65':
        if not emit.get('csc_id') or not emit.get('csc_token'):
            raise ValueError("CSC_ID e CSC_TOKEN nao configurados na tabela emitente para NFC-e.")
        url_qr, url_chave = gerar_qrcode_nfce(nfe, emit, xml_assinado)
        xml_assinado = anexar_qrcode_no_xml(xml_assinado, url_qr, url_chave)
        session.exec(
            text("UPDATE nfe SET qrcode = :qr, urlchave = :url WHERE id = :id"),
            params={"qr": url_qr, "url": url_chave, "id": nfe_id}
        )
        session.commit()

    # 4. Transmite para a SEFAZ
    res = transmitir_nfe_sefaz(
        xml_assinado, nfe['cuf'], nfe['modelo'], nfe['tpamb'], caminho_pfx, senha_pfx
    )

    # Cenário A: Autorizada (cStat 100)
    if res['sucesso']:
        session.exec(text("""
            UPDATE nfe SET
                status_sefaz = 'AUTORIZADA',
                cstat = :cstat, xmotivo = :xmotivo, nprot = :nprot, dhrecbto = :dhrecbto,
                xml_completo = :xml, sincronizado = 0
            WHERE id = :id
        """), params={
            "cstat": res['cstat'], "xmotivo": res['xmotivo'], "nprot": res['nprot'],
            "dhrecbto": res['dhrecbto'], "xml": res['xml_autorizado'], "id": nfe_id
        })
        session.commit()
        return {"status": "AUTORIZADA", "nprot": res['nprot'], "xml": res['xml_autorizado']}

    # Cenário B: Sem Internet -> Contingência Offline (Apenas Mod 65)
    if res['erro_rede'] and str(nfe['modelo']) == '65':
        dh_cont = agora_iso()
        just = "Falha de comunicacao com a SEFAZ no momento da venda no PDV"
        session.exec(text("""
            UPDATE nfe SET tpemis = '9', dhcont = :dh, xjust = :just, chnfe = NULL, cdv = NULL WHERE id = :id
        """), params={"dh": dh_cont, "just": just, "id": nfe_id})
        session.commit()

        xml_cont = gerar_xml_nfe(nfe_id, session=session, salvar_arquivo=False)
        nfe_cont = dict(session.exec(text("SELECT * FROM nfe WHERE id = :id"), params={"id": nfe_id}).first()._mapping)
        xml_ass_cont = assinar_xml_nfe(xml_cont, caminho_pfx, senha_pfx)
        url_qr, url_chave = gerar_qrcode_nfce(nfe_cont, emit, xml_ass_cont)
        xml_final_cont = anexar_qrcode_no_xml(xml_ass_cont, url_qr, url_chave)

        session.exec(text("""
            UPDATE nfe SET status_sefaz = 'CONTINGENCIA', qrcode = :qr, urlchave = :url, xml_completo = :xml, sincronizado = 0 WHERE id = :id
        """), params={"qr": url_qr, "url": url_chave, "xml": xml_final_cont, "id": nfe_id})
        session.commit()
        return {"status": "CONTINGENCIA", "chnfe": nfe_cont['chnfe'], "xml": xml_final_cont}

    # Cenário C: Rejeição Fiscal
    session.exec(text("""
        UPDATE nfe SET status_sefaz = 'REJEITADA', cstat = :cstat, xmotivo = :xmotivo, sincronizado = 0 WHERE id = :id
    """), params={"cstat": res['cstat'], "xmotivo": res['xmotivo'], "id": nfe_id})
    session.commit()
    return {"status": "REJEITADA", "cstat": res['cstat'], "motivo": res['xmotivo']}
