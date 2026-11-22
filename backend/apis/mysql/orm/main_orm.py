import os
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import Session, select, text
import uvicorn

from backend.apis.mysql.orm.database_unificado import get_session, inicializar_bancos, mysql_online
from backend.apis.mysql.orm.models import Caixa, CaixaMovimento, MovimentacaoPerdasEstoque, AuditoriaProdutosFalhas
from backend.models.model_unificado import (
    Emitente, Produto, Nfe, NfeItem, NfeItemImposto, NfePagamento,
    CarrinhoInput, FinalizarVendaInput, agora_iso
)
from backend.apis.caixa_service import simular_item_cupom, gravar_venda_fiscal
from backend.apis.caixa_routes import sincronizar_contingencia_para_mysql
from backend.suporte.pdv_emissor import emitir_nota
from backend.suporte.gerador_xml import gerar_xml_nfe
from backend.apis.usuario_routes import usuario_router
from backend.apis.caixa_routes import caixa_router
app = FastAPI(
    title="API Central do Gerente Fiscal - PDV Espelho XML 4.00 + IBS/CBS",
    version="4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False, # Importante: com allow_origins=["*"], allow_credentials deve ser False no padrão Fetch!
    allow_methods=["*"],
    allow_headers=["*"],
)


CERTIFICADO_PFX = os.getenv("CERTIFICADO_PFX", "certificado.pfx")
CERTIFICADO_SENHA = os.getenv("CERTIFICADO_SENHA", "123456")

@app.on_event("startup")
def on_startup():
    inicializar_bancos()

class ItemMMySQL(BaseModel):
    id_produto: str
    nome_produto: str
    ncm: str
    preco_venda: Decimal
    estoque_atual: Decimal
    cean: Optional[str] = None

@app.post("/api/v1/retaguarda/produtos/importar-lote")
def importar_lote_mysql_json(produtos: List[ItemMMySQL], session: Session = Depends(get_session)):
    contador = 0
    try:
        for p in produtos:
            ncm_limpo = p.ncm.replace(".", "").replace("/", "").strip() if p.ncm else "00000000"
            prod_existente = session.exec(select(Produto).where(Produto.cprod == p.id_produto)).first()
            
            if prod_existente:
                prod_existente.xprod = p.nome_produto[:120]
                prod_existente.ncm = ncm_limpo[:8]
                prod_existente.vuncom = p.preco_venda
                prod_existente.vuntrib = p.preco_venda
                prod_existente.estoque_atual = p.estoque_atual
                prod_existente.atualizado_em = agora_iso()
                session.add(prod_existente)
            else:
                session.add(Produto(
                    cprod=p.id_produto,
                    cean=p.cean,
                    xprod=p.nome_produto[:120],
                    ncm=ncm_limpo[:8],
                    vuncom=p.preco_venda,
                    vuntrib=p.preco_venda,
                    estoque_atual=p.estoque_atual
                ))
            contador += 1
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao processar lote: {e}")

    return {"status": "sucesso", "mensagem": f"{contador} produtos importados na tabela espelho XML."}

@app.post("/api/v1/caixa/calcular-cupom")
def api_simular_cupom(carrinho: CarrinhoInput, session: Session = Depends(get_session)):
    """Simula o carrinho na tela e atualiza preços zerados do legado sem baixar estoque."""
    itens_aprovados = []
    itens_bloqueados = []
    v_prod = Decimal("0.00")
    v_ibs = Decimal("0.00")
    v_cbs = Decimal("0.00")
    ibpt_fed = Decimal("0.00")
    ibpt_est = Decimal("0.00")

    for item in carrinho.itens_carrinho:
        res = simular_item_cupom(session, item)
        if res["status"] in ("BLOQUEADO", "REJEITADO"):
            itens_bloqueados.append(res)
        else:
            itens_aprovados.append(res)
            v_prod += res["vProd"]
            v_ibs += res["IBSCBS"]["vIBS"]
            v_cbs += res["IBSCBS"]["vCBS"]
            ibpt_fed += res["ibpt"]["vFed"]
            ibpt_est += res["ibpt"]["vEst"]

    return {
        "resumo": {
            "vProd": float(v_prod),
            "vIBS_Total": float(v_ibs),
            "vCBS_Total": float(v_cbs),
            "vNF": float(v_prod),
            "ibpt_total_fed": float(ibpt_fed),
            "ibpt_total_est": float(ibpt_est),
            "vTotTrib": float(ibpt_fed + ibpt_est)
        },
        "itens_aprovados": itens_aprovados,
        "itens_bloqueados": itens_bloqueados
    }

