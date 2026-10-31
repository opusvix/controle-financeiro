import uvicorn

from .main import criar_app

if __name__ == "__main__":
    # Só escuta no próprio PC (127.0.0.1): ninguém da rede acessa seus dados.
    uvicorn.run(criar_app(), host="127.0.0.1", port=8000)
