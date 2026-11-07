from datetime import datetime, timezone
import os
from decimal import Decimal
from typing import List, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select, text

from backend.apis.mysql.orm.core_fiscal import calcular_item_cupom, dar_baixa_estoque_lote, generar_string_xml_ibscbs
from backend.apis.mysql.orm.core_sync import processar_fila_sincronizacao_background
from backend.apis.mysql.orm.database import get_session, init_db
from backend.apis.mysql.orm.models import Caixa, CaixaMovimento, MovimentacaoPerdasEstoque, OaasControleSync, Produtos, Loja, Venda, VendaItem, AuditoriaProdutosFalhas

app = FastAPI(
    title="API Central do Gerente Fiscal - Software House (SQLModel)",
    description="Motor de validação e homologação refatorado em SQLModel",
    version="3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

# Pydantic Schemas adaptados
class ItemMMySQL(BaseModel):
    id_produto: str
    nome_produto: str
    ncm: str
    preco_venda: Decimal
    estoque_atual: Decimal
    situacao: str = "A"

class ItemCarrinhoInput(BaseModel):
    codigo: str
    quantidade: Decimal
    preco_contingencia: Decimal

class CarrinhoInput(BaseModel):
    itens_carrinho: List[ItemCarrinhoInput]

class ItemVendaXML(BaseModel):
    id_produto: str
    valor_venda: Decimal

class NotaInput(BaseModel):
    numero_nota: int
    id_loja: int = 2
    indPres: str = "1"
    cMunFGIBS: Optional[str] = None
    produtos: List[ItemVendaXML]


def atualizar_preco_produto_background(id_produto: str, novo_preco: Decimal):
    """Executa a atualização de contingência comercial em background."""
    from backend.apis.mysql.orm.database import engine
    with Session(engine) as session:
        try:
            produto = session.exec(select(Produtos).where(Produtos.id_produto == id_produto)).first()
            if produto and (produto.preco_venda == Decimal("0.0000")):
                produto.preco_venda = novo_preco
                session.add(produto)
                session.commit()
        except Exception as e:
            print(f"Falha ao atualizar preço em background: {e}")


@app.post("/api/v1/retaguarda/produtos/importar-lote")
def importar_lote_mysql_json(produtos: List[ItemMMySQL], session: Session = Depends(get_session)):
    contador = 0
    try:
        for p in produtos:
            ncm_limpo = p.ncm.replace(".", "").replace("/", "").strip() if p.ncm else "00000000"
            
            # Executa REPLACE orm-friendly usando a instrução nativa do repositório
            produto_existente = session.exec(select(Produtos).where(Produtos.id_produto == p.id_produto)).first()
            if produto_existente:
                session.delete(produto_existente)
                session.flush()

            novo_produto = Produtos(
                id_produto=p.id_produto,
                nome_produto=p.nome_produto,
                ncm=ncm_limpo,
                preco_venda=p.preco_venda,
                estoque_atual=p.estoque_atual,
                situacao=p.situacao
            )
            session.add(novo_produto)
            contador += 1
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao processar lote: {e}")
        
    return {"status": "sucesso", "mensagem": f"{contador} produtos importados e higienizados."}

@app.post("/api/v1/caixa/calcular-cupom")
def calcular_e_finalizar_cupom_caixa(
    carrinho: CarrinhoInput, 
    background_tasks: BackgroundTasks, 
    session: Session = Depends(get_session)
):
    itens_aprovados = []
    itens_bloqueados = []
    subtotal_produtos = Decimal("0.00")
    total_ibs = Decimal("0.00")
    total_cbs = Decimal("0.00")
    total_ibpt_fed = Decimal("0.00")
    total_ibpt_est = Decimal("0.00")
    
    for item in carrinho.itens_carrinho:
        res = calcular_item_cupom(
            session=session,
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
            
            if res.get("forcou_contingencia"):
                background_tasks.add_task(atualizar_preco_produto_background, res["id_produto"], item.preco_contingencia)
            
    if itens_aprovados:
        dar_baixa_estoque_lote(session, itens_aprovados)
        
        # 1. Cria a instância de cabeçalho da Venda no banco (Mapeada na sessão)
        nova_venda = Venda(
            subtotal=Decimal(subtotal_produtos),
            total=Decimal(subtotal_produtos),
            status="APROVADO",
            data_venda=datetime.now(timezone.utc)
        )
        session.add(nova_venda)
        session.flush() # Descarrega para o MySQL gerar o ID auto-incremental imediatamente

        # 2. Injeta o Log CDC de sincronização pendente para o robô
        log_sync = OaasControleSync(
            tabela_afetada="venda",
            registro_id=str(nova_venda.id),
            status="P"
        )
        session.add(log_sync)
        session.commit()
        
        # 3. Dispara o Robô Python em Background Tasks de forma assíncrona
        background_tasks.add_task(processar_fila_sincronizacao_background)
        
    return {
        "resumo": {
            "vProd": subtotal_produtos,
            "vIBS_Total": total_ibs,
            "vCBS_Total": total_cbs,
            "vNF": subtotal_produtos,
            "ibpt_total_fed": total_ibpt_fed,
            "ibpt_total_est": total_ibpt_est,
            "vTotTrib": total_ibpt_fed + total_ibpt_est
        },
        "itens_aprovados": itens_aprovados,
        "itens_bloqueados": itens_bloqueados
    }


@app.get("/api/v1/auditoria/inconsistencias")
def emitir_relatorio_inconsistencias(session: Session = Depends(get_session)):
    try:
        session.exec(text("DELETE FROM auditoria_produtos_falhas;"))
        produtos = session.exec(select(Produtos)).all()
        
        for p in produtos:
            if p.preco_venda == Decimal("0.0000"):
                falha = AuditoriaProdutosFalhas(
                    id_produto=p.id_produto,
                    falha=f"PREÇO ZERADO: Produto {p.nome_produto} ativo sem valor comercial."
                )
                session.add(falha)
            elif p.cst_iva_dual is None:
                falha = AuditoriaProdutosFalhas(
                    id_produto=p.id_produto,
                    falha=f"IVA DUAL INCOMPLETO: NCM {p.ncm} sem amarração correspondente."
                )
                session.add(falha)
        session.commit()
        
        falhas = session.exec(select(AuditoriaProdutosFalhas)).all()
        return {"inconsistencias": falhas}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/v1/caixa/gerar-xml-nota")
def api_gerar_xml_nota_completa(dados: NotaInput, session: Session = Depends(get_session)):
    diretorio_script = os.path.dirname(os.path.abspath(__file__))
    pasta_destino = os.path.join(diretorio_script, "xml_notas")
    
    # 1. Busca os dados da Loja utilizando o ORM do SQLModel
    loja_ativa = session.exec(
        select(Loja).where(Loja.id_loja == dados.id_loja)
    ).first()
    
    if not loja_ativa:
        raise HTTPException(status_code=404, detail="Loja ativa não encontrada.")

    # 2. Inicialização do elemento raiz XML da NF-e
    nfe_root = ET.Element("NFe", xmlns="http://portalfiscal.inf.br")
    
    # Higienização e formatação do CNPJ do Emitente
    cnpj_limpo = "".join(filter(str.isdigit, str(loja_ativa.cnpj_cpf))).zfill(14)
    
    # Geração da Chave de Acesso (Mock estruturado mantendo a regra dos fontes originais)
    chave_acesso_mock = f"NFe312610{cnpj_limpo}55001{str(dados.numero_nota).zfill(9)}100000001"
    inf_nfe = ET.SubElement(nfe_root, "infNFe", Id=chave_acesso_mock, versao="5.00")
    
    # 3. Grupo: ide (Identificação da NF-e)
    ide = ET.SubElement(inf_nfe, "ide")
    ET.SubElement(ide, "cUF").text = "31"
    ET.SubElement(ide, "natOp").text = "Venda de Mercadoria"
    ET.SubElement(ide, "mod").text = "55"
    ET.SubElement(ide, "serie").text = "1"
    ET.SubElement(ide, "nNF").text = str(dados.numero_nota)
    ET.SubElement(ide, "dhEmi").text = "2026-10-27T19:30:00-03:00" # Data fixada conforme regras fiscais vigentes
    ET.SubElement(ide, "tpNF").text = "1"
    ET.SubElement(ide, "idDest").text = "1"
    ET.SubElement(ide, "cMunFG").text = str(loja_ativa.codigo_municipio or "3106200")
    ET.SubElement(ide, "tpImp").text = "1"
    ET.SubElement(ide, "tpEmis").text = "1"
    ET.SubElement(ide, "tpAmb").text = "2"
    ET.SubElement(ide, "finNFe").text = "1"
    ET.SubElement(ide, "indPres").text = str(dados.indPres)
    
    # 4. Grupo: emit (Emitente da Nota)
    emit = ET.SubElement(inf_nfe, "emit")
    ET.SubElement(emit, "CNPJ").text = cnpj_limpo
    ET.SubElement(emit, "xNome").text = str(loja_ativa.nome_razao)
    
    # 5. Acumuladores Globais de Totais (Tratamento estrito com Decimal)
    v_prod_total = Decimal("0.00")
    v_ibs_uf_total = Decimal("0.00")
    v_ibs_mun_total = Decimal("0.00")
    v_cbs_total = Decimal("0.00")
    
    # 6. Processamento dos itens informados no payload
    for idx, item in enumerate(dados.produtos, start=1):
        # Busca o produto de forma relacional atômica
        prod = session.exec(
            select(Produtos).where(Produtos.id_produto == item.id_produto)
        ).first()
        
        if not prod:
            continue

        v_item = item.valor_venda
        v_prod_total += v_item
        ind_mono = prod.ind_monofasico
        
        # Alíquotas baseadas nas flags fiscais injetadas
        p_ibs_uf = Decimal("14.50") if ind_mono != 1 else Decimal("0.00")
        p_ibs_mun = Decimal("3.20") if ind_mono != 1 else Decimal("0.00")
        p_cbs = Decimal("8.80") if ind_mono != 1 else Decimal("0.00")
        
        # Cálculos de partilha com precisão centesimal (.quantize)
        v_ibs_uf = (v_item * (p_ibs_uf / Decimal("100.00"))).quantize(Decimal("1.00"))
        v_ibs_mun = (v_item * (p_ibs_mun / Decimal("100.00"))).quantize(Decimal("1.00"))
        v_cbs = (v_item * (p_cbs / Decimal("100.00"))).quantize(Decimal("1.00"))
        
        v_ibs_uf_total += v_ibs_uf
        v_ibs_mun_total += v_ibs_mun
        v_cbs_total += v_cbs
        
        # Injeção das Tags de Detalhamento do Produto no XML
        det = ET.SubElement(inf_nfe, "det", nItem=str(idx))
        prod_tag = ET.SubElement(det, "prod")
        ET.SubElement(prod_tag, "cProd").text = str(item.id_produto)
        ET.SubElement(prod_tag, "xProd").text = str(prod.nome_produto)
        ET.SubElement(prod_tag, "NCM").text = str(prod.ncm)
        ET.SubElement(prod_tag, "uCom").text = "UN"
        ET.SubElement(prod_tag, "qCom").text = "1.000"
        ET.SubElement(prod_tag, "vUnCom").text = f"{v_item:.2f}"
        ET.SubElement(prod_tag, "vProd").text = f"{v_item:.2f}"
        
        # Bloco da Reforma Tributária (IVA Dual) por Item
        imposto = ET.SubElement(det, "imposto")
        ub_block = ET.SubElement(imposto, "UB")
        ET.SubElement(ub_block, "cst").text = str(prod.cst_iva_dual or "000").zfill(3)
        ET.SubElement(ub_block, "cClassTrib").text = str(prod.cclass_trib or "000001").zfill(6)
        ET.SubElement(ub_block, "vBC").text = f"{v_item:.2f}"
        ET.SubElement(ub_block, "vIBSUF").text = f"{v_ibs_uf:.2f}"
        ET.SubElement(ub_block, "vIBSMun").text = f"{v_ibs_mun:.2f}"
        ET.SubElement(ub_block, "vCBS").text = f"{v_cbs:.2f}"
        
    # 7. Consolidação de Valores Totais da Nota
    v_ibs_total_consolidado = v_ibs_uf_total + v_ibs_mun_total
    v_nf_total = v_prod_total + v_ibs_total_consolidado + v_cbs_total
    
    total = ET.SubElement(inf_nfe, "total")
    w_block = ET.SubElement(total, "IBSCBS")
    ET.SubElement(w_block, "vBCIBSCBS").text = f"{v_prod_total:.2f}"
    ET.SubElement(w_block, "vIBS").text = f"{v_ibs_total_consolidado:.2f}"
    ET.SubElement(w_block, "vCBS").text = f"{v_cbs_total:.2f}"
    ET.SubElement(w_block, "vNFTot").text = f"{v_nf_total:.2f}"
    
    # 8. Formatação (Pretty Print) e Escrita em Disco
    rough_string = ET.tostring(nfe_root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    xml_formatado = reparsed.toprettyxml(indent="    ")
    
    # Remove a declaração xml automática para compatibilidade SEFAZ
    linhas = xml_formatado.split("\n")
    if linhas[0].startswith("<?xml"):
        linhas = linhas[1:]
    xml_final = "\n".join(linhas)
        
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino, exist_ok=True)
        
    caminho_arquivo = os.path.join(pasta_destino, f"nota_{dados.numero_nota}.xml")
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        f.write(xml_final)
        
    return Response(content=xml_final, media_type="application/xml")

# Adicione o Schema de entrada no bloco de modelos Pydantic
class ItemPerda(BaseModel):
    id_produto: str
    quantidade_perdida: Decimal
    motivo_perda: str


@app.post("/api/v1/retaguarda/estoque/processar-perdas")
def post_processar_lote_perdas(lote: List[ItemPerda], session: Session = Depends(get_session)):
    """
    Processa em lote a lista de produtos perdidos/vencidos, aplicando o estorno
    de crédito fiscal de IBS e CBS, além de realizar a baixa física no estoque.
    """
    aliq_base_ibs = Decimal("0.01")  # 1% de alíquota base original do fonte legado
    aliq_base_cbs = Decimal("0.09")  # 9% de alíquota base original do fonte legado
    resultado_lote = []
    
    try:
        for item in lote:
            # 1. Busca atômica do produto via SQLModel
            produto = session.exec(
                select(Produtos).where(Produtos.id_produto == item.id_produto)
            ).first()
            
            if not produto:
                continue
                
            # No banco legado, a coluna 'preco_venda' era lida como custo na perda (conforme fonte enviado)
            custo_medio = produto.preco_venda if produto.preco_venda is not None else Decimal("0.0000")
            ind_mono = produto.ind_monofasico
            
            # 2. Regra de Estorno Tributário (Reforma Tributária)
            if ind_mono == 1:
                v_estorno_ibs = Decimal("0.0000")
                v_estorno_cbs = Decimal("0.0000")
                detalhe = "Item Monofásico - Isento de Estorno na Perda"
            else:
                base_calculo_estorno = (custo_medio * item.quantidade_perdida).quantize(Decimal("1.0000"))
                v_estorno_ibs = (base_calculo_estorno * aliq_base_ibs).quantize(Decimal("1.00"))
                v_estorno_cbs = (base_calculo_estorno * aliq_base_cbs).quantize(Decimal("1.00"))
                detalhe = f"Estorno calculado sobre Base R$ {base_calculo_estorno:.2f}"
                
            # 3. Baixa física de inventário na tabela mestre
            produto.estoque_atual -= item.quantidade_perdida
            session.add(produto)
            
            # 4. Lançamento no histórico de movimentação de quebras
            nova_perda = MovimentacaoPerdasEstoque(
                id_produto=item.id_produto,
                quantidade_perdida=item.quantidade_perdida,
                motivo_perda=item.motivo_perda,
                valor_estorno_ibs=v_estorno_ibs,
                valor_estorno_cbs=v_estorno_cbs
            )
            session.add(nova_perda)
            
            # 5. Adiciona ao payload de retorno da API comercial
            resultado_lote.append({
                "id_produto": item.id_produto,
                "nome": produto.nome_produto,
                "qtd_baixada": item.quantidade_perdida,
                "motivo": item.motivo_perda,
                "cClassTrib": "410030",  # Código de Classificação de Perdas/Quebras
                "vEstornoIBS": v_estorno_ibs,
                "vEstornoCBS": v_estorno_cbs,
                "status": detalhe
            })
            
        # Gravação atômica de todo o lote enviado (All-or-Nothing)
        session.commit()
        
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Falha crítica no processamento do lote de perdas: {str(e)}"
        )
        
    return {"status": "sucesso", "operacoes_estorno": resultado_lote}

@app.post("/api/v1/retaguarda/matriz/sincronizar")
def sincronizar_matriz_lote(session: Session = Depends(get_session)):
    """
    Executa a sincronização em massa da tabela de produtos local com as tabelas
    de referência da Matriz Fiscal, higienizando os NCMs e aplicando as novas
    regras do IVA Dual de forma atômica.
    """
    try:
        # 1. Executa a query complexa de atualização em lote usando a engine de texto do SQLModel
        # Mantém a compatibilidade exata com as regras de concatenação e fallback do MySQL 5.7
        session.execute(text("""
            UPDATE produtos
            SET 
                cst_iva_dual = (
                    SELECT cst_ibs_cbs FROM ref_matriz_fiscal_ncm 
                    WHERE ref_matriz_fiscal_ncm.ncm_codigo = REPLACE(produtos.ncm, '.', '')
                       OR REPLACE(produtos.ncm, '.', '') LIKE CONCAT(ref_matriz_fiscal_ncm.ncm_codigo, '%')
                    LIMIT 1
                ),
                cclass_trib = (
                    SELECT cclass_trib FROM ref_matriz_fiscal_ncm 
                    WHERE ref_matriz_fiscal_ncm.ncm_codigo = REPLACE(produtos.ncm, '.', '')
                       OR REPLACE(produtos.ncm, '.', '') LIKE CONCAT(ref_matriz_fiscal_ncm.ncm_codigo, '%')
                    LIMIT 1
                ),
                ind_monofasico = (
                    SELECT m.ind_gIBSCBSMono 
                    FROM ref_iva_cst_matriz m
                    WHERE m.cst_ibs_cbs = (
                        SELECT cst_ibs_cbs FROM ref_matriz_fiscal_ncm 
                        WHERE ref_matriz_fiscal_ncm.ncm_codigo = REPLACE(produtos.ncm, '.', '')
                           OR REPLACE(produtos.ncm, '.', '') LIKE CONCAT(ref_matriz_fiscal_ncm.ncm_codigo, '%')
                        LIMIT 1
                    )
                ),
                ibpt_fed = (
                    SELECT ibpt_nacional_federal FROM ref_matriz_fiscal_ncm 
                    WHERE ref_matriz_fiscal_ncm.ncm_codigo = REPLACE(produtos.ncm, '.', '')
                       OR REPLACE(produtos.ncm, '.', '') LIKE CONCAT(ref_matriz_fiscal_ncm.ncm_codigo, '%')
                    LIMIT 1
                ),
                ibpt_est = (
                    SELECT ibpt_estadual FROM ref_matriz_fiscal_ncm 
                    WHERE ref_matriz_fiscal_ncm.ncm_codigo = REPLACE(produtos.ncm, '.', '')
                       OR REPLACE(produtos.ncm, '.', '') LIKE CONCAT(ref_matriz_fiscal_ncm.ncm_codigo, '%')
                    LIMIT 1
                )
            WHERE EXISTS (
                SELECT 1 FROM ref_matriz_fiscal_ncm 
                WHERE ref_matriz_fiscal_ncm.ncm_codigo = REPLACE(produtos.ncm, '.', '')
                   OR REPLACE(produtos.ncm, '.', '') LIKE CONCAT(ref_matriz_fiscal_ncm.ncm_codigo, '%')
            );
        """))

        # 2. Executa a query de higienização secundária (Remoção definitiva de pontos dos NCMs locais)
        session.execute(text("UPDATE produtos SET ncm = REPLACE(ncm, '.', '');"))
        
        # 3. Confirma a transação atômica gerenciada
        session.commit()
        
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Erro crítico durante a sincronização em lote com a matriz: {str(e)}"
        )
        
    return {
        "status": "sucesso", 
        "mensagem": "Tabela mestre higienizada e sincronizada com sucesso com a matriz fiscal via SQLModel!"
    }
