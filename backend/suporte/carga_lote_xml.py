import os
import uuid
import sqlite3
import pymysql
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

NS = {'nfe': "http://" + "www.portalfiscal.inf.br" + "/nfe"}

# Configurações MySQL (mesmas do seu .env / database_unificado.py)
MYSQL_CFG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "Roberto"),
    "password": os.getenv("MYSQL_PASSWORD", "rlp562@"),
    "database": os.getenv("MYSQL_DATABASE", "pdv_cpa"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "charset": "utf8mb4"
}

SQLITE_PATH = r"D:\cpa\pdv_cpa.db"
CNPJ_NOSSA_LOJA = "03540677000100"

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

def executar_sql(cursor, is_mysql, query_sqlite, params=()):
    """Adapta automaticamente placeholders '?' (SQLite) para '%s' (MySQL)."""
    query = query_sqlite.replace("?", "%s") if is_mysql else query_sqlite
    cursor.execute(query, params)

def salvar_produto_no_banco(cursor, is_mysql, dados_prod, qtd_somar, agora):
    executar_sql(
        cursor, is_mysql,
        "SELECT id, estoque_atual FROM produto WHERE cprod = ? OR (cean IS NOT NULL AND cean = ?)",
        (dados_prod['cprod'], dados_prod['cean'])
    )
    row = cursor.fetchone()

    if row:
        prod_id = row[0]
        novo_estoque = float(row[1] or 0) + qtd_somar
        executar_sql(cursor, is_mysql, """
            UPDATE produto SET
                xprod = ?, ncm = ?, cest = ?, cfop_padrao = ?,
                ucom = ?, vuncom = ?, utrib = ?, vuntrib = ?,
                fator_conversao = ?, estoque_atual = ?, atualizado_em = ?
            WHERE id = ?
        """, (
            dados_prod['xprod'], dados_prod['ncm'], dados_prod['cest'], dados_prod['cfop_venda'],
            dados_prod['unidade'], dados_prod['preco_venda'], dados_prod['unidade'], dados_prod['preco_venda'],
            dados_prod['fator_conversao'], novo_estoque, agora, prod_id
        ))
    else:
        prod_id = str(uuid.uuid4())
        executar_sql(cursor, is_mysql, """
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
            prod_id, dados_prod['cprod'], dados_prod['cean'], dados_prod['xprod'],
            dados_prod['ncm'], dados_prod['cest'], dados_prod['cbenef'], dados_prod['cfop_venda'],
            dados_prod['unidade'], dados_prod['preco_venda'], dados_prod['cean'],
            dados_prod['unidade'], dados_prod['preco_venda'],
            dados_prod['fator_conversao'], qtd_somar,
            dados_prod['icms_orig'], dados_prod['icms_cst'], dados_prod['icms_picms'],
            dados_prod['pis_cst'], dados_prod['pis_ppis'],
            dados_prod['cofins_cst'], dados_prod['cofins_pcofins'],
            dados_prod['ibscbs_cst'], dados_prod['ibscbs_cclasstrib'],
            dados_prod['ibs_pibsuf'], dados_prod['cbs_pcbs'],
            agora
        ))
def processar_xml_em_conexao(caminho_xml, cursor, is_mysql, margem_lucro):
    tree = ET.parse(caminho_xml)
    root = tree.getroot()
    inf_nfe = root.find('.//nfe:infNFe', NS)

    if inf_nfe is None:
        return "IGNORADO_NAO_NFE"

    chnfe_atual = inf_nfe.attrib.get('Id', '').replace('NFe', '')
    dest = inf_nfe.find('nfe:dest', NS)
    cnpj_dest = get_text(dest, 'nfe:CNPJ') or get_text(dest, 'nfe:CPF')

    # Garante que só importa notas de compra destinadas à nossa loja
    if cnpj_dest != CNPJ_NOSSA_LOJA:
        return "IGNORADO_OUTRO_DEST"

    # Trava contra reimportação
    executar_sql(cursor, is_mysql, "SELECT id FROM nfe WHERE chnfe = ?", (chnfe_atual,))
    if cursor.fetchone():
        return "JA_IMPORTADA"

    agora = agora_iso()
    ender_dest = dest.find('nfe:enderDest', NS)

    # 1. Cadastra ou recupera Emitente (Loja)
    executar_sql(cursor, is_mysql, "SELECT id FROM emitente WHERE cnpj = ?", (cnpj_dest,))
    row_emit = cursor.fetchone()
    if row_emit:
        emitente_id = row_emit[0]
    else:
        emitente_id = str(uuid.uuid4())
        executar_sql(cursor, is_mysql, """
            INSERT INTO emitente (
                id, cnpj, xnome, xfant, xlgr, nro, xbairro, cmun, xmun, uf, cep, fone, ie, crt, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            emitente_id, cnpj_dest, get_text(dest, 'nfe:xNome')[:60], get_text(dest, 'nfe:xNome')[:60],
            get_text(ender_dest, 'nfe:xLgr')[:60], get_text(ender_dest, 'nfe:nro')[:60],
            get_text(ender_dest, 'nfe:xBairro')[:60], get_text(ender_dest, 'nfe:cMun'),
            get_text(ender_dest, 'nfe:xMun')[:60], get_text(ender_dest, 'nfe:UF'),
            get_text(ender_dest, 'nfe:CEP'), get_text(ender_dest, 'nfe:fone'),
            get_text(dest, 'nfe:IE'), '1', agora
        ))

    # 2. Processa Itens (com regra dupla CX / CD + Unidade)
    for det in inf_nfe.findall('nfe:det', NS):
        prod = det.find('nfe:prod', NS)
        imposto = det.find('nfe:imposto', NS)

        cprod_forn = get_text(prod, 'nfe:cProd')
        xprod = get_text(prod, 'nfe:xProd')
        ncm = get_text(prod, 'nfe:NCM')
        cest = get_text(prod, 'nfe:CEST')
        cbenef = get_text(prod, 'nfe:cBenef')
        cfop_compra = get_text(prod, 'nfe:CFOP')

        u_com = get_text(prod, 'nfe:uCom', '').upper()
        u_trib = get_text(prod, 'nfe:uTrib', '').upper()
        c_ean = get_text(prod, 'nfe:cEAN')
        c_ean_trib = get_text(prod, 'nfe:cEANTrib')

        ean_cx = c_ean if c_ean and c_ean != 'SEM GTIN' else None
        ean_un = c_ean_trib if c_ean_trib and c_ean_trib != 'SEM GTIN' else None

        q_com = float(get_text(prod, 'nfe:qCom', '1'))
        q_trib = float(get_text(prod, 'nfe:qTrib', '1'))
        v_prod_total = float(get_text(prod, 'nfe:vProd', '0'))

        icms_node = imposto.find('.//nfe:ICMS/*', NS)
        icms_orig = get_text(icms_node, 'nfe:orig', '0')
        icms_cst = get_text(icms_node, 'nfe:CST') or get_text(icms_node, 'nfe:CSOSN') or '102'
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

        base_tributos = {
            'ncm': ncm, 'cest': cest, 'cbenef': cbenef, 'cfop_venda': cfop_venda,
            'icms_orig': icms_orig, 'icms_cst': icms_cst, 'icms_picms': icms_picms,
            'pis_cst': pis_cst, 'pis_ppis': pis_ppis,
            'cofins_cst': cofins_cst, 'cofins_pcofins': cofins_pcofins,
            'ibscbs_cst': ibscbs_cst, 'ibscbs_cclasstrib': ibscbs_cclasstrib,
            'ibs_pibsuf': ibs_pibsuf, 'cbs_pcbs': cbs_pcbs
        }

        fator_conv = round(q_trib / q_com, 4) if q_com > 0 else 1.0
        qtd_total_un = q_com * fator_conv

        if u_com in ('CX', 'CD') and ean_cx and ean_un and ean_cx != ean_un:
            custo_un = v_prod_total / qtd_total_un if qtd_total_un > 0 else 0.0
            prod_un = {
                **base_tributos, 'cprod': cprod_forn, 'cean': ean_un,
                'xprod': xprod[:120], 'unidade': u_trib if u_trib not in ('CX', 'CD') else 'UN',
                'preco_venda': round(custo_un * margem_lucro, 2), 'fator_conversao': 1.0
            }
            salvar_produto_no_banco(cursor, is_mysql, prod_un, qtd_total_un, agora)

            custo_cx = v_prod_total / q_com if q_com > 0 else 0.0
            prod_cx = {
                **base_tributos, 'cprod': f"{cprod_forn}-{u_com}", 'cean': ean_cx,
                'xprod': f"{xprod[:110]} ({u_com})", 'unidade': u_com,
                'preco_venda': round(custo_cx * margem_lucro, 2), 'fator_conversao': fator_conv
            }
            salvar_produto_no_banco(cursor, is_mysql, prod_cx, 0.0, agora)
        else:
            ean_final = ean_un if (u_com in ('CX', 'CD') and ean_un) else (ean_cx or ean_un)
            unidade_final = u_trib if (u_com in ('CX', 'CD') and u_trib) else u_com
            custo_unit = v_prod_total / qtd_total_un if qtd_total_un > 0 else 0.0
            prod_unico = {
                **base_tributos, 'cprod': cprod_forn, 'cean': ean_final,
                'xprod': xprod[:120], 'unidade': unidade_final,
                'preco_venda': round(custo_unit * margem_lucro, 2), 'fator_conversao': fator_conv
            }
            salvar_produto_no_banco(cursor, is_mysql, prod_unico, qtd_total_un, agora)

    # 3. Registra Nota de Entrada
    ide = inf_nfe.find('nfe:ide', NS)
    icms_tot = inf_nfe.find('.//nfe:total/nfe:ICMSTot', NS)

    executar_sql(cursor, is_mysql, """
        INSERT INTO nfe (
            id, emitente_id, status_sefaz, sincronizado, chnfe, cuf, cnf, natop,
            modelo, serie, nnf, dhemi, tpnf, iddest, cmunfg, tpimp, tpemis, cdv, tpamb,
            vprod, vnf, modfrete
        ) VALUES (?, ?, 'AUTORIZADA', 1, ?, ?, ?, ?, ?, ?, ?, ?, '0', ?, ?, ?, ?, ?, ?, ?, ?, '0')
    """, (
        str(uuid.uuid4()), emitente_id, chnfe_atual,
        get_text(ide, 'nfe:cUF'), get_text(ide, 'nfe:cNF'), get_text(ide, 'nfe:natOp')[:60],
        get_text(ide, 'nfe:mod'), get_text(ide, 'nfe:serie'), int(get_text(ide, 'nfe:nNF')),
        get_text(ide, 'nfe:dhEmi'), get_text(ide, 'nfe:idDest'), get_text(ide, 'nfe:cMunFG'),
        get_text(ide, 'nfe:tpImp'), get_text(ide, 'nfe:tpEmis'), get_text(ide, 'nfe:cDV'),
        get_text(ide, 'nfe:tpAmb'), float(get_text(icms_tot, 'nfe:vProd', '0')),
        float(get_text(icms_tot, 'nfe:vNF', '0'))
    ))
    return "IMPORTADA"

