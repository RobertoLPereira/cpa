import sqlite3

DATABASE_PATH = "poc_iva_reforma.db"

def obter_conexao():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Permite acessar colunas pelo nome
    return conn

def inicializar_banco_gerente():
    conn = obter_conexao()
    cursor = conn.cursor()
    
    # 1. Tabela de Matriz Unificada de NCMs (IBPT + Catálogo SEFAZ)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ref_matriz_fiscal_ncm (
        ncm_codigo TEXT PRIMARY KEY,
        ex TEXT,
        tipo TEXT,
        descricao TEXT,
        ibpt_nacional_federal REAL DEFAULT 0.0,
        ibpt_importados_federal REAL DEFAULT 0.0,
        ibpt_estadual REAL DEFAULT 0.0,
        ibpt_municipal REAL DEFAULT 0.0,
        ibpt_vigencia_fim TEXT,
        cst_ibs_cbs TEXT,
        cclass_trib TEXT
    );
    """)
    
    # 2. Tabela Mestre de Produtos (Estrutura Real do seu MySQL)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id_produto VARCHAR(20) NOT NULL PRIMARY KEY,
        nome_produto VARCHAR(200) NOT NULL,
        nome_reduzido VARCHAR(80),
        grupos VARCHAR(50),
        referencia VARCHAR(50),
        cod_fornecedor INTEGER,
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
        -- Atributos injetados de Auditoria do IVA Dual
        cst_iva_dual TEXT,
        cclass_trib TEXT,
        ind_monofasico INTEGER DEFAULT 0,
        ibpt_fed REAL DEFAULT 0.0,
        ibpt_est REAL DEFAULT 0.0
    );
    """)
    
    # 3. Matriz de Propriedades Lógicas por CST da SEFAZ
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ref_iva_cst_matriz (
        cst_ibs_cbs TEXT PRIMARY KEY,
        descricao_cst TEXT,
        ind_gIBSCBS INTEGER,
        ind_gIBSCBSMono INTEGER,
        ind_gRed INTEGER,
        ind_gDif INTEGER,
        ind_gTransfCred INTEGER,
        ind_gCredPresIBSZFM INTEGER,
        ind_gAjusteCompet INTEGER,
        ind_RedutorBC INTEGER
    );
    """)
    
    # 4. Repositório de Inconsistências Gerenciais
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auditoria_produtos_falhas (
        id_falha INTEGER PRIMARY KEY AUTOINCREMENT,
        id_produto TEXT,
        nome_produto TEXT,
        ncm TEXT,
        tipo_inconsistencia TEXT,
        detalhe_erro TEXT,
        data_identificacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
        # 5. Registro de Ocorrências de Quebras e Baixas por Perda
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movimentacao_perdas_estoque (
        id_perda INTEGER PRIMARY KEY AUTOINCREMENT,
        id_produto TEXT,
        quantidade_perdida REAL,
        motivo_perda TEXT, -- 'VENCIDO', 'QUEBRADO', 'FURTO'
        cclass_trib_estorno TEXT DEFAULT '410030',
        valor_estorno_ibs REAL,
        valor_estorno_cbs REAL,
        data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    inicializar_banco_gerente()
