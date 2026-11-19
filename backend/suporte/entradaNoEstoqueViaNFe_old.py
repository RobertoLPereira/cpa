import xml.etree.ElementTree as ET
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta

NS = {'nfe': "http://" + "www.portalfiscal.inf.br" + "/nfe"}

def get_text(element, path, default=None):
    if element is None:
        return default
    found = element.find(path, NS)
    return found.text.strip() if found is not None and found.text else default

def agora_iso():
    fuso_br = timezone(timedelta(hours=-3))
    return datetime.now(fuso_br).strftime('%Y-%m-%dT%H:%M:%S%z')[:-2] + ':00'

def definir_cfop_venda(cfop_compra, icms_cst):
    if cfop_compra in ('5401', '5403', '5405', '6401', '6403') or icms_cst in ('60', '500'):
        return '5405'
    return '5102'

def importar_xml_compra_e_estoque(caminho_xml, db_path='pdv.db', margem_lucro=1.40):
    tree = ET.parse(caminho_xml)
    root = tree.getroot()
    inf_nfe = root.find('.//nfe:infNFe', NS)
    
    # Extrai a chave de acesso (removendo o prefixo 'NFe')
    chnfe_atual = inf_nfe.attrib.get('Id', '').replace('NFe', '')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    agora = agora_iso()

    try:
        # =====================================================================
        # 0. TRAVA DE SEGURANÇA: EVITA SOMAR ESTOQUE DUAS VEZES SE REIMPORTAR
        # =====================================================================
        cursor.execute("SELECT id FROM nfe WHERE chnfe = ?", (chnfe_atual,))
        if cursor.fetchone():
            print(f"[AVISO] A NF-e {chnfe_atual} já foi importada anteriormente. Operação cancelada para não duplicar estoque.")
            return

        # =====================================================================
        # 1. CADASTRAR A NOSSA LOJA COMO 'emitente' USANDO A TAG <dest> DO XML
        # =====================================================================
        dest = inf_nfe.find('nfe:dest', NS)
        ender_dest = dest.find('nfe:enderDest', NS)
        cnpj_loja = get_text(dest, 'nfe:CNPJ') or get_text(dest, 'nfe:CPF')
        
        cursor.execute("SELECT id FROM emitente WHERE cnpj = ?", (cnpj_loja,))
        row_emit = cursor.fetchone()
        
        if row_emit:
            emitente_id = row_emit
        else:
            emitente_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO emitente (
                    id, cnpj, xnome, xfant, xlgr, nro, xbairro, cmun, xmun, uf, cep, fone, ie, crt, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                emitente_id, cnpj_loja, get_text(dest, 'nfe:xNome'), get_text(dest, 'nfe:xNome'),
                get_text(ender_dest, 'nfe:xLgr'), get_text(ender_dest, 'nfe:nro'),
                get_text(ender_dest, 'nfe:xBairro'), get_text(ender_dest, 'nfe:cMun'),
                get_text(ender_dest, 'nfe:xMun'), get_text(ender_dest, 'nfe:UF'),
                get_text(ender_dest, 'nfe:CEP'), get_text(ender_dest, 'nfe:fone'),
                get_text(dest, 'nfe:IE'), '1', agora
            ))

        # =====================================================================
        # 2. PROCESSAR ITENS: CADASTRO, FATOR DE CONVERSÃO E ENTRADA NO ESTOQUE
        # =====================================================================
        itens = inf_nfe.findall('nfe:det', NS)
        
        for det in itens:
            prod = det.find('nfe:prod', NS)
            imposto = det.find('nfe:imposto', NS)

            cprod_fornecedor = get_text(prod, 'nfe:cProd')
            xprod = get_text(prod, 'nfe:xProd')
            ncm = get_text(prod, 'nfe:NCM')
            cest = get_text(prod, 'nfe:CEST')
            cbenef = get_text(prod, 'nfe:cBenef')
            cfop_compra = get_text(prod, 'nfe:CFOP')

            u_com = get_text(prod, 'nfe:uCom', '').upper()
            u_trib = get_text(prod, 'nfe:uTrib', '').upper()
            c_ean = get_text(prod, 'nfe:cEAN')
            c_ean_trib = get_text(prod, 'nfe:cEANTrib')

            q_com = float(get_text(prod, 'nfe:qCom', '1'))
            q_trib = float(get_text(prod, 'nfe:qTrib', '1'))
            v_prod_total = float(get_text(prod, 'nfe:vProd', '0'))

            # Regra: Se uCom == 'CX', EAN assume obrigatoriamente o cEANTrib
            if u_com == 'CX':
                ean_venda = c_ean_trib if c_ean_trib and c_ean_trib != 'SEM GTIN' else None
                unidade_venda = u_trib if u_trib else 'UN'
            else:
                ean_bruto = c_ean if c_ean and c_ean != 'SEM GTIN' else c_ean_trib
                ean_venda = ean_bruto if ean_bruto and ean_bruto != 'SEM GTIN' else None
                unidade_venda = u_com

            # Cálculo do Fator de Conversão e Quantidade Real de Entrada no Estoque
            fator_conversao = round(q_trib / q_com, 4) if q_com > 0 else 1.0
            qtd_entrada_estoque = q_com * fator_conversao  # Ex: 3 CX * 640 UN = 1920 UN

            # Custo unitário real na unidade de venda e preço sugerido
            custo_unitario = v_prod_total / qtd_entrada_estoque if qtd_entrada_estoque > 0 else 0.0
            preco_venda_sugerido = round(custo_unitario * margem_lucro, 2)

            # Extração dos Impostos
            icms_node = imposto.find('.//nfe:ICMS/*', NS)
            icms_orig = get_text(icms_node, 'nfe:orig', '0')
            icms_cst = get_text(icms_node, 'nfe:CST') or get_text(icms_node, 'nfe:CSOSN')
            icms_picms = float(get_text(icms_node, 'nfe:pICMS', '0'))

            pis_node = imposto.find('.//nfe:PIS/*', NS)
            pis_cst = get_text(pis_node, 'nfe:CST', '01')
            pis_ppis = float(get_text(pis_node, 'nfe:pPIS', '0'))

            cofins_node = imposto.find('.//nfe:COFINS/*', NS)
            cofins_cst = get_text(cofins_node, 'nfe:CST', '01')
            cofins_pcofins = float(get_text(cofins_node, 'nfe:pCOFINS', '0'))

            ibscbs_node = imposto.find('nfe:IBSCBS', NS)
            ibscbs_cst = get_text(ibscbs_node, 'nfe:CST', '000')
            ibscbs_cclasstrib = get_text(ibscbs_node, 'nfe:cClassTrib', '000001')
            ibs_pibsuf = float(get_text(ibscbs_node, './/nfe:pIBSUF', '0'))
            cbs_pcbs = float(get_text(ibscbs_node, './/nfe:pCBS', '0'))

            cfop_venda = definir_cfop_venda(cfop_compra, icms_cst)

            # Busca produto existente pelo EAN ou código
            cursor.execute(
                "SELECT id, estoque_atual FROM produto WHERE cprod = ? OR (cean IS NOT NULL AND cean = ?)", 
                (cprod_fornecedor, ean_venda)
            )
            row_prod = cursor.fetchone()

            if row_prod:
                prod_id, estoque_anterior = row_prod
                novo_estoque = float(estoque_anterior) + qtd_entrada_estoque
                
                cursor.execute("""
                    UPDATE produto SET 
                        xprod = ?, ncm = ?, cest = ?, cfop_padrao = ?,
                        fator_conversao = ?, estoque_atual = ?,
                        vuncom = ?, vuntrib = ?, atualizado_em = ?
                    WHERE id = ?
                """, (
                    xprod, ncm, cest, cfop_venda,
                    fator_conversao, novo_estoque,
                    preco_venda_sugerido, preco_venda_sugerido, agora, prod_id
                ))
                print(f"[ATUALIZADO] {xprod[:30]} | +{qtd_entrada_estoque} {unidade_venda} (Total: {novo_estoque})")
            else:
                prod_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO produto (
                        id, cprod, cean, xprod, ncm, cest, cbenef, cfop_padrao,
                        ucom, vuncom, ceantrib, utrib, vuntrib,
                        fator_conversao, estoque_atual,
                        icms_orig, icms_cst, icms_picms,
                        pis_cst, pis_ppis, cofins_cst, cofins_pcofins,
                        ibscbs_cst, ibscbs_cclasstrib, ibs_pibsuf, cbs_pcbs,
                        atualizado_em
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prod_id, cprod_fornecedor, ean_venda, xprod, ncm, cest, cbenef, cfop_venda,
                    unidade_venda, preco_venda_sugerido, ean_venda, unidade_venda, preco_venda_sugerido,
                    fator_conversao, qtd_entrada_estoque,
                    icms_orig, icms_cst, icms_picms,
                    pis_cst, pis_ppis, cofins_cst, cofins_pcofins,
                    ibscbs_cst, ibscbs_cclasstrib, ibs_pibsuf, cbs_pcbs,
                    agora
                ))
                print(f"[NOVO] {xprod[:30]} | Fator: {fator_conversao} | Estoque inicial: {qtd_entrada_estoque} {unidade_venda}")

        # =====================================================================
        # 3. REGISTRA O CABEÇALHO DA NOTA COMO ENTRADA (tpnf = '0') PARA HISTÓRICO
        # =====================================================================
        ide = inf_nfe.find('nfe:ide', NS)
        icms_tot = inf_nfe.find('.//nfe:total/nfe:ICMSTot', NS)
        
        cursor.execute("""
            INSERT INTO nfe (
                id, emitente_id, status_sefaz, sincronizado, chnfe, cuf, cnf, natop,
                modelo, serie, nnf, dhemi, tpnf, iddest, cmunfg, tpimp, tpemis, cdv, tpamb,
                vprod, vnf, modfrete
            ) VALUES (?, ?, 'AUTORIZADA', 0, ?, ?, ?, ?, ?, ?, ?, ?, '0', ?, ?, ?, ?, ?, ?, ?, ?, '0')
        """, (
            str(uuid.uuid4()), emitente_id, chnfe_atual,
            get_text(ide, 'nfe:cUF'), get_text(ide, 'nfe:cNF'), get_text(ide, 'nfe:natOp'),
            get_text(ide, 'nfe:mod'), get_text(ide, 'nfe:serie'), int(get_text(ide, 'nfe:nNF')),
            get_text(ide, 'nfe:dhEmi'), get_text(ide, 'nfe:idDest'), get_text(ide, 'nfe:cMunFG'),
            get_text(ide, 'nfe:tpImp'), get_text(ide, 'nfe:tpEmis'), get_text(ide, 'nfe:cDV'),
            get_text(ide, 'nfe:tpAmb'), float(get_text(icms_tot, 'nfe:vProd', '0')), float(get_text(icms_tot, 'nfe:vNF', '0'))))
        conn.commit()
        print("\nImportação concluída com sucesso!")
    except Exception as e:
            conn.rollback()
            print(f"Erro durante a importação: {e}")
    finally:
            conn.close()
if __name__ == "__main__":
    arquivo = 'C:\\Users\\teste\\Downloads\\CPA_RADAR_03540677000100_PRODUCAO\\03540677000100\\2026\\09\\43260943214055001502550000012398751898382811.xml'
    #importar_xml_compra_e_estoque('43260987315834000760550010003169701215247227.xml', db_path='d:\\cpa\\pdv_cpa.db', margem_lucro=1.40)
    #importar_xml_compra_e_estoque('43260987315834000760550010003169701215247227.xml', db_path='pdv_cpa.db', margem_lucro=1.40)
    importar_xml_compra_e_estoque(arquivo, db_path='pdv_cpa.db', margem_lucro=1.40)