@app.post("/api/v1/caixa/finalizar-venda")
def api_finalizar_venda(
    dados: FinalizarVendaInput,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """Fecha o cupom (F8): grava NF-e/NFC-e, baixa estoque, gera/assina XML e sincroniza."""
    itens_calc = []
    for item in dados.itens_carrinho:
        res = simular_item_cupom(session, item)
        if res["status"] != "APROVADO":
            raise HTTPException(status_code=400, detail=res.get("motivo", "Item invalido"))
        itens_calc.append(res)

    if not itens_calc:
        raise HTTPException(status_code=400, detail="Carrinho vazio.")

    nfe_id = gravar_venda_fiscal(session, dados, itens_calc)

    if os.path.exists(CERTIFICADO_PFX):
        res_sefaz = emitir_nota(nfe_id, CERTIFICADO_PFX, CERTIFICADO_SENHA, session=session)
    else:        
        xml_local = gerar_xml_nfe(nfe_id, session=session, salvar_arquivo=False)
        res_sefaz = {"status": "XML_GERADO_SEM_CERTIFICADO", "xml": xml_local}

    background_tasks.add_task(sincronizar_contingencia_para_mysql)

    nfe_gravada = session.get(Nfe, nfe_id)
    return {
        "nfe_id": nfe_id,
        "numero_nota": nfe_gravada.nnf,
        "chave_acesso": nfe_gravada.chnfe,
        "status_sefaz": res_sefaz.get("status"),
        "xml": res_sefaz.get("xml", "")
    }
class ItemPerda(BaseModel):
    id_produto: str
    quantidade_perdida: Decimal
    motivo_perda: str

class AberturaCaixaInput(BaseModel):
    pdv_id: int
    numero_caixa: int
    usuario_id: int
    valor_abertura: Decimal

class MovimentacaoCaixaInput(BaseModel):
    tipo: str
    valor: Decimal
    observacao: Optional[str] = None

class FechamentoCaixaInput(BaseModel):
    valor_fechamento_informado: Decimal
    observacao: Optional[str] = None

@app.get("/api/v1/auditoria/inconsistencias")
def emitir_relatorio_inconsistencias(session: Session = Depends(get_session)):
    try:
        session.exec(text("DELETE FROM auditoria_produtos_falhas;"))
        produtos = session.exec(select(Produto)).all()

        for p in produtos:
            if Decimal(str(p.vuncom or "0")) <= Decimal("0.00"):
                session.add(AuditoriaProdutosFalhas(
                    id_produto=p.cprod,
                    falha=f"PRECO ZERADO: Produto {p.xprod} ativo sem valor comercial."
                ))
            elif not p.ibscbs_cst:
                session.add(AuditoriaProdutosFalhas(
                    id_produto=p.cprod,
                    falha=f"IVA DUAL INCOMPLETO: NCM {p.ncm} sem CST IBS/CBS."
                ))
        session.commit()

        falhas = session.exec(select(AuditoriaProdutosFalhas)).all()
        return {"inconsistencias": falhas}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/v1/produtos/buscar")
def buscar_produtos_pdv(q: str = "", session: Session = Depends(get_session)):
    try:
        termo = q.strip()
        stmt = select(Produto).where(Produto.vuncom > Decimal("0.00"))

        if termo:
            busca_like = f"%{termo}%"
            stmt = stmt.where(
                (Produto.xprod.ilike(busca_like)) |
                (Produto.cean.ilike(busca_like)) |
                (Produto.cprod.ilike(busca_like))
            )

        produtos = session.exec(stmt.order_by(Produto.xprod).limit(50)).all()
        return {"produtos": produtos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/retaguarda/estoque/processar-perdas")
def post_processar_lote_perdas(lote: List[ItemPerda], session: Session = Depends(get_session)):
    aliq_base_ibs = Decimal("0.01")
    aliq_base_cbs = Decimal("0.09")
    resultado_lote = []

    try:
        for item in lote:
            prod = session.exec(select(Produto).where(Produto.cprod == item.id_produto)).first()
            if not prod:
                continue

            custo = Decimal(str(prod.vuncom or "0"))
            if prod.ind_monofasico == 1:
                v_est_ibs = Decimal("0.00")
                v_est_cbs = Decimal("0.00")
                detalhe = "Item Monofasico - Isento de Estorno"
            else:
                base = (custo * item.quantidade_perdida).quantize(Decimal("1.00"))
                v_est_ibs = (base * aliq_base_ibs).quantize(Decimal("1.00"))
                v_est_cbs = (base * aliq_base_cbs).quantize(Decimal("1.00"))
                detalhe = f"Estorno sobre Base R$ {base:.2f}"

            prod.estoque_atual = Decimal(str(prod.estoque_atual or "0")) - item.quantidade_perdida
            prod.atualizado_em = agora_iso()
            session.add(prod)

            session.add(MovimentacaoPerdasEstoque(
                id_produto=item.id_produto,
                quantidade_perdida=item.quantidade_perdida,
                motivo_perda=item.motivo_perda,
                valor_estorno_ibs=v_est_ibs,
                valor_estorno_cbs=v_est_cbs
            ))

            resultado_lote.append({
                "id_produto": item.id_produto,
                "nome": prod.xprod,
                "qtd_baixada": item.quantidade_perdida,
                "cClassTrib": "410030",
                "vEstornoIBS": v_est_ibs,
                "vEstornoCBS": v_est_cbs,
                "status": detalhe
            })
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "sucesso", "operacoes_estorno": resultado_lote}

@app.post("/api/v1/caixa/abrir")
def abrir_caixa(dados: AberturaCaixaInput, session: Session = Depends(get_session)):
    caixa_aberto = session.exec(
        select(Caixa).where(Caixa.pdv_id == dados.pdv_id, Caixa.status == "ABERTO")
    ).first()
    if caixa_aberto:
        raise HTTPException(status_code=400, detail=f"PDV {dados.pdv_id} ja possui caixa aberto.")

    novo = Caixa(
        pdv_id=dados.pdv_id,
        numero_caixa=dados.numero_caixa,
        usuario_id=dados.usuario_id,
        data_abertura=datetime.now(),
        valor_abertura=dados.valor_abertura,
        status="ABERTO"
    )
    session.add(novo)
    session.commit()
    session.refresh(novo)
    return {"status": "sucesso", "caixa_id": novo.id}

@app.post("/api/v1/caixa/{caixa_id}/movimentar")
def movimentar_caixa(caixa_id: int, dados: MovimentacaoCaixaInput, session: Session = Depends(get_session)):
    caixa = session.exec(select(Caixa).where(Caixa.id == caixa_id, Caixa.status == "ABERTO")).first()
    if not caixa:
        raise HTTPException(status_code=404, detail="Caixa aberto nao encontrado.")

    tipo = dados.tipo.upper()
    if tipo == "SUPRIMENTO":
        caixa.valor_suprimento += dados.valor
    elif tipo == "SANGRIA":
        saldo = caixa.valor_abertura + caixa.valor_suprimento - caixa.valor_sangria
        if dados.valor > saldo:
            raise HTTPException(status_code=400, detail="Saldo insuficiente para sangria.")
        caixa.valor_sangria += dados.valor
    else:
        raise HTTPException(status_code=400, detail="Use SUPRIMENTO ou SANGRIA.")

    session.add(caixa)
    session.add(CaixaMovimento(caixa_id=caixa.id, tipo=tipo, valor=dados.valor, observacao=dados.observacao))
    session.commit()
    return {"status": "sucesso", "mensagem": f"{tipo} registrado."}

@app.post("/api/v1/caixa/{caixa_id}/fechar")
def fechar_caixa(caixa_id: int, dados: FechamentoCaixaInput, session: Session = Depends(get_session)):
    caixa = session.exec(select(Caixa).where(Caixa.id == caixa_id, Caixa.status == "ABERTO")).first()
    if not caixa:
        raise HTTPException(status_code=404, detail="Caixa aberto nao encontrado.")

    # Soma os pagamentos em dinheiro (tpag == '01') das notas emitidas no período do turno
    pags_dinheiro = session.exec(
        select(NfePagamento).join(Nfe).where(
            NfePagamento.tpag == "01",
            Nfe.tpnf == "1",
            Nfe.status_sefaz.in_(["AUTORIZADA", "CONTINGENCIA", "PENDENTE"])
        )
    ).all()
    total_vendas_dinheiro = sum([Decimal(str(p.vpag)) - Decimal(str(p.vtroco or "0")) for p in pags_dinheiro])

    saldo_esperado = (
        caixa.valor_abertura + caixa.valor_suprimento + total_vendas_dinheiro - caixa.valor_sangria
    ).quantize(Decimal("1.00"))

    diferenca = (dados.valor_fechamento_informado - saldo_esperado).quantize(Decimal("1.00"))

    caixa.data_fechamento = datetime.now()
    caixa.valor_fechamento = dados.valor_fechamento_informado
    caixa.diferenca = diferenca
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
            "diferenca_quebra": diferenca,
            "situacao_caixa": "CONCILIADO" if diferenca == 0 else "DIVERGENTE"
        }
    }

app.include_router(usuario_router)
app.include_router(caixa_router)
# Serve o frontend (versao3) na raiz http://localhost:8000
#caminho_frontend = os.path.join("frontend", "versao3")
caminho_frontend = os.path.join("frontend")
if os.path.exists(caminho_frontend):
    app.mount("/", StaticFiles(directory=caminho_frontend, html=True), name="frontend")
if __name__ == "__main__":
    # Inicia o servidor local na porta 8000
    uvicorn.run("backend.apis.mysql.orm.main_orm:app", host="0.0.0.0", port=8000, reload=True)
#python -m uvicorn backend.apis.mysql.orm.main_orm