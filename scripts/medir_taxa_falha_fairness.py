"""Repete cada pergunta dos pares de fairness N vezes contra a API real e
mede a taxa de resposta malformada / a distribuição dos fatos extraídos.

O enunciado pede: "Para afirmar que um comportamento é (ou não) falha,
repita a pergunta algumas vezes e reporte a taxa. Uma execução só é
anedota." Este script existe para isso — é uma investigação pontual, não
faz parte da suíte pytest nem roda em toda execução.

Uso:
    python scripts/medir_taxa_falha_fairness.py

Esse script deve ser executado com moderação, já que consome uma
quantidade considerável de cota da API
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
import time

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.aura_client import AuraClient, AuraQuotaExhausted, AuraServerError  # noqa: E402
from src.fact_extractor import extrair_fatos  # noqa: E402

DATA_DIR = RAIZ / "data"
INTERVALO_ENTRE_CHAMADAS_SEGUNDOS = 3.5
REPETICOES = 5
PARES_ALVO = (
    "fairness_genero_aumento_automatico",
    "fairness_idade_renda_minima",
    "fairness_raca_renda_minima",
    "fairness_estado_civil_renda_minima",
    "fairness_regiao_renda_minima",
)


# Fragmentos de raciocínio interno (chain-of-thought/guardrail) que às vezes
# vazam no lugar da resposta de verdade — não começam com "{" nem "```", por
# isso precisam de uma checagem própria (ver Padrão 2 em FALHAS.md).
_MARCADORES_VAZAMENTO_RACIOCINIO = (
    "valid json",
    "check json",
    "did i ",
    "refrain from",
    "escape quotes",
    "evaluated strictly",
)


def _malformado(mensagem: str) -> bool:
    inicio = mensagem.strip()[:10]
    if inicio.startswith("{") or inicio.startswith("```"):
        return True
    mensagem_lower = mensagem.lower()
    return any(marcador in mensagem_lower for marcador in _MARCADORES_VAZAMENTO_RACIOCINIO)


def _amostrar(cliente: AuraClient, item_id: str, texto_pergunta: str) -> list[dict]:
    amostras = []
    for i in range(1, REPETICOES + 1):
        print(f"    [{i}/{REPETICOES}] chamando...")
        try:
            resposta = cliente.chat(texto_pergunta)
            mensagem = resposta.get("message", "")
            amostras.append(
                {
                    "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
                    "message": mensagem,
                    "sources": resposta.get("sources", []),
                    "fatos": extrair_fatos(mensagem).to_dict(),
                    "malformado": _malformado(mensagem),
                    "erro": None,
                }
            )
        except AuraQuotaExhausted as exc:
            print(f"    Cota esgotada: {exc}")
            raise
        except AuraServerError as exc:
            amostras.append(
                {
                    "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
                    "message": None,
                    "sources": [],
                    "fatos": None,
                    "malformado": False,
                    "erro": f"AuraServerError: {exc}",
                }
            )
        time.sleep(INTERVALO_ENTRE_CHAMADAS_SEGUNDOS)
    return amostras


def _resumir(amostras: list[dict]) -> dict:
    validas = [a for a in amostras if a["erro"] is None]
    malformadas = [a for a in validas if a["malformado"]]
    sim_nao_dist: dict[str, int] = {}
    for a in validas:
        chave = str(a["fatos"]["sim_nao"])
        sim_nao_dist[chave] = sim_nao_dist.get(chave, 0) + 1
    valores = sorted({v for a in validas for v in a["fatos"]["valores"]})
    return {
        "total_amostras": len(amostras),
        "amostras_com_erro_infra": len(amostras) - len(validas),
        "taxa_malformado": f"{len(malformadas)}/{len(validas)}" if validas else "n/a",
        "distribuicao_sim_nao": sim_nao_dist,
        "valores_monetarios_vistos": valores,
    }


def main() -> None:
    base_url = os.environ["AURORA_BASE_URL"]
    username = os.environ["AURORA_USERNAME"]
    password = os.environ["AURORA_PASSWORD"]

    with open(DATA_DIR / "golden_dataset.json", encoding="utf-8") as f:
        golden = json.load(f)

    pares_por_id = {p["id"]: p for p in golden["pares_fairness"]}

    cliente = AuraClient(base_url, username, password)
    print("Checando /health...")
    print(cliente.health())

    resultados: dict[str, dict] = {}
    destino = DATA_DIR / "repeticoes_fairness.json"

    try:
        for par_id in PARES_ALVO:
            par = pares_por_id[par_id]
            print(f"\n=== {par_id} (atributo: {par['atributo']}) ===")
            resultado_par = {}
            for lado in ("pergunta_a", "pergunta_b"):
                item = par[lado]
                print(f"  {lado} ({item['id']}): {item['texto'][:70]}...")
                amostras = _amostrar(cliente, item["id"], item["texto"])
                resultado_par[lado] = {
                    "id": item["id"],
                    "texto": item["texto"],
                    "amostras": amostras,
                    "resumo": _resumir(amostras),
                }
            resultados[par_id] = resultado_par
            # salva incrementalmente para não perder progresso se a cota acabar no meio
            _salvar(destino, resultados, base_url)
    except AuraQuotaExhausted:
        print("Parando por aqui — cota esgotada. O que já foi coletado está salvo.")

    print(f"\nResultados salvos em {destino}")
    _imprimir_resumo(resultados)


def _salvar(destino: pathlib.Path, resultados: dict, base_url: str) -> None:
    saida = {
        "metadata": {
            "data_gravacao": dt.datetime.now().isoformat(timespec="seconds"),
            "base_url": base_url,
            "repeticoes_por_pergunta": REPETICOES,
        },
        "resultados": resultados,
    }
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)


def _imprimir_resumo(resultados: dict) -> None:
    print("\n=== RESUMO ===")
    for par_id, par in resultados.items():
        print(f"\n{par_id}")
        for lado in ("pergunta_a", "pergunta_b"):
            r = par[lado]["resumo"]
            print(f"  {par[lado]['id']}: {r}")


if __name__ == "__main__":
    main()
