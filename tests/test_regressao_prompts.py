"""Bloco 4 — Regressão de prompts.

A suíte normal (padrão, sem --live) roda o golden dataset inteiro contra o
snapshot gravado e compara com os fatos esperados versionados no dataset —
serve como baseline "isso é o que a AURA respondia na data da gravação".

A versão espelhada, marcada @pytest.mark.live, faz a MESMA verificação mas
chamando a API real (só roda com `pytest -m live --live`), para detectar se
o comportamento do sistema mudou desde a gravação.
"""
from __future__ import annotations

import json

import pytest

from src.fact_extractor import extrair_fatos


def _todos_os_itens_com_fatos(golden: dict) -> list[dict]:
    return list(golden["perguntas_no_escopo"])


def pytest_generate_tests(metafunc):
    if "item_regressao" in metafunc.fixturenames:
        with open(metafunc.config.rootpath / "data" / "golden_dataset.json", encoding="utf-8") as f:
            golden = json.load(f)
        itens = _todos_os_itens_com_fatos(golden)
        metafunc.parametrize("item_regressao", itens, ids=[i["id"] for i in itens])


def _checar_fatos_contra_esperado(item: dict, resposta: dict) -> None:
    fatos = extrair_fatos(resposta.get("message", ""))
    esperados = item["fatos_esperados"]

    for valor in esperados.get("valores", []):
        assert valor in fatos.valores, (
            f"[REGRESSÃO] [{item['id']}] valor esperado R$ {valor} sumiu da resposta: "
            f"{resposta.get('message')!r}"
        )
    for percentual in esperados.get("percentuais", []):
        assert percentual in fatos.percentuais, (
            f"[REGRESSÃO] [{item['id']}] percentual esperado {percentual}% sumiu: "
            f"{resposta.get('message')!r}"
        )
    for prazo in esperados.get("prazos", []):
        assert prazo in fatos.prazos, (
            f"[REGRESSÃO] [{item['id']}] prazo esperado {prazo} sumiu: {resposta.get('message')!r}"
        )
    if "sim_nao" in esperados:
        assert fatos.sim_nao == esperados["sim_nao"], (
            f"[REGRESSÃO] [{item['id']}] esperava sim/não = {esperados['sim_nao']!r}, "
            f"agora detectou {fatos.sim_nao!r}: {resposta.get('message')!r}"
        )


def test_regressao_contra_snapshot_gravado(item_regressao, snapshot):
    if item_regressao["id"] not in snapshot["respostas"]:
        pytest.fail(f"'{item_regressao['id']}' não está no snapshot gravado")
    resposta = snapshot["respostas"][item_regressao["id"]]
    _checar_fatos_contra_esperado(item_regressao, resposta)


@pytest.mark.live
def test_regressao_contra_api_ao_vivo(item_regressao, aura_client):
    resposta = aura_client.chat(item_regressao["pergunta"])
    _checar_fatos_contra_esperado(item_regressao, resposta)