def importar_diretorio_completo(diretorio_raiz, margem_lucro=1.40):
    arquivos_xml = []
    for root_dir, _, files in os.walk(diretorio_raiz):
        for f in files:
            if f.lower().endswith(".xml"):
                arquivos_xml.append(os.path.join(root_dir, f))

    print(f"Total de arquivos XML encontrados: {len(arquivos_xml)}\n")

    conn_sqlite = sqlite3.connect(SQLITE_PATH)
    conn_mysql = pymysql.connect(**MYSQL_CFG)

    stats = {"IMPORTADA": 0, "JA_IMPORTADA": 0, "IGNORADO_NAO_NFE": 0, "IGNORADO_OUTRO_DEST": 0, "ERRO": 0}

    for caminho in arquivos_xml:
        nome = os.path.basename(caminho)
        for nome_banco, conn, is_mysql in [("SQLite", conn_sqlite, False), ("MySQL", conn_mysql, True)]:
            cur = conn.cursor()
            try:
                status = processar_xml_em_conexao(caminho, cur, is_mysql, margem_lucro)
                conn.commit()
                if nome_banco == "MySQL":
                    stats[status] = stats.get(status, 0) + 1
                    if status == "IMPORTADA":
                        print(f"[OK] {nome} -> Importada no SQLite e MySQL")
            except Exception as e:
                conn.rollback()
                if nome_banco == "MySQL":
                    stats["ERRO"] += 1
                print(f"[ERRO {nome_banco}] {nome}: {e}")

    conn_sqlite.close()
    conn_mysql.close()
    print("\n=== RESUMO DA CARGA EM LOTE ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    pasta_notas = r"C:\Users\teste\Downloads\CPA_RADAR_03540677000100_PRODUCAO\03540677000100"
    importar_diretorio_completo(pasta_notas, margem_lucro=1.40)