# Schemas Pydantic para os payloads de Entrada do PDV
class AberturaCaixaInput(BaseModel):
    pdv_id: int
    numero_caixa: int
    usuario_id: int
    valor_abertura: Decimal

class MovimentacaoCaixaInput(BaseModel):
    tipo: str  # "SUPRIMENTO" ou "SANGRIA"
    valor: Decimal
    observacao: Optional[str] = None

class FechamentoCaixaInput(BaseModel):
    valor_fechamento_informado: Decimal
    observacao: Optional[str] = None


@app.post("/api/v1/caixa/abrir")
def abrir_caixa(dados: AberturaCaixaInput, session: Session = Depends(get_session)):
    """Verifica se já existe um caixa aberto para o PDV e realiza a abertura oficial."""
    caixa_aberto = session.exec(
        select(Caixa).where(Caixa.pdv_id == dados.pdv_id, Caixa.status == "ABERTO")
    ).first()

    if caixa_aberto:
        raise HTTPException(
            status_code=400, 
            detail=f"Operação Negada: O PDV {dados.pdv_id} já possui um caixa ativo aberto."
        )

    novo_caixa = Caixa(
        pdv_id=dados.pdv_id,
        numero_caixa=dados.numero_caixa,
        usuario_id=dados.usuario_id,
        data_abertura=datetime.now(),
        valor_abertura=dados.valor_abertura,
        status="ABERTO"
    )
    session.add(novo_caixa)
    session.commit()
    session.refresh(novo_caixa)
    
    return {"status": "sucesso", "mensagem": "Caixa aberto com sucesso.", "caixa_id": novo_caixa.id}


