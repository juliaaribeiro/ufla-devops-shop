"""ufla-devops-shop --- a aplicacao fio condutor da disciplina DevOps na Pratica.

Para subir a API:

    uvicorn app:api --host 0.0.0.0 --port 8000

O modulo e ``app``; o objeto ASGI e ``api``.
"""

from app.config import VERSAO as __version__
from app.principal import api

__all__ = ["api", "__version__"]
