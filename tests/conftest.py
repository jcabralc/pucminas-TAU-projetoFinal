from __future__ import annotations

import json
import os
import pathlib
import sys

import pytest
from dotenv import load_dotenv

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

load_dotenv(RAIZ / ".env")

DATA_DIR = RAIZ / "data"
DOCS_DIR = RAIZ / "docs_referencia"


def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Roda os testes marcados @pytest.mark.live contra a API real da AURA "
        "em vez do snapshot gravado (consome a cota compartilhada da turma).",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    pular = pytest.mark.skip(reason="precisa de --live para rodar contra a API real")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(pular)


@pytest.fixture(scope="session")
def golden_dataset() -> dict:
    with open(DATA_DIR / "golden_dataset.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def snapshot() -> dict:
    with open(DATA_DIR / "snapshot_respostas.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def texto_documentos() -> str:
    partes = []
    for arquivo in sorted(DOCS_DIR.glob("*.md")):
        partes.append(arquivo.read_text(encoding="utf-8"))
    return "\n".join(partes)


@pytest.fixture(scope="session")
def aura_client():
    """Só é instanciado quando um teste marcado @pytest.mark.live de fato
    solicita esta fixture — evita exigir credenciais para rodar a suíte
    padrão contra o snapshot.
    """
    from src.aura_client import AuraClient

    base_url = os.environ.get("AURORA_BASE_URL")
    username = os.environ.get("AURORA_USERNAME")
    password = os.environ.get("AURORA_PASSWORD")
    if not all([base_url, username, password]):
        pytest.skip(
            "Defina AURORA_BASE_URL, AURORA_USERNAME e AURORA_PASSWORD "
            "(veja .env.example) para rodar testes --live."
        )
    return AuraClient(base_url, username, password)


@pytest.fixture
def resposta_para(request, snapshot):
    """Devolve uma função `resposta_para(item_id, pergunta)` que busca a
    resposta no snapshot gravado por padrão, ou chama a API real quando a
    suíte é rodada com --live.
    """
    ao_vivo = request.config.getoption("--live")

    def _obter(item_id: str, pergunta: str) -> dict:
        if ao_vivo:
            cliente = request.getfixturevalue("aura_client")
            return cliente.chat(pergunta)
        if item_id not in snapshot["respostas"]:
            pytest.fail(
                f"Snapshot não contém resposta gravada para '{item_id}'. "
                "Rode scripts/gravar_snapshot.py."
            )
        return snapshot["respostas"][item_id]

    return _obter