@app.post("/api/v1/caixa/{caixa_id}/movimentar")
def movimentar_caixa(caixa_id: int, dados: MovimentacaoCaixaInput, session: Session = Depends(get_session)):
    """Executa suprimentos (entrada de troco) ou sangrias (retirada de excesso de numerário)."""
    caixa = session.exec(select(Caixa).where(Caixa.id == caixa_id, Caixa.status == "ABERTO")).first()
    
    if not caixa:
        raise HTTPException(status_code=404, detail="Caixa ativo não localizado para esta operação.")

    dados.tipo = dados.tipo.upper()
    if dados.tipo not in ["SUPRIMENTO", "SANGRIA"]:
        raise HTTPException(status_code=400, detail="Tipo inválido. Escolha 'SUPRIMENTO' ou 'SANGRIA'.")

    # Atualiza os acumuladores no cabeçalho do Caixa ativo
    if dados.tipo == "SUPRIMENTO":
        caixa.valor_suprimento += dados.valor
    elif dados.tipo == "SANGRIA":
        # Validação de segurança para não deixar o saldo em caixa negativo
        saldo_atual_estimado = caixa.valor_abertura + caixa.valor_suprimento - caixa.valor_sangria
        if dados.valor > saldo_atual_estimado:
            raise HTTPException(status_code=400, detail="Sangria bloqueada: Valor superior ao saldo físico em caixa.")
        caixa.valor_sangria += dados.valor

    # Registra a movimentação no histórico
    movimento = CaixaMovimento(
        caixa_id=caixa.id,
        tipo=dados.tipo,
        valor=dados.valor,
        observacao=dados.observacao,
        data_movimento=datetime.now()
    )
    
    session.add(caixa)
    session.add(movimento)
    session.commit()
    
    return {"status": "sucesso", "mensagem": f"Movimentação de {dados.tipo} registrada."}


