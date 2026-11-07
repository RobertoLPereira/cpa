from fastapi import FastAPI, HTTPException,BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from fastapi.responses import Response
from lxml import etree
from signxml import XMLSigner, methods
from backend.core.database_sqlite import obter_conexao, inicializar_banco_gerente
from backend.core.core_fiscal_sqlite import calcular_item_cupom,generar_string_xml_ibscbs,dar_baixa_estoque_lote,processar_lote_perdas_estorno
from backend.models.sqlite.models import CarrinhoInput, ItemMMySQL, ItemPerda, NotaInput

inicializar_banco_gerente()

app = FastAPI(
    title="API Central do Gerente Fiscal - Software House",
    description="Motor de validação e homologação do IVA Dual (LC 214/2025) e IBPT",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/v1/retaguarda/produtos/importar-lote")
def importar_lote_mysql_json(produtos: List[ItemMMySQL]):
    conn = obter_conexao()
    cursor = conn.cursor()
    contador = 0
    for p in produtos:
        ncm_limpo = p.ncm.replace(".", "").replace("/", "").strip() if p.ncm else "00000000"
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO produtos 
                (id_produto, nome_produto, ncm, preco_venda, estoque_atual, situacao)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (p.id_produto, p.nome_produto, ncm_limpo, p.preco_venda, p.estoque_atual, p.situacao))
            contador += 1
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=400, detail=f"Erro ao processar item {p.id_produto}: {e}")
    conn.commit()
    conn.close()
    return {"status": "sucesso", "mensagem": f"{contador} produtos importados e higienizados."}

