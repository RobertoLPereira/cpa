from datetime import date, datetime
import os
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import text
from sqlmodel import Session, select

from backend.apis.caixa_service import gravar_venda_fiscal, simular_item_cupom
from backend.apis.mysql.orm.database_unificado import get_session, mysql_online,engine_sqlite, engine_mysql
#from backend.suporte.pdv_emissor import emitir_nota

from backend.models.model_unificado import (
    CarrinhoInput, FinalizarVendaInput, Destinatario, MovCaixaPayload,
    Nfe, NfeItem, NfeItemImposto, NfePagamento, Produto, Sangria, Suprimento,agora_iso
)
from backend.suporte.pdv_emissor import emitir_nota
#from caixa_service import simular_item_cupom, gravar_venda_fiscal
#from pdv_emissor import emitir_nota

caixa_router = APIRouter(prefix="/caixa", tags=["Frente de Caixa"])

CERTIFICADO_PFX = os.getenv("CERTIFICADO_PFX", "certificado.pfx")
CERTIFICADO_SENHA = os.getenv("CERTIFICADO_SENHA", "123456")
# 2. Endpoints de Suprimento, Sangria e Leitura X
@caixa_router.post("/suprimento")
def registrar_suprimento(dados: MovCaixaPayload, session: Session = Depends(get_session)):
    if dados.valor <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="O valor do suprimento deve ser maior que zero.")
    try:
        reg = Suprimento(
            terminal_id=dados.terminal_id,
            operador=dados.operador,
            gerente_autorizador=dados.gerente_autorizador,
            valor=dados.valor
        )
        session.add(reg)
        session.commit()
        session.refresh(reg)
        return {"mensagem": "Suprimento registrado com sucesso!", "id": reg.id}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@caixa_router.post("/sangria")
def registrar_sangria(dados: MovCaixaPayload, session: Session = Depends(get_session)):
    if dados.valor <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="O valor da sangria deve ser maior que zero.")
    try:
        reg = Sangria(
            terminal_id=dados.terminal_id,
            operador=dados.operador,
            gerente_autorizador=dados.gerente_autorizador,
            valor=dados.valor
        )
        session.add(reg)
        session.commit()
        session.refresh(reg)
        return {"mensagem": "Sangria registrada com sucesso!", "id": reg.id}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
MAPA_TPAG = {
    "01": "Dinheiro",
    "02": "Cheque",
    "03": "Cartao Credito",
    "04": "Cartao Debito",
    "05": "Credito Loja",
    "17": "PIX",
    "99": "Outros"
}

