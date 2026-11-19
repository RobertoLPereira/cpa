import sqlite3
from datetime import datetime, timezone, timedelta
from lxml import etree

#from assinador_sefaz import assinar_xml_nfe, gerar_qrcode_nfce
from backend.suporte.assinador_sefaz import assinar_xml_nfe, gerar_qrcode_nfce
from backend.suporte.gerador_xml import gerar_xml_nfe
from backend.suporte.transmissor_sefaz import transmitir_nfe_sefaz

NS_NFE = "http://" + "www.portalfiscal.inf.br" + "/nfe"

def agora_iso():
    fuso_br = timezone(timedelta(hours=-3))
    return datetime.now(fuso_br).strftime('%Y-%m-%dT%H:%M:%S%z')[:-2] + ':00'

def anexar_qrcode_no_xml(xml_assinado_str, url_qrcode, url_chave):
    """
    Insere a tag <infNFeSupl> após </Signature> (e antes de </NFe>)
    exigida pela SEFAZ para NFC-e (Modelo 65).
    """
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_assinado_str.encode("utf-8"), parser)
    
    # Remove se já existir para evitar duplicidade
    supl_antigo = root.find(f"{{{NS_NFE}}}infNFeSupl")
    if supl_antigo is not None:
        root.remove(supl_antigo)

    supl = etree.SubElement(root, f"{{{NS_NFE}}}infNFeSupl")
    el_qr = etree.SubElement(supl, f"{{{NS_NFE}}}qrCode")
    el_qr.text = etree.CDATA(url_qrcode)
    el_url = etree.SubElement(supl, f"{{{NS_NFE}}}urlChave")
    el_url.text = url_chave

    return etree.tostring(root, encoding="unicode")

def emitir_nota(nfe_id, caminho_pfx, senha_pfx, db_path='pdv.db'):
    """
    Orquestrador completo do PDV:
    1. Gera XML -> 2. Assina A1 -> 3. Gera QR Code (Mod 65) -> 4. Transmite SEFAZ
    5. Aciona Contingência Offline automaticamente se cair a internet (Mod 65).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Gera XML base e calcula Chave de Acesso
        xml_base = gerar_xml_nfe(nfe_id, db_path=db_path, salvar_arquivo=False)
        
        cursor.execute("SELECT * FROM nfe WHERE id = ?", (nfe_id,))
        nfe = cursor.fetchone()
        cursor.execute("SELECT * FROM emitente WHERE id = ?", (nfe['emitente_id'],))
        emit = cursor.fetchone()

        # 2. Assina digitalmente com Certificado A1
        xml_assinado = assinar_xml_nfe(xml_base, caminho_pfx, senha_pfx)

        # 3. Se for NFC-e (Mod 65), gera e injeta o QR Code 2.00
        if nfe['modelo'] == '65':
            url_qr, url_chave = gerar_qrcode_nfce(nfe, emit, xml_assinado)
            xml_assinado = anexar_qrcode_no_xml(xml_assinado, url_qr, url_chave)
            cursor.execute(
                "UPDATE nfe SET qrcode = ?, urlchave = ? WHERE id = ?",
                (url_qr, url_chave, nfe_id)
            )
            conn.commit()

        # 4. Transmite para a SEFAZ (RS / SVRS-SC)
        res = transmitir_nfe_sefaz(
            xml_assinado, nfe['cuf'], nfe['modelo'], nfe['tpamb'], caminho_pfx, senha_pfx
        )

        # Cenário A: Autorizada na hora (cStat 100)
        if res['sucesso']:
            cursor.execute("""
                UPDATE nfe SET
                    status_sefaz = 'AUTORIZADA',
                    cstat = ?, xmotivo = ?, nprot = ?, dhrecbto = ?,
                    xml_completo = ?, sincronizado = 0
                WHERE id = ?
            """, (res['cstat'], res['xmotivo'], res['nprot'], res['dhrecbto'], res['xml_autorizado'], nfe_id))
            conn.commit()
            return {"status": "AUTORIZADA", "nprot": res['nprot'], "xml": res['xml_autorizado']}

        # Cenário B: Sem Internet / Timeout -> Contingência Offline (Apenas Mod 65)
        if res['erro_rede']:
            if nfe['modelo'] == '65':
                return _acionar_contingencia_offline(conn, cursor, nfe_id, caminho_pfx, senha_pfx, db_path)
            else:
                cursor.execute(
                    "UPDATE nfe SET status_sefaz = 'PENDENTE', xmotivo = ? WHERE id = ?",
                    (res['xmotivo'], nfe_id)
                )
                conn.commit()
                return {"status": "OFFLINE_MOD55", "mensagem": "NF-e Modelo 55 exige conexão com a internet."}

        # Cenário C: Rejeição Fiscal (Erro de preenchimento/tributação)
        cursor.execute("""
            UPDATE nfe SET
                status_sefaz = 'REJEITADA', cstat = ?, xmotivo = ?, sincronizado = 0
            WHERE id = ?
        """, (res['cstat'], res['xmotivo'], nfe_id))
        conn.commit()
        return {"status": "REJEITADA", "cstat": res['cstat'], "motivo": res['xmotivo']}

    finally:
        conn.close()
def _acionar_contingencia_offline(conn, cursor, nfe_id, caminho_pfx, senha_pfx, db_path):
    """
    Converte a NFC-e para Contingência Offline (tpEmis = 9),
    recalcula Chave + Assinatura + QR Code e libera o caixa imediatamente.
    """
    dh_cont = agora_iso()
    justificativa = "Falha de comunicacao com a SEFAZ no momento da venda no PDV"

    # Limpa chnfe para forçar recálculo da chave com tpEmis = '9'
    cursor.execute("""
        UPDATE nfe SET
            tpemis = '9',
            dhcont = ?,
            xjust = ?,
            chnfe = NULL,
            cdv = NULL
        WHERE id = ?
    """, (dh_cont, justificativa, nfe_id))
    conn.commit()

    # Regera XML e nova Chave de Acesso contendo tpEmis = 9
    xml_cont = gerar_xml_nfe(nfe_id, db_path=db_path, salvar_arquivo=False)
    
    cursor.execute("SELECT * FROM nfe WHERE id = ?", (nfe_id,))
    nfe_cont = cursor.fetchone()
    cursor.execute("SELECT * FROM emitente WHERE id = ?", (nfe_cont['emitente_id'],))
    emit = cursor.fetchone()

    # Assina o XML de contingência e gera QR Code com DigestValue em Hex
    xml_assinado_cont = assinar_xml_nfe(xml_cont, caminho_pfx, senha_pfx)
    url_qr, url_chave = gerar_qrcode_nfce(nfe_cont, emit, xml_assinado_cont)
    xml_final_cont = anexar_qrcode_no_xml(xml_assinado_cont, url_qr, url_chave)

    cursor.execute("""
        UPDATE nfe SET
            status_sefaz = 'CONTINGENCIA',
            qrcode = ?,
            urlchave = ?,
            xml_completo = ?,
            sincronizado = 0
        WHERE id = ?
    """, (url_qr, url_chave, xml_final_cont, nfe_id))
    conn.commit()

    return {
        "status": "CONTINGENCIA",
        "chnfe": nfe_cont['chnfe'],
        "xml": xml_final_cont,
        "mensagem": "NFC-e emitida em Contingência Offline. Imprimir DANFE em 2 vias."
    }