@app.post("/api/v1/retaguarda/matriz/sincronizar")
def sincronizar_matriz_lote():
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE produtos
        SET 
            cst_iva_dual = (
                SELECT cst_ibs_cbs FROM ref_matriz_fiscal_ncm 
                WHERE ref_matriz_fiscal_ncm.ncm_codigo = REPLACE(produtos.ncm, '.', '')
                   OR REPLACE(produtos.ncm, '.', '') LIKE ref_matriz_fiscal_ncm.ncm_codigo || '%'
                LIMIT 1
            ),
            cclass_trib = (
                SELECT cclass_trib FROM ref_matriz_fiscal_ncm 
                WHERE ref_matriz_fiscal_ncm.ncm_codigo = REPLACE(produtos.ncm, '.', '')
                   OR REPLACE(produtos.ncm, '.', '') LIKE ref_matriz_fiscal_ncm.ncm_codigo || '%'
                LIMIT 1
            ),
            ind_monofasico = (
                SELECT m.ind_gIBSCBSMono 
                FROM ref_iva_cst_matriz m
                WHERE m.cst_ibs_cbs = (
                    SELECT cst_ibs_cbs FROM ref_matriz_fiscal_ncm 
                    WHERE ref_matriz_fiscal_ncm.ncm_codigo = REPLACE(produtos.ncm, '.', '')
                       OR REPLACE(produtos.ncm, '.', '') LIKE ref_matriz_fiscal_ncm.ncm_codigo || '%'
                    LIMIT 1
                )
            ),
            ibpt_fed = (
                SELECT ibpt_nacional_federal FROM ref_matriz_fiscal_ncm 
                WHERE ref_matriz_fiscal_ncm.ncm_codigo = REPLACE(produtos.ncm, '.', '')
                   OR REPLACE(produtos.ncm, '.', '') LIKE ref_matriz_fiscal_ncm.ncm_codigo || '%'
                LIMIT 1
            ),
            ibpt_est = (
                SELECT ibpt_estadual FROM ref_matriz_fiscal_ncm 
                WHERE ref_matriz_fiscal_ncm.ncm_codigo = REPLACE(produtos.ncm, '.', '')
                   OR REPLACE(produtos.ncm, '.', '') LIKE ref_matriz_fiscal_ncm.ncm_codigo || '%'
                LIMIT 1
            )
        WHERE EXISTS (
            SELECT 1 FROM ref_matriz_fiscal_ncm 
            WHERE ref_matriz_fiscal_ncm.ncm_codigo = REPLACE(produtos.ncm, '.', '')
               OR REPLACE(produtos.ncm, '.', '') LIKE ref_matriz_fiscal_ncm.ncm_codigo || '%'
        );
    """)
    cursor.execute("UPDATE produtos SET ncm = REPLACE(ncm, '.', '');")
    conn.commit()
    conn.close()
    return {"status": "sucesso", "mensagem": "Tabela mestre higienizada e sincronizada com sucesso com a matriz fiscal!"}

# 2. ROTINA DE SEGUNDO PLANO PARA ATUALIZAÇÃO AUTOMÁTICA DE CADASTROS ZERADOS
def atualizar_preco_produto_background(id_produto: str, novo_preco: float):
    """
    Atualiza o campo preco_venda na tabela de produtos em segundo plano,
    caso o valor anterior estivesse zerado no banco de dados.
    """
    try:
        conn = obter_conexao()
        cursor = conn.cursor()
        
        # Verifica se o preço atual realmente é nulo ou zerado antes de sobrescrever
        cursor.execute("SELECT preco_venda FROM produtos WHERE id_produto = ?;", (id_produto,))
        produto = cursor.fetchone()
        
        if produto and (produto["preco_venda"] is None or float(produto["preco_venda"]) == 0.0):
            cursor.execute("""
                UPDATE produtos 
                SET preco_venda = ? 
                WHERE id_produto = ?;
            """, (novo_preco, id_produto))
            conn.commit()
            print(f"DEBUG FISCAL [Background] - Preço do produto {id_produto} atualizado automaticamente de R$ 0.00 para R$ {novo_preco:.2f}")
            
        conn.close()
    except Exception as e:
        print(f"ALERTA FISCAL [Background] - Falha ao atualizar preço dinâmico do produto {id_produto}: {e}")

@app.post("/api/v1/caixa/calcular-cupom")
def calcular_e_finalizar_cupom_caixa(carrinho: CarrinhoInput, background_tasks: BackgroundTasks):
    itens_aprovados = []
    itens_bloqueados = []
    subtotal_produtos = 0.0
    total_ibs = 0.0
    total_cbs = 0.0
    total_ibpt_fed = 0.0
    total_ibpt_est = 0.0
    
    for item in carrinho.itens_carrinho:
        # Passa a quantidade e preço coletados no caixa para o cálculo atômico
        res = calcular_item_cupom(
            codigo_lido=item.codigo,
            qtd_caixa=item.quantidade,
            preco_caixa=item.preco_contingencia
        )
        
        if res["status"] in ["BLOQUEADO", "REJEITADO"]:
            itens_bloqueados.append(res)
        else:
            res["xml_string_sefaz"] = generar_string_xml_ibscbs(res)
            itens_aprovados.append(res)
            
            subtotal_produtos += res["vProd"]
            total_ibs += res["IBSCBS"]["vIBS"]
            total_cbs += res["IBSCBS"]["vCBS"]
            total_ibpt_fed += res["ibpt"]["vFed"]
            total_ibpt_est += res["ibpt"]["vEst"]
            
            # Se a flag de contingência foi disparada, atualiza o preço zerado em background
            if res.get("forcou_contingencia"):
                background_tasks.add_task(atualizar_preco_produto_background, res["id_produto"], item.preco_contingencia)
            
    if itens_aprovados:
        dar_baixa_estoque_lote(itens_aprovados)
        
    return {
        "resumo": {
            "vProd": round(subtotal_produtos, 2),
            "vIBS_Total": round(total_ibs, 2),
            "vCBS_Total": round(total_cbs, 2),
            "vNF": round(subtotal_produtos, 2),
            "ibpt_total_fed": round(total_ibpt_fed, 2),
            "ibpt_total_est": round(total_ibpt_est, 2),
            "vTotTrib": round(total_ibpt_fed + total_ibpt_est, 2)
        },
        "itens_aprovados": itens_aprovados,
        "itens_bloqueados": itens_bloqueados
    }


@app.get("/api/v1/auditoria/inconsistencias")
def emitir_relatorio_inconsistencias():
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM auditoria_produtos_falhas;")
    cursor.execute("SELECT id_produto, nome_produto, ncm, preco_venda, cst_iva_dual FROM produtos;")
    produtos = cursor.fetchall()
    for p in produtos:
        if float(p["preco_venda"] or 0) == 0.0:
            cursor.execute("""
                INSERT INTO auditoria_produtos_falhas (id_produto, nome_produto, ncm, tipo_inconsistencia, detalhe_erro)
                VALUES (?, ?, ?, 'PREÇO ZERADO', 'Produto ativo comercialmente sem preço de venda definido.');
            """, (p["id_produto"], p["nome_produto"], p["ncm"]))
        elif p["cst_iva_dual"] is None:
            cursor.execute("""
                INSERT INTO auditoria_produtos_falhas (id_produto, nome_produto, ncm, tipo_inconsistencia, detalhe_erro)
                VALUES (?, ?, ?, 'IVA DUAL INCOMPLETO', 'NCM sem amarração correspondente no Catálogo da SEFAZ.');
            """, (p["id_produto"], p["nome_produto"], p["ncm"]))
    cursor.execute("SELECT id_produto, nome_produto, ncm, tipo_inconsistencia, detalhe_erro FROM auditoria_produtos_falhas;")
    falhas = [dict(row) for row in cursor.fetchall()]
    conn.commit()
    conn.close()
    return {"inconsistencias": falhas}

@app.post("/api/v1/retaguarda/estoque/processar-perdas")
def post_processar_lote_perdas(lote: List[ItemPerda]):    
    lote_dicts = [item.model_dump() for item in lote]
    resultado = processar_lote_perdas_estorno(lote_dicts)
    return {"status": "sucesso", "operacoes_estorno": resultado}

def assinar_xml_nfe(caminho_xml_origem: str, caminho_pfx: str, senha_pfx: str):
    """
    Assina digitalmente o arquivo XML da NF-e no padrão ICP-Brasil (XMLDSig).
    """
    if not os.path.exists(caminho_xml_origem):
        raise FileNotFoundError(f"Arquivo XML não localizado: {caminho_xml_origem}")
        
    # 1. Carrega o certificado digital A1 e a chave privada
    # Nota: Em sistemas de produção, utilize bibliotecas como cryptography para extrair do PFX
    from cryptography.hazmat.primitives.serialization import pkcs12
    
    with open(caminho_pfx, "rb") as f_cert:
        pfx_dados = f_cert.read()
        
    chave_privada, certificado, os_certificados = pkcs12.load_key_and_certificates(
        pfx_dados, 
        senha_pfx.encode()
    )

    # 2. Faz o parse do XML utilizando a biblioteca lxml (exigida pela signxml)
    parser = etree.XMLParser(remove_blank_text=True)
    xml_tree = etree.parse(caminho_xml_origem, parser)
    root = xml_tree.getroot()
    
    # 3. Localiza o nó 'infNFe' para referenciar a assinatura pelo atributo Id
    inf_nfe = root.find(".//{http://portalfiscal.inf.br}infNFe")
    if inf_nfe is None:
        # Tenta sem namespace caso o XML não possua
        inf_nfe = root.find(".//infNFe")
        
    if inf_nfe is None:
        raise ValueError("Tag <infNFe> não encontrada no arquivo XML original.")
        
    id_atributo = inf_nfe.get("Id")
    uri_referencia = f"#{id_atributo}"

    # 4. Configura o assinador no padrão exigido pela SEFAZ
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha1", # Padrão SEFAZ para NF-e
        digest_algorithm="sha1"
    )
    
    # Executa a assinatura acoplada
    signed_root = signer.sign(
        root, 
        key=chave_privada, 
        cert=certificado,
        reference_uri=uri_referencia
    )
    
    # 5. Sobrescreve o arquivo físico com o XML assinado devidamente formatado
    xml_assinado_bytes = etree.tostring(signed_root, pretty_print=True, encoding="utf-8", xml_declaration=True)
    
    with open(caminho_xml_origem, "wb") as f_out:
        f_out.write(xml_assinado_bytes)
        
    print(f"DEBUG FISCAL - XML Assinado Digitalmente com Sucesso: {caminho_xml_origem}")
    return xml_assinado_bytes

@app.post("/api/v1/caixa/gerar-xml-nota")
def api_gerar_xml_nota_completa(dados: NotaInput):
    """
    Endpoint chamado pelo PWA para gerar o XML completo de conferência.
    Retorna o arquivo XML bruto diretamente como um fluxo de download.
    """
    import xml.etree.ElementTree as ET
    from xml.dom import minidom
    import os
    import sys
    
    # 1. MOSTRAR LOG DE CAMINHO ANTES DE QUALQUER OPERAÇÃO DE BANCO
    diretorio_execucao = os.getcwd()
    diretorio_script = os.path.dirname(os.path.abspath(__file__))
    pasta_destino = os.path.join(diretorio_script, "xml_notas")
    pasta_assinadas = os.path.join(diretorio_script, "assinadas")
    
    print("\n" + "="*80)
    print(f"DEBUG FISCAL - DIRETÓRIO ATUAL DE EXECUÇÃO: {diretorio_execucao}")
    print(f"DEBUG FISCAL - PASTA ONDE O XML SERÁ GRAVADO: {pasta_destino}")
    print("="*80 + "\n")
    
    # 2. TENTATIVA DE CONEXÃO PROTEGIDA COM TIMEOUT CONTRA DEADLOCK
    try:
        print("DEBUG FISCAL - Tentando obter conexão com o banco...")
        conn = obter_conexao()
        
        # Se for SQLite, configuramos um timeout de 5 segundos para não travar infinitamente
        if hasattr(conn, 'execute'):
            conn.execute("PRAGMA busy_timeout = 5000;")
            
        cursor = conn.cursor()
        print("DEBUG FISCAL - Conexão obtida com sucesso!")
        
    except Exception as e:
        print(f"ERRO CRÍTICO NA CONEXÃO: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Não foi possível conectar ao banco de dados devido a um travamento (Deadlock). Erro: {e}"
        )
        
    cursor.execute("""
        SELECT nome_razao, fantasia, cnpj_cpf, inscr_estadual, logradouro, numero, 
               bairro, cidade as cidade, uf, cep, fone, email, codigo_municipio
        FROM loja WHERE id_loja = ? AND status = 'A';
    """, (dados.id_loja,))
    raw_loja = cursor.fetchone()
    
    if not raw_loja:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Loja ativa com ID {dados.id_loja} não encontrada.")

    # 3. TRATAMENTO CRÍTICO DE CHAVES (Garante compatibilidade de dicionário do SQLite)
    dados_loja = {}
    if isinstance(raw_loja, dict):
        for k, v in raw_loja.items():
            chave_limpa = k[0] if isinstance(k, tuple) else k
            dados_loja[chave_limpa] = v if v is not None else ""
    else:
        # Fallback caso retorne tupla pura por índice
        colunas = ["nome_razao", "fantasia", "cnpj_cpf", "inscr_estadual", "logradouro", 
                   "numero", "bairro", "cidade", "uf", "cep", "fone", "email", "codigo_municipio"]
        dados_loja = {col: raw_loja[i] if raw_loja[i] is not None else "" for i, col in enumerate(colunas)}

    print(f"Dados da loja normalizados: {dados_loja}")

    nfe_root = ET.Element("NFe", xmlns="http://www.portalfiscal.inf.br/nfe")
    
    # Geração da Chave de Acesso Limpa
    cnpj_limpo = str(dados_loja['cnpj_cpf']).replace('.','').replace('-','').replace('/','').strip().zfill(14)
    inf_nfe = ET.SubElement(nfe_root, "infNFe", Id=f"NFe312610{cnpj_limpo}55001{str(dados.numero_nota).zfill(9)}100000001", versao="5.00")
    
    ide = ET.SubElement(inf_nfe, "ide")
    ET.SubElement(ide, "cUF").text = "31"
    ET.SubElement(ide, "natOp").text = "Venda de Mercadoria"
    ET.SubElement(ide, "mod").text = "55"
    ET.SubElement(ide, "serie").text = "1"
    ET.SubElement(ide, "nNF").text = str(dados.numero_nota)
    ET.SubElement(ide, "dhEmi").text = "2026-10-27T19:30:00-03:00"
    ET.SubElement(ide, "tpNF").text = "1"
    ET.SubElement(ide, "idDest").text = "1"
    ET.SubElement(ide, "cMunFG").text = str(dados_loja["codigo_municipio"])
    ET.SubElement(ide, "tpImp").text = "1"
    ET.SubElement(ide, "tpEmis").text = "1"
    ET.SubElement(ide, "tpAmb").text = "2"
    ET.SubElement(ide, "finNFe").text = "1"
    ET.SubElement(ide, "indPres").text = str(dados.indPres)
    
    if dados.indPres == "5" and dados.cMunFGIBS:
        ET.SubElement(ide, "cMunFGIBS").text = str(dados.cMunFGIBS)
        
    emit = ET.SubElement(inf_nfe, "emit")
    ET.SubElement(emit, "CNPJ").text = "".join(filter(str.isdigit, str(dados_loja["cnpj_cpf"])))
    ET.SubElement(emit, "xNome").text = str(dados_loja["nome_razao"])
    if dados_loja["fantasia"]:
        ET.SubElement(emit, "xFant").text = str(dados_loja["fantasia"])
        
    ender_emit = ET.SubElement(emit, "enderEmit")
    ET.SubElement(ender_emit, "xlgr").text = str(dados_loja["logradouro"])
    ET.SubElement(ender_emit, "nro").text = str(dados_loja["numero"])
    ET.SubElement(ender_emit, "xBairro").text = str(dados_loja["bairro"])
    ET.SubElement(ender_emit, "cMun").text = str(dados_loja["codigo_municipio"])
    ET.SubElement(ender_emit, "xMun").text = str(dados_loja.get("cidade", ""))
    ET.SubElement(ender_emit, "UF").text = str(dados_loja["uf"])
    ET.SubElement(ender_emit, "CEP").text = "".join(filter(str.isdigit, str(dados_loja["cep"])))
    ET.SubElement(emit, "IE").text = "".join(filter(str.isdigit, str(dados_loja["inscr_estadual"])))
    ET.SubElement(emit, "CRT").text = "3"
    
    v_prod_total = 0.0
    v_ibs_uf_total = 0.0
    v_ibs_mun_total = 0.0
    v_cbs_total = 0.0
    
    # Tratamento para os produtos (converte chaves complexas se houver no laço)
    for idx, item in enumerate(dados.produtos, start=1):
        cursor.execute("""
            SELECT nome_produto, ncm, cst_iva_dual, cclass_trib, ind_monofasico 
            FROM produtos WHERE id_produto = ?;
        """, (item.id_produto,))
        raw_prod = cursor.fetchone()
        if not raw_prod:
            continue
            
        prod = {}
        if isinstance(raw_prod, dict):
            for k, v in raw_prod.items():
                chave_p_limpa = k[0] if isinstance(k, tuple) else k
                prod[chave_p_limpa] = v
        else:
            col_prods = ["nome_produto", "ncm", "cst_iva_dual", "cclass_trib", "ind_monofasico"]
            prod = {c: raw_prod[i] for i, c in enumerate(col_prods)}

        v_item = item.valor_venda
        v_prod_total += v_item
        ind_mono = int(prod["ind_monofasico"] or 0)
        
        p_ibs_uf = 14.5 if ind_mono != 1 else 0.0
        p_ibs_mun = 3.2 if ind_mono != 1 else 0.0
        p_cbs = 8.8 if ind_mono != 1 else 0.0
        
        v_ibs_uf = round(v_item * (p_ibs_uf / 100.0), 2)
        v_ibs_mun = round(v_item * (p_ibs_mun / 100.0), 2)
        v_cbs = round(v_item * (p_cbs / 100.0), 2)
        
        v_ibs_uf_total += v_ibs_uf
        v_ibs_mun_total += v_ibs_mun
        v_cbs_total += v_cbs
        
        det = ET.SubElement(inf_nfe, "det", nItem=str(idx))
        prod_tag = ET.SubElement(det, "prod")
        ET.SubElement(prod_tag, "cProd").text = str(item.id_produto)
        ET.SubElement(prod_tag, "cEAN").text = "SEM GTIN"
        ET.SubElement(prod_tag, "xProd").text = str(prod["nome_produto"])
        ET.SubElement(prod_tag, "NCM").text = str(prod["ncm"])
        ET.SubElement(prod_tag, "CFOP").text = "5102"
        ET.SubElement(prod_tag, "uCom").text = "UN"
        ET.SubElement(prod_tag, "qCom").text = "1.000"
        ET.SubElement(prod_tag, "vUnCom").text = f"{v_item:.2f}"
        ET.SubElement(prod_tag, "vProd").text = f"{v_item:.2f}"
        ET.SubElement(prod_tag, "indTot").text = "1"
        
        imposto = ET.SubElement(det, "imposto")
        ub_block = ET.SubElement(imposto, "UB")
        ET.SubElement(ub_block, "cst").text = str(prod["cst_iva_dual"] or "000").zfill(3)
        ET.SubElement(ub_block, "cClassTrib").text = str(prod["cclass_trib"] or "000001").zfill(6)
        ET.SubElement(ub_block, "vBC").text = f"{v_item:.2f}"
        ET.SubElement(ub_block, "pIBSUF").text = f"{p_ibs_uf:.2f}"
        ET.SubElement(ub_block, "vIBSUF").text = f"{v_ibs_uf:.2f}"
        ET.SubElement(ub_block, "pIBSMun").text = f"{p_ibs_mun:.2f}"
        ET.SubElement(ub_block, "vIBSMun").text = f"{v_ibs_mun:.2f}"
        ET.SubElement(ub_block, "pCBS").text = f"{p_cbs:.2f}"
        ET.SubElement(ub_block, "vCBS").text = f"{v_cbs:.2f}"
        
    conn.close()
    
    v_ibs_total_consolidado = round(v_ibs_uf_total + v_ibs_mun_total, 2)
    v_nf_total = round(v_prod_total + v_ibs_total_consolidado + v_cbs_total, 2)
    
    total = ET.SubElement(inf_nfe, "total")
    w_block = ET.SubElement(total, "IBSCBS")
    ET.SubElement(w_block, "vBCIBSCBS").text = f"{v_prod_total:.2f}"
    ET.SubElement(w_block, "vIBSMun").text = f"{v_ibs_mun_total:.2f}"
    ET.SubElement(w_block, "vIBS").text = f"{v_ibs_total_consolidado:.2f}"
    ET.SubElement(w_block, "vCBS").text = f"{v_cbs_total:.2f}"
    ET.SubElement(w_block, "vNFTot").text = f"{v_nf_total:.2f}"
    
    rough_string = ET.tostring(nfe_root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    xml_formatado = reparsed.toprettyxml(indent="    ")
    
    # GARANTIA ABSOLUTA DE PASTA: Cria o diretório xml_notas de maneira forçada
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino, exist_ok=True)
        
    nome_arquivo = f"nota_{dados.numero_nota}_loja_{dados.id_loja}.xml"
    caminho_arquivo = os.path.join(pasta_destino, nome_arquivo)
    
    print(f"DEBUG FISCAL - O arquivo XML está sendo gravado com sucesso em: {os.path.abspath(caminho_arquivo)}")
    
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        f.write(xml_formatado)
    # Bloco novo de Assinatura Digital:
    try:
        # Exemplo apontando para as credenciais da empresa (configure variáveis de ambiente ou config)
        caminho_certificado = "certificado.pfx" 
        senha_certificado = "1234" # Senha do certificado A1
        
        if os.path.exists(caminho_certificado):
            print("DEBUG FISCAL - Iniciando assinatura digital do XML...")
            xml_final_bytes = assinar_xml_nfe(caminho_arquivo, caminho_certificado, senha_certificado)
            return Response(content=xml_final_bytes, media_type="application/xml")
        else:
            print("DEBUG FISCAL - Certificado não configurado. Retornando XML sem assinatura.")
            
    except Exception as err_assinatura:
        print(f"ALERTA FISCAL - Falha ao assinar: {err_assinatura}")
        # Retorna o sem assinatura para não quebrar o fluxo caso o certificado expire
           
    return Response(content=xml_formatado, media_type="application/xml")
