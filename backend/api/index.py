"""Entrypoint da função Python na Vercel.

O runtime Python da Vercel procura um objeto ASGI chamado `app` num arquivo dentro de
`api/`. Este arquivo só reexporta o app real — nenhuma lógica mora aqui, para que o
mesmo `app/main.py` sirva ao `uvicorn` local e à função publicada, sem caminho
alternativo que só é exercitado em produção.

O roteamento de todos os caminhos para este arquivo está em `../vercel.json`.

**Por que mexer no `sys.path`**: este arquivo vive em `backend/api/`, e o pacote que ele
importa vive em `backend/app/` — um diretório acima. Rodando local com
`uvicorn app.main:app` a partir de `backend/`, o diretório atual já está no caminho de
busca e o import funciona. Na Vercel, quem monta o caminho de busca é o runtime, e ele
nem sempre inclui a raiz do projeto. As três linhas abaixo garantem que `backend/` esteja
lá nos dois casos. Sem elas, o sintoma é `FUNCTION_INVOCATION_FAILED` — um 500 sem
mensagem, porque a falha acontece antes de o app existir para tratá-la.

Tarefa: T035
"""

import sys
from pathlib import Path

RAIZ_DO_BACKEND = Path(__file__).resolve().parent.parent
if str(RAIZ_DO_BACKEND) not in sys.path:
    sys.path.insert(0, str(RAIZ_DO_BACKEND))

from app.main import app  # noqa: E402 — precisa vir depois do ajuste de sys.path

__all__ = ["app"]
