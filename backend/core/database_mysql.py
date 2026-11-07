import pymysql
import os

# Configurações de Conexão com o MySQL via Variáveis de Ambiente ou Fallback Seguro
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "Roberto")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "rlp562@")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "retaguarda3")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))

def obter_conexao():
    """
    Retorna uma conexão ativa com o banco MySQL utilizando o DictCursor,
    permitindo que as colunas sejam acessadas como dicionários (ex: row["nome_produto"]).
    """
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        port=MYSQL_PORT,
        cursorclass=pymysql.cursors.DictCursor, # Mantém a compatibilidade com row_factory do SQLite
        autocommit=False # Deixa o controle de transações (commit/rollback) explícito no código
    )

def inicializar_banco_mysql():
    """
    Cria a estrutura de tabelas mestre e matrizes fiscais diretamente no MySQL,
    já aplicando as adequações de chaves e autoincrementos do dialeto.
    """
    # Estabelece uma conexão temporária sem banco selecionado apenas para garantir que o Schema existe
    conn_init = pymysql.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, port=MYSQL_PORT)
    cursor_init = conn_init.cursor()
    cursor_init.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    conn_init.close()

    # Abre a conexão oficial no banco selecionado para criar as tabelas
    conn = obter_conexao()
    cursor = conn.cursor()
    
    # 1. Tabela de Matriz Unificada de NCMs (IBPT + Catálogo SEFAZ)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ref_matriz_fiscal_ncm (
        ncm_codigo VARCHAR(10) NOT NULL,
        ex VARCHAR(10) DEFAULT '',
        tipo VARCHAR(20) DEFAULT '',
        descricao LONGTEXT,
        ibpt_nacional_federal DECIMAL(15,4) DEFAULT 0.0,
        ibpt_importados_federal DECIMAL(15,4) DEFAULT 0.0,
        ibpt_estadual DECIMAL(15,4) DEFAULT 0.0,
        ibpt_municipal DECIMAL(15,4) DEFAULT 0.0,
        ibpt_vigencia_fim VARCHAR(20),
        cst_ibs_cbs VARCHAR(4),
        cclass_trib VARCHAR(6),
        PRIMARY KEY (ncm_codigo)
    ) ENGINE=InnoDB;
    """)
    
    # 2. Tabela Mestre de Produtos (Alinhada com a estrutura da sua Retaguarda)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id_produto VARCHAR(20) NOT NULL,
        nome_produto VARCHAR(200) NOT NULL,
        nome_reduzido VARCHAR(80),
        grupos VARCHAR(50),
        referencia VARCHAR(50),
        cod_fornecedor INT,
        unm VARCHAR(3),
        qtd_emb DECIMAL(15,6) DEFAULT 0.0,
        peso_bruto DECIMAL(15,6) DEFAULT 0.0,
        orig_prod CHAR(1),
        cest VARCHAR(10),
        ncm VARCHAR(10),
        cst_icms VARCHAR(4),
        preco_venda DECIMAL(15,4) DEFAULT 0.0,
        estoque_atual DECIMAL(15,4) DEFAULT 0.0,
        situacao CHAR(1) DEFAULT 'A',
        -- Atributos injetados de Auditoria do IVA Dual (De TEXT para VARCHAR)
        cst_iva_dual VARCHAR(4) DEFAULT NULL,
        cclass_trib VARCHAR(6) DEFAULT NULL,
        ind_monofasico INT DEFAULT 0,
        ibpt_fed DECIMAL(15,4) DEFAULT 0.0,
        ibpt_est DECIMAL(15,4) DEFAULT 0.0,
        PRIMARY KEY (id_produto)
    ) ENGINE=InnoDB;
    """)
    
    # 3. Matriz de Propriedades Lógicas por CST da SEFAZ
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ref_iva_cst_matriz (
        cst_ibs_cbs VARCHAR(4) NOT NULL,
        descricao_cst VARCHAR(255),
        ind_gIBSCBS INT DEFAULT 0,
        ind_gIBSCBSMono INT DEFAULT 0,
        ind_gRed INT DEFAULT 0,
        ind_gDif INT DEFAULT 0,
        ind_gTransfCred INT DEFAULT 0,
        ind_gCredPresIBSZFM INT DEFAULT 0,
        ind_gAjusteCompet INT DEFAULT 0,
        ind_RedutorBC INT DEFAULT 0,
        PRIMARY KEY (cst_ibs_cbs)
    ) ENGINE=InnoDB;
    """)
    
    # 4. Repositório de Inconsistências Gerenciais (Adequado AUTO_INCREMENT e TIMESTAMP)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auditoria_produtos_falhas (
        id_falha INT NOT NULL AUTO_INCREMENT,
        id_produto VARCHAR(20),
        nome_produto VARCHAR(200),
        ncm VARCHAR(10),
        tipo_inconsistencia VARCHAR(50),
        detalhe_erro VARCHAR(255),
        data_identificacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id_falha)
    ) ENGINE=InnoDB;
    """)

    # 5. Registro de Ocorrências de Quebras e Baixas por Perda
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movimentacao_perdas_estoque (
        id_perda INT NOT NULL AUTO_INCREMENT,
        id_produto VARCHAR(20),
        quantidade_perdida DECIMAL(15,4) DEFAULT 0.0,
        motivo_perda VARCHAR(50), -- 'VENCIDO', 'QUEBRADO', 'FURTO'
        cclass_trib_estorno VARCHAR(6) DEFAULT '410030',
        valor_estorno_ibs DECIMAL(15,4) DEFAULT 0.0,
        valor_estorno_cbs DECIMAL(15,4) DEFAULT 0.0,
        data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id_perda)
    ) ENGINE=InnoDB;
    """)

    conn.commit()
    conn.close()

# Adicione isso EXATAMENTE no final do seu arquivo backend/core/database_mysql.py

# 1. Cria um "falso engine" ou apenas exporta a string de conexão se a API precisar rodar algo nativo
engine = obter_conexao() 

# 2. A função de sessão que o FastAPI (Depends) está procurando na linha 11 do main.py
def get_session():
    """Entrega a conexão bruta com o MySQL para os endpoints da API"""
    conexao = obter_conexao()
    try:
        yield conexao
    finally:
        conexao.close()

if __name__ == "__main__":
    inicializar_banco_mysql()

