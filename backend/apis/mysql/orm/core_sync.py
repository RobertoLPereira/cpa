import httpx
from sqlmodel import Session, select
from backend.apis.mysql.orm.database import engine
from backend.apis.mysql.orm.models import OaasControleSync, Produtos, Venda

MATRIZ_API_URL = "https://matriz-sistema.com.br"

def processar_fila_sincronizacao_background() -> None:
    """
    Robô Python executado de forma assíncrona. Varre a tabela 'oaas_controle_sync'
    em busca de modificações pendentes ('P') e despacha para o servidor central.
    """
    with Session(engine) as session:
        # 1. Coleta os registros pendentes de sincronização
        pendencias = session.exec(
            select(OaasControleSync).where(OaasControleSync.status == "P").limit(50)
        ).all()

        if not pendencias:
            return

        # Inicializa cliente HTTP para bater na Matriz
        with httpx.Client(timeout=10.0) as client:
            for item in pendencias:
                payload = {}
                
                # 2. Busca e monta o payload específico baseado na tabela afetada
                if item.tabela_afetada == "produtos":
                    produto = session.exec(
                        select(Produtos).where(Produtos.id_produto == item.registro_id)
                    ).first()
                    if produto:
                        payload = {
                            "tipo_registro": "PRODUTO",
                            "id_produto": produto.id_produto,
                            "nome": produto.nome_produto,
                            "preco_venda": float(produto.preco_venda),
                            "estoque_atual": float(produto.estoque_atual)
                        }
                        
                elif item.tabela_afetada == "venda":
                    venda = session.exec(
                        select(Venda).where(Venda.id == int(item.registro_id))
                    ).first()
                    if venda:
                        payload = {
                            "tipo_registro": "VENDA",
                            "id_venda_local": venda.id,
                            "numero_cupom": venda.numero,
                            "total": float(venda.total),
                            "chave_acesso": venda.chave_acesso,
                            "status": venda.status
                        }

                # 3. Envia os dados caso o registro local tenha sido localizado
                if payload:
                    try:
                        resposta = client.post(MATRIZ_API_URL, json=payload)
                        
                        # Se a matriz aceitou o lote, marca como Sincronizado ('S')
                        if resposta.status_code :
                            item.status = "S"
                            session.add(item)
                    except httpx.RequestError as exc:
                        print(f"ALERTA SYNC - Erro de conexão com a Matriz para o ID {item.id}: {exc}")
                        # Mantém como 'P' para tentar na próxima rodada do robô
                        continue
            
            # Confirma as atualizações de status em lote
            session.commit()
