import os
import sys
import threading
import time
import webbrowser
import uvicorn
from dotenv import load_dotenv

# 1. Garante que o diretório base seja a pasta onde o .exe (ou script) está localizado
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 2. Proteção para modo sem console (--noconsole), evitando crash no Uvicorn
if sys.stdout is None:
    sys.stdout = open(os.path.join(BASE_DIR, "servidor_pdv.log"), "a", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = sys.stdout

# 3. Carrega o .env externo
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

from backend.apis.mysql.orm.main_orm import app

def abrir_navegador():
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    # Abre automaticamente o frontend no navegador padrão após subir o servidor
    threading.Thread(target=abrir_navegador, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False, workers=1)
