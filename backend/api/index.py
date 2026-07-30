"""Entrypoint da função Python na Vercel.

O runtime Python da Vercel procura um objeto ASGI chamado `app` num arquivo dentro de
`api/`. Este arquivo só reexporta o app real — nenhuma lógica mora aqui, para que o
mesmo `app/main.py` sirva ao `uvicorn` local e à função publicada, sem caminho
alternativo que só é exercitado em produção.

O roteamento de todos os caminhos para este arquivo está em `../vercel.json`.

Tarefa: T035
"""

from app.main import app

__all__ = ["app"]
