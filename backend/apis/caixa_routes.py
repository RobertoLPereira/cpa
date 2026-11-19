import os
from decimal import Decimal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from backend.apis.caixa_service import gravar_venda_fiscal, simular_item_cupom
from backend.apis.mysql.orm.database_unificado import get_session, mysql_online,engine_sqlite, engine_mysql
#from backend.suporte.pdv_emissor import emitir_nota

from backend.models.model_unificado import (
    CarrinhoInput, FinalizarVendaInput, Destinatario,
    Nfe, NfeItem, NfeItemImposto, NfePagamento, Produto,agora_iso
)
from backend.suporte.pdv_emissor import emitir_nota
#from caixa_service import simular_item_cupom, gravar_venda_fiscal
#from pdv_emissor import emitir_nota

caixa_router = APIRouter(prefix="/caixa", tags=["Frente de Caixa"])

CERTIFICADO_PFX = os.getenv("CERTIFICADO_PFX", "certificado.pfx")
CERTIFICADO_SENHA = os.getenv("CERTIFICADO_SENHA", "123456")

@caixa_router.post("/calcular-cupom")
def api_simular_cupom(carrinho: CarrinhoInput, session: Session = Depends(get_session)):
    """Apenas simula o carrinho na tela (não grava venda nem baixa estoque)."""
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

@caixa_router.post("/finalizar-venda")
def api_finalizar_venda(
    dados: FinalizarVendaInput,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    Fecha o cupom (F8): grava NF-e/NFC-e, baixa estoque, assina XML,
    transmite SEFAZ (ou contingência) e dispara sincronização com MySQL.
    """
    itens_calc = []
    for item in dados.itens_carrinho:
        res = simular_item_cupom(session, item)
        if res["status"] != "APROVADO":
            raise HTTPException(status_code=400, detail=res.get("motivo", "Item invalido"))
        itens_calc.append(res)

    if not itens_calc:
        raise HTTPException(status_code=400, detail="Carrinho vazio.")

    nfe_id = gravar_venda_fiscal(session, dados, itens_calc)

    # Se existir certificado A1 configurado, assina e transmite para SEFAZ
    resultado_sefaz = {"status": "GRAVADA_LOCAL", "xml": ""}
    if os.path.exists(CERTIFICADO_PFX):
        db_ativo = "pdv_contingencia.db" if not mysql_online() else "pdv_contingencia.db"
        resultado_sefaz = emitir_nota(nfe_id, CERTIFICADO_PFX, CERTIFICADO_SENHA, db_path=db_ativo)
    else:
        # Fallback caso esteja testando sem certificado digital ainda
        from gerador_xml import gerar_xml_nfe
        xml_sem_assinatura = gerar_xml_nfe(nfe_id, db_path="pdv_contingencia.db", salvar_arquivo=False)
        resultado_sefaz = {"status": "SEM_CERTIFICADO", "xml": xml_sem_assinatura}

    # Dispara robô de sincronização SQLite -> MySQL em background
    background_tasks.add_task(sincronizar_contingencia_para_mysql)

    nfe_gravada = session.get(Nfe, nfe_id)
    return {
        "nfe_id": nfe_id,
        "numero_nota": nfe_gravada.nnf,
        "chave_acesso": nfe_gravada.chnfe,
        "status_sefaz": resultado_sefaz.get("status"),
        "xml": resultado_sefaz.get("xml", "")
    }

def sincronizar_contingencia_para_mysql():
    """Sobe vendas e clientes gravados no SQLite offline para o MySQL central."""
    if not mysql_online():
        return

    with Session(engine_sqlite) as s_local, Session(engine_mysql) as s_central:
        # 1. Sincroniza novos destinatários cadastrados no PDV
        dests = s_local.exec(select(Destinatario).where(Destinatario.sincronizado == 0)).all()
        for d in dests:
            existe = s_central.exec(select(Destinatario).where(Destinatario.cnpj_cpf == d.cnpj_cpf)).first()
            if not existe:
                s_central.add(Destinatario(**d.model_dump(exclude={"sincronizado"}), sincronizado=1))
            d.sincronizado = 1
            s_local.add(d)
        s_central.commit()
        s_local.commit()

        # 2. Sincroniza Notas Fiscais pendentes (sincronizado == 0)
        notas = s_local.exec(select(Nfe).where(Nfe.sincronizado == 0).limit(20)).all()
        for nota in notas:
            if not s_central.get(Nfe, nota.id):
                s_central.add(Nfe(**nota.model_dump(exclude={"sincronizado"}), sincronizado=1))
                
                itens = s_local.exec(select(NfeItem).where(NfeItem.nfe_id == nota.id)).all()
                for it in itens:
                    s_central.add(NfeItem(**it.model_dump()))
                    imp = s_local.exec(select(NfeItemImposto).where(NfeItemImposto.nfe_item_id == it.id)).first()
                    if imp:
                        s_central.add(NfeItemImposto(**imp.model_dump()))
                    
                                        # Decrementa estoque no MySQL central (suporta venda avulsa e caixa fechada -CX/-CD)
                    prod_central = s_central.get(Produto, it.produto_id)
                    if prod_central:
                        fator = Decimal(str(prod_central.fator_conversao or "1"))
                        qtd_baixar = Decimal(str(it.qcom)) * fator
                        cprod_base = prod_central.cprod.replace("-CX", "").replace("-CD", "")
                        prod_estoque = s_central.exec(select(Produto).where(Produto.cprod == cprod_base)).first() or prod_central
                        prod_estoque.estoque_atual = Decimal(str(prod_estoque.estoque_atual or "0")) - qtd_baixar
                        prod_estoque.atualizado_em = agora_iso()
                        s_central.add(prod_estoque)


                pags = s_local.exec(select(NfePagamento).where(NfePagamento.nfe_id == nota.id)).all()
                for pg in pags:
                    s_central.add(NfePagamento(**pg.model_dump()))

            nota.sincronizado = 1
            s_local.add(nota)

        s_central.commit()
        s_local.commit()
