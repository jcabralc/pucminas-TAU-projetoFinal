"""Bloco 3 — Fairness.

Pares contrafactuais: a mesma pergunta, trocando só um atributo sensível
(gênero, idade, raça, estado civil, região). Os FATOS extraídos das duas
respostas precisam ser iguais — a frase pode variar, o valor/prazo/sim-não
não pode.
"""
from __future__ import annotations

from src.fact_extractor import extrair_fatos, fatos_batem


def pytest_generate_tests(metafunc):
    if "par_fairness" in metafunc.fixturenames:
        import json

        with open(metafunc.config.rootpath / "data" / "golden_dataset.json", encoding="utf-8") as f:
            golden = json.load(f)
        pares = golden["pares_fairness"]
        metafunc.parametrize("par_fairness", pares, ids=[p["id"] for p in pares])


def test_fatos_identicos_entre_par_contrafactual(par_fairness, resposta_para):
    pergunta_a, pergunta_b = par_fairness["pergunta_a"], par_fairness["pergunta_b"]

    resposta_a = resposta_para(pergunta_a["id"], pergunta_a["texto"])
    resposta_b = resposta_para(pergunta_b["id"], pergunta_b["texto"])

    fatos_a = extrair_fatos(resposta_a.get("message", ""))
    fatos_b = extrair_fatos(resposta_b.get("message", ""))

    divergentes = fatos_batem(fatos_a, fatos_b)
    assert not divergentes, (
        f"[{par_fairness['id']}] atributo sensível testado: '{par_fairness['atributo']}'. "
        f"Campos divergentes entre as duas respostas: {divergentes}.\n"
        f"Pergunta A ({pergunta_a['texto']!r}) -> {resposta_a.get('message')!r} "
        f"(fatos: {fatos_a.to_dict()})\n"
        f"Pergunta B ({pergunta_b['texto']!r}) -> {resposta_b.get('message')!r} "
        f"(fatos: {fatos_b.to_dict()})"
    )
