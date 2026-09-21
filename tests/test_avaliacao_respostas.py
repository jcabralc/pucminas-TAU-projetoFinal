"""Bloco 1 — Avaliação de respostas.

Para perguntas cuja resposta está nos 4 documentos:
  - o fato certo aparece (valor, prazo, sim/não)?
  - o campo `sources` traz o documento que sustenta a resposta?
  - a AURA fica no escopo do banco (não devolve recusa/erro/cota esgotada)?
"""
from __future__ import annotations

import json

from src.fact_extractor import extrair_fatos


def pytest_generate_tests(metafunc):
    if "item_in_scope" in metafunc.fixturenames:
        with open(metafunc.config.rootpath / "data" / "golden_dataset.json", encoding="utf-8") as f:
            golden = json.load(f)
        itens = golden["perguntas_no_escopo"]
        metafunc.parametrize("item_in_scope", itens, ids=[i["id"] for i in itens])


def test_resposta_fica_no_escopo_do_banco(item_in_scope, resposta_para):
    resposta = resposta_para(item_in_scope["id"], item_in_scope["pergunta"])
    texto = resposta.get("message", "")
    assert texto, f"resposta vazia para '{item_in_scope['id']}'"
    assert "não está disponível" not in texto.lower(), (
        f"pergunta no escopo do banco recebeu recusa de fora de escopo: {texto!r}"
    )
    assert "cota da api" not in texto.lower(), f"cota esgotada durante o teste: {texto!r}"
    assert "erro ao processar" not in texto.lower(), f"erro interno da API: {texto!r}"


def test_fato_esperado_aparece_na_resposta(item_in_scope, resposta_para):
    resposta = resposta_para(item_in_scope["id"], item_in_scope["pergunta"])
    fatos_obtidos = extrair_fatos(resposta.get("message", ""))
    esperados = item_in_scope["fatos_esperados"]

    for valor in esperados.get("valores", []):
        assert valor in fatos_obtidos.valores, (
            f"[{item_in_scope['id']}] valor esperado R$ {valor} não encontrado na resposta: "
            f"{resposta.get('message')!r} (extraídos: {fatos_obtidos.valores})"
        )
    for percentual in esperados.get("percentuais", []):
        assert percentual in fatos_obtidos.percentuais, (
            f"[{item_in_scope['id']}] percentual esperado {percentual}% não encontrado: "
            f"{resposta.get('message')!r} (extraídos: {fatos_obtidos.percentuais})"
        )
    for prazo in esperados.get("prazos", []):
        assert prazo in fatos_obtidos.prazos, (
            f"[{item_in_scope['id']}] prazo esperado {prazo} não encontrado: "
            f"{resposta.get('message')!r} (extraídos: {fatos_obtidos.prazos})"
        )
    if "sim_nao" in esperados:
        assert fatos_obtidos.sim_nao == esperados["sim_nao"], (
            f"[{item_in_scope['id']}] esperava sim/não = {esperados['sim_nao']!r}, "
            f"heurística detectou {fatos_obtidos.sim_nao!r} em: {resposta.get('message')!r}"
        )


def test_sources_cita_documento_esperado(item_in_scope, resposta_para):
    resposta = resposta_para(item_in_scope["id"], item_in_scope["pergunta"])
    sources = resposta.get("sources", [])
    documento_esperado = item_in_scope["documento_esperado"]
    assert documento_esperado in sources, (
        f"[{item_in_scope['id']}] esperava '{documento_esperado}' em sources, "
        f"recebido: {sources}"
    )
