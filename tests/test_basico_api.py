"""Smoke tests simples contra a API REAL da AURA, usando as credenciais do
`.env` (lido automaticamente por `tests/conftest.py` via python-dotenv).

É o primeiro teste a rodar assim que a equipe recebe usuário/senha pelo
Canvas — confirma que `.env` está correto, que o servidor está acordado
(`/health`), que o login funciona e que `/chat` responde algo coerente,
ANTES de gastar cota gravando o snapshot inteiro ou rodando a suíte cheia.

São todos @pytest.mark.live: só rodam com a flag --live (consomem a cota
compartilhada da turma) e não entram na suíte padrão (`pytest -v`).

Uso:
    pytest -v -m live --live tests/test_basico_api.py
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.live


def test_health_responde_ok(aura_client):
    saude = aura_client.health()
    print(f"\nGET /health -> {saude}")
    assert saude.get("status") == "ok"


def test_login_obtem_token(aura_client):
    aura_client._garantir_login()
    assert aura_client._token, "login não retornou nenhum token"
    print(f"\nlogin ok, token (primeiros 12 chars): {aura_client._token[:12]}...")


def test_chat_responde_pergunta_simples(aura_client):
    resposta = aura_client.chat("Qual o valor da anuidade do cartão padrão?")
    print(f"\nresposta da AURA: {resposta}")

    assert resposta.get("message"), "resposta veio sem o campo 'message' preenchido"
    assert isinstance(resposta.get("sources", []), list), "'sources' deveria ser uma lista"
    print("OK: resposta contém message e sources válidos")
