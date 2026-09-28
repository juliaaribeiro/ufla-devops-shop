"""Os testes rodam no modo autonomo (SQLite temporario + cache em memoria).

As variaveis de ambiente sao definidas ANTES de importar a aplicacao, porque
``app.config`` as le no momento do import.
"""

import os
import tempfile

_pasta = tempfile.mkdtemp(prefix="ufla-shop-testes-")
os.environ["SQLITE_PATH"] = os.path.join(_pasta, "teste.db")
os.environ.pop("DATABASE_URL", None)
os.environ.pop("REDIS_URL", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import api  # noqa: E402


@pytest.fixture(scope="session")
def cliente():
    with TestClient(api, raise_server_exceptions=False) as c:
        yield c