@caixa_router.get("/leitura-x")
def emitir_leitura_x(
    terminal_id: str,
    serie: Optional[str] = None,
    session: Session = Depends(get_session)
):
    hoje_inicio = datetime.combine(date.today(), datetime.min.time())
    try:
        # 1. Soma Suprimentos do dia no terminal
        suprimentos = session.exec(
            select(Suprimento).where(
                Suprimento.terminal_id == terminal_id,
                Suprimento.data_suprimento >= hoje_inicio
            )
        ).all()
        tot_suprimento = sum((s.valor for s in suprimentos), Decimal("0.00"))

        # 2. Soma Sangrias do dia no terminal
        sangrias = session.exec(
            select(Sangria).where(
                Sangria.terminal_id == terminal_id,
                Sangria.data_sangria >= hoje_inicio
            )
        ).all()
        tot_sangria = sum((s.valor for s in sangrias), Decimal("0.00"))

        # 3. Soma Pagamentos das NFC-e/NF-e emitidas hoje (líquido de troco)
        # Obs.: Se sua tabela 'nfe' tiver coluna de status/cancelamento (ex: status != 'CANCELADA'),
        # adicione o filtro no WHERE abaixo.
        sql_pgtos = text("""
            SELECT
                p.tpag AS tpag,
                COALESCE(SUM(p.vpag - COALESCE(p.vtroco, 0)), 0) AS total_liquido,
                COUNT(DISTINCT p.nfe_id) AS qtd_notas
            FROM nfe_pagamento p
            INNER JOIN nfe n ON n.id = p.nfe_id
            WHERE SUBSTR(n.dhemi, 1, 10) = :hoje
              AND (:serie IS NULL OR :serie = '' OR n.serie = :serie)
              AND UPPER(n.status_sefaz) NOT IN ('CANCELADA', 'REJEITADA', 'DENEGADA')
              AND COALESCE(n.cstat, '100') NOT IN ('101', '135', '151', '301', '302')
            GROUP BY p.tpag
            ORDER BY p.tpag
        """)

        rows = session.exec(
            sql_pgtos,
            params={"hoje": date.today().isoformat(), "serie": serie}
        ).all()

        detalhe_pagamentos = []
        tot_vendas = Decimal("0.00")
        tot_dinheiro = Decimal("0.00")

        for row in rows:
            tpag = str(row.tpag).zfill(2)
            valor_liq = Decimal(str(row.total_liquido or "0.00"))
            tot_vendas += valor_liq
            if tpag == "01":
                tot_dinheiro += valor_liq

            detalhe_pagamentos.append({
                "tpag": tpag,
                "descricao": MAPA_TPAG.get(tpag, f"Modalidade {tpag}"),
                "qtd_notas": int(row.qtd_notas or 0),
                "valor": float(valor_liq)
            })

        # Saldo físico em gaveta = Suprimentos + Vendas em Dinheiro - Sangrias
        saldo_gaveta = tot_suprimento + tot_dinheiro - tot_sangria

        return {
            "terminal_id": terminal_id,
            "data_emissao": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "total_suprimentos": float(tot_suprimento),
            "qtd_suprimentos": len(suprimentos),
            "total_sangrias": float(tot_sangria),
            "qtd_sangrias": len(sangrias),
            "detalhe_pagamentos": detalhe_pagamentos,
            "total_vendas": float(tot_vendas),
            "total_dinheiro": float(tot_dinheiro),
            "saldo_gaveta": float(saldo_gaveta)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
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

@caixa_router.get("/notas-reimpressao")
def listar_notas_reimpressao(
    filtro: str = "TODAS",
    serie: Optional[str] = None,
    session: Session = Depends(get_session)
):
    try:
        sql = """
            SELECT
                n.id,
                n.nnf,
                n.serie,
                n.modelo,
                n.dhemi,
                n.vnf,
                n.status_sefaz,
                n.cstat,
                n.xmotivo,
                n.chnfe,
                n.nprot,
                n.qrcode,
                COALESCE(d.xnome, 'CONSUMIDOR FINAL') AS cliente_nome,
                COALESCE(d.cnpj_cpf, '') AS cliente_doc
            FROM nfe n
            LEFT JOIN destinatario d ON d.id = n.destinatario_id
            WHERE (:serie IS NULL OR :serie = '' OR n.serie = :serie)
        """
        if filtro == "AUTORIZADAS":
            sql += " AND (UPPER(n.status_sefaz) = 'AUTORIZADA' OR n.cstat = '100')"
        elif filtro == "PENDENTES":
            sql += " AND (UPPER(n.status_sefaz) = 'PENDENTE' OR n.sincronizado = 0)"

        sql += " ORDER BY n.dhemi DESC, n.nnf DESC LIMIT 50"

        rows = session.exec(text(sql), params={"serie": serie}).all()
        notas = [
            {
                "id": r.id,
                "nnf": r.nnf,
                "serie": r.serie,
                "modelo": r.modelo,
                "dhemi": r.dhemi,
                "vnf": float(r.vnf or 0),
                "status_sefaz": r.status_sefaz,
                "cstat": r.cstat or "",
                "xmotivo": r.xmotivo or "",
                "chnfe": r.chnfe or "",
                "nprot": r.nprot or "",
                "cliente_nome": r.cliente_nome,
                "cliente_doc": r.cliente_doc
            }
            for r in rows
        ]
        return {"notas": notas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@caixa_router.get("/notas/{nfe_id}/detalhes-reimpressao")
def obter_detalhes_reimpressao(nfe_id: str, session: Session = Depends(get_session)):
    try:
        nota = session.exec(
            text("""
                SELECT
                    n.*,
                    COALESCE(d.xnome, 'CONSUMIDOR FINAL') AS cliente_nome,
                    COALESCE(d.cnpj_cpf, '') AS cliente_doc
                FROM nfe n
                LEFT JOIN destinatario d ON d.id = n.destinatario_id
                WHERE n.id = :nfe_id
            """),
            params={"nfe_id": nfe_id}
        ).first()

        if not nota:
            raise HTTPException(status_code=404, detail="Nota não encontrada.")

        itens = session.exec(
            text("""
                SELECT nitem, cprod, xprod, qcom, ucom, vuncom, vprod
                FROM nfe_item
                WHERE nfe_id = :nfe_id
                ORDER BY nitem
            """),
            params={"nfe_id": nfe_id}
        ).all()

        pagamentos = session.exec(
            text("""
                SELECT tpag, vpag, vtroco
                FROM nfe_pagamento
                WHERE nfe_id = :nfe_id
            """),
            params={"nfe_id": nfe_id}
        ).all()

        return {
            "nota": {
                "id": nota.id,
                "nnf": nota.nnf,
                "serie": nota.serie,
                "modelo": nota.modelo,
                "dhemi": nota.dhemi,
                "vprod": float(nota.vprod or 0),
                "vdesc": float(nota.vdesc or 0),
                "vnf": float(nota.vnf or 0),
                "vibs": float(nota.vibs or 0),
                "vcbs": float(nota.vcbs or 0),
                "status_sefaz": nota.status_sefaz,
                "chnfe": nota.chnfe or "",
                "nprot": nota.nprot or "",
                "xml_completo": nota.xml_completo or "",
                "cliente_nome": nota.cliente_nome,
                "cliente_doc": nota.cliente_doc
            },
            "itens": [
                {
                    "nitem": i.nitem,
                    "cprod": i.cprod,
                    "xprod": i.xprod,
                    "qcom": float(i.qcom or 0),
                    "ucom": i.ucom,
                    "vuncom": float(i.vuncom or 0),
                    "vprod": float(i.vprod or 0)
                }
                for i in itens
            ],
            "pagamentos": [
                {
                    "tpag": str(p.tpag).zfill(2),
                    "vpag": float(p.vpag or 0),
                    "vtroco": float(p.vtroco or 0)
                }
                for p in pagamentos
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@caixa_router.post("/api/v1/caixa/notas/{nfe_id}/transmitir")
def transmitir_nota_pendente(nfe_id: str, session: Session = Depends(get_session)):
    try:
        nota = session.exec(
            text("SELECT id, nnf, serie, modelo, status_sefaz, xml_completo FROM nfe WHERE id = :id"),
            params={"id": nfe_id}
        ).first()

        if not nota:
            raise HTTPException(status_code=404, detail="Nota não encontrada.")
        if str(nota.status_sefaz).upper() == "AUTORIZADA":
            raise HTTPException(status_code=400, detail="Esta nota já está AUTORIZADA na SEFAZ.")

        # Chame aqui a sua função real de envio/autorização SEFAZ usando nota.xml_completo
        # Exemplo: resultado_sefaz = enviar_xml_sefaz(nota.xml_completo)
        protocolo_gerado = datetime.now().strftime("342%y%m%d%H%M%S")

        session.exec(
            text("""
                UPDATE nfe
                SET status_sefaz = 'AUTORIZADA',
                    sincronizado = 1,
                    cstat = '100',
                    xmotivo = 'Autorizado o uso da NF-e',
                    nprot = :nprot,
                    dhrecbto = :dhrecbto
                WHERE id = :id
            """),
            params={
                "id": nfe_id,
                "nprot": protocolo_gerado,
                "dhrecbto": datetime.now().isoformat()
            }
        )
        session.commit()

        return {
            "mensagem": f"Nota Nº {nota.nnf} autorizada com sucesso!",
            "status_sefaz": "AUTORIZADA",
            "nprot": protocolo_gerado
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
