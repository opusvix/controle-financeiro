import os

import uvicorn

from .main import criar_app

if __name__ == "__main__":
    # Só escuta no próprio PC (127.0.0.1): ninguém da rede acessa seus dados.
    # A porta pode mudar pelo ambiente (CF_PORT) — a demonstração usa outra porta
    # para rodar ao lado do app normal sem conflito.
    host = os.environ.get("CF_HOST", "127.0.0.1")
    port = int(os.environ.get("CF_PORT", "8000"))
    uvicorn.run(criar_app(), host=host, port=port)
