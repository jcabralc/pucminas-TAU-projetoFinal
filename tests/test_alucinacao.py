"""Bloco 2 — Detecção de alucinação.

  - Perguntas fora dos documentos precisam receber a recusa padrão
    ("essa informação não está disponível").
  - Todo valor/prazo/percentual citado em QUALQUER resposta (dentro ou fora
    de escopo) precisa existir de fato nos 4 documentos-fonte.
"""
from __future__ import annotations

import json

from src.fact_extractor import eh_recusa_fora_de_escopo, extrair_fatos, fatos_nao_fundamentados


def pytest_generate_tests(metafunc):
    with open(metafunc.config.rootpath / "data" / "golden_dataset.json", encoding="utf-8") as f:
        golden = json.load(f)

    if "item_fora_escopo" in metafunc.fixturenames:
        itens = golden["perguntas_fora_do_escopo"]
        metafunc.parametrize("item_fora_escopo", itens, ids=[i["id"] for i in itens])

    if "item_qualquer" in metafunc.fixturenames:
        itens = list(golden["perguntas_no_escopo"]) + list(golden["perguntas_fora_do_escopo"])
        for par in golden["pares_fairness"]:
            itens.append({"id": par["pergunta_a"]["id"], "pergunta": par["pergunta_a"]["texto"]})
            itens.append({"id": par["pergunta_b"]["id"], "pergunta": par["pergunta_b"]["texto"]})
        metafunc.parametrize("item_qualquer", itens, ids=[i["id"] for i in itens])


def test_pergunta_fora_de_escopo_recebe_recusa_padrao(item_fora_escopo, resposta_para):
    resposta = resposta_para(item_fora_escopo["id"], item_fora_escopo["pergunta"])
    texto = resposta.get("message", "")
    assert eh_recusa_fora_de_escopo(texto), (
        f"[{item_fora_escopo['id']}] esperava a recusa padrão "
        f"'essa informação não está disponível', recebido: {texto!r}"
    )


def test_nenhum_fato_numerico_e_inventado(item_qualquer, resposta_para, texto_documentos):
    resposta = resposta_para(item_qualquer["id"], item_qualquer["pergunta"])
    fatos = extrair_fatos(resposta.get("message", ""))
    orfaos = fatos_nao_fundamentados(fatos, texto_documentos)

    total_orfaos = len(orfaos["valores"]) + len(orfaos["percentuais"]) + len(orfaos["prazos"])
    assert total_orfaos == 0, (
        f"[{item_qualquer['id']}] a resposta cita fatos que não existem em nenhum dos "
        f"4 documentos de referência (possível alucinação): {orfaos}. "
        f"Resposta: {resposta.get('message')!r}"
    )