@app.post("/api/v1/caixa/{caixa_id}/fechar")
def fechar_caixa(caixa_id: int, dados: FechamentoCaixaInput, session: Session = Depends(get_session)):
    """Consolida todas as vendas e movimentações, calcula a diferença/quebra e fecha o caixa."""
    caixa = session.exec(select(Caixa).where(Caixa.id == caixa_id, Caixa.status == "ABERTO")).first()
    
    if not caixa:
        raise HTTPException(status_code=404, detail="Caixa ativo não localizado ou já encerrado.")

    # 1. Recupera o total de vendas faturadas em dinheiro/formas processadas neste caixa
    # No dump real, a tabela 'venda' possui a coluna 'caixa_id' e 'total'
    vendas = session.exec(
        select(Venda).where(Venda.caixa_id == caixa.id, Venda.status == "APROVADO")
    ).all()
    total_vendas = sum([v.total for v in vendas]) if vendas else Decimal("0.00")

    # 2. Equação matemática de conferência cega (Saldo Esperado no Sistema)
    saldo_esperado = (
        caixa.valor_abertura + 
        caixa.valor_suprimento + 
        total_vendas - 
        caixa.valor_sangria
    ).quantize(Decimal("1.00"))

    # 3. Calcula quebra de caixa ou sobra (Diferença)
    diferenca_caixa = (dados.valor_fechamento_informado - saldo_esperado).quantize(Decimal("1.00"))

    # 4. Atualiza os metadados de fechamento do cabeçalho
    caixa.data_fechamento = datetime.now()
    caixa.valor_fechamento = dados.valor_fechamento_informado
    caixa.diferenca = diferenca_caixa
    caixa.status = "FECHADO"
    caixa.observacao = dados.observacao

    session.add(caixa)
    session.commit()

    return {
        "status": "sucesso",
        "auditoria_fechamento": {
            "caixa_id": caixa.id,
            "saldo_sistema_esperado": saldo_esperado,
            "saldo_fisico_informado": dados.valor_fechamento_informado,
            "diferenca_quebra": diferenca_caixa,
            "situacao_caixa": "CONCILIADO" if diferenca_caixa == 0 else "DIVERGENTE"
        }
    }
