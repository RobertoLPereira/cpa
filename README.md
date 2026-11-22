Executar o backend: Dentro da pasta cpa
  - python -m venv .venv
  - .venv\Scripts\Activate.ps1
  - python backend.apis.mysql.orm.main_orm.py
Executar o frontend:
  - python -m http.server 4000
Obs.: Sempre que alterar um arquivo no frontend, altere a linha de versão do sw.js CACHE_NAME
para que o browser não use versão anterior. Adicione 1 na versão que estiver lá.
Comando para gerar a distribuição:
 pyinstaller --noconfirm --onedir --console --name "PDV_CPA_Server" --paths="." --collect-data="signxml" --collect-data="certifi" --collect-submodules="reportlab" --hidden-import="uvicorn.logging" --hidden-import="uvicorn.loops" --hidden-import="uvicorn.loops.auto" --hidden-import="uvicorn.protocols" --hidden-import="uvicorn.protocols.http" --hidden-import="uvicorn.protocols.http.auto" --hidden-import="uvicorn.lifespan" --hidden-import="uvicorn.lifespan.on" --hidden-import="pymysql" --hidden-import="cryptography" --hidden-import="lxml.etree" --hidden-import="lxml._elementpath" --hidden-import="sqlite3" run_server.py
Após a criação da pasta dist:
 - Copiar o arquivo .env para dist\pdv_cpa_server
 - Copiar o pdv_cpa.db para dist\pdv_cpa_server
 - copiar a pasta frontend para dist\pdv_cpa_server
   * Altere as linhas que realizam impostação dos css e javascript, incluindo a versão
   exemplo:<link rel="stylesheet" href="./css/layout.css?v=2" />
           <script src="auth_retaguarda.js?v=2"></script>
           <script type="module" src="./js/main.js?v=2"></script>
 - Criar a pasta backend
  - copiar o arquivo do certificado.pfx para esta pasta