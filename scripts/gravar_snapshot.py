"""Grava snapshot_respostas.json chamando a API uma única vez
para cada pergunta do golden dataset

Uso:
    python scripts/gravar_snapshot.py

Variaveis de ambiente necessárias:
    AURORA_BASE_URL, AURORA_USERNAME, AURORA_PASSWORD

Respeita o limite de 20 chamadas/min por conta e o
timeout de 180s recomendado para a primeira chamada (servidor hiberna).

Depois de rodar, `data/snapshot_respostas.json` passa a conter respostas
retornadas pela API gravadas na data em que foram extraidas.

É seguro rodar várias vezes: perguntas que já têm resposta real gravada
são puladas, então só as pendentes (nunca respondidas ou que falharam
antes) chamam a API. Cada resposta é salva no disco assim que chega, então
interromper a execução (cota esgotada, Ctrl+C, kernel reiniciado) não perde
o que já foi gravado até ali — rode de novo depois para completar o resto.
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

DATA_DIR = RAIZ / "data"
INTERVALO_ENTRE_CHAMADAS_SEGUNDOS = 3.5


def _todas_as_perguntas(golden: dict) -> list[tuple[str, str]]:
    perguntas = []
    for item in golden["perguntas_no_escopo"]:
        perguntas.append((item["id"], item["pergunta"]))
    for item in golden["perguntas_fora_do_escopo"]:
        perguntas.append((item["id"], item["pergunta"]))
    for par in golden["pares_fairness"]:
        perguntas.append((par["pergunta_a"]["id"], par["pergunta_a"]["texto"]))
        perguntas.append((par["pergunta_b"]["id"], par["pergunta_b"]["texto"]))
    return perguntas


def _tem_resposta_valida(resposta: dict | None) -> bool:
    return bool(resposta) and "erro" not in resposta and bool(resposta.get("message"))


def _carregar_respostas_existentes(destino: pathlib.Path) -> dict[str, dict]:
    if not destino.exists():
        return {}
    with open(destino, encoding="utf-8") as f:
        existente = json.load(f)
    if existente.get("metadata", {}).get("sintetico", True):
        print("Snapshot existente é sintético/placeholder — ignorando e gravando do zero.")
        return {}
    return existente.get("respostas", {})


def _salvar(destino: pathlib.Path, respostas: dict[str, dict], base_url: str) -> None:
    pendentes = [item_id for item_id, r in respostas.items() if not _tem_resposta_valida(r)]
    saida = {
        "metadata": {
            "sintetico": False,
            "data_gravacao": dt.datetime.now().isoformat(timespec="seconds"),
            "base_url": base_url,
            "total_perguntas": len(respostas),
            "pendentes": pendentes,
        },
        "respostas": respostas,
    }
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)


def main() -> None:
    base_url = os.environ["AURORA_BASE_URL"]
    username = os.environ["AURORA_USERNAME"]
    password = os.environ["AURORA_PASSWORD"]

    with open(DATA_DIR / "golden_dataset.json", encoding="utf-8") as f:
        golden = json.load(f)

    destino = DATA_DIR / "snapshot_respostas.json"
    respostas = _carregar_respostas_existentes(destino)

    perguntas = _todas_as_perguntas(golden)
    pendentes = [(item_id, texto) for item_id, texto in perguntas if not _tem_resposta_valida(respostas.get(item_id))]

    if not pendentes:
        print("Todas as perguntas já têm resposta real gravada. Nada a fazer.")
        return

    cliente = AuraClient(base_url, username, password)

    print("Checando /health...")
    print(cliente.health())

    print(f"{len(perguntas) - len(pendentes)} já gravadas, {len(pendentes)} pendentes...")

    for indice, (item_id, texto_pergunta) in enumerate(pendentes, start=1):
        print(f"[{indice}/{len(pendentes)}] {item_id}: {texto_pergunta[:60]}...")
        try:
            respostas[item_id] = cliente.chat(texto_pergunta)
        except AuraQuotaExhausted as exc:
            print(f"Cota esgotada em '{item_id}': {exc}")
            print("Parando por aqui — rode de novo mais tarde para completar o restante.")
            respostas[item_id] = {"erro": str(exc)}
            _salvar(destino, respostas, base_url)
            break
        except AuraServerError as exc:
            print(f"AVISO: falha ao gravar '{item_id}': {exc}")
            respostas[item_id] = {"erro": str(exc)}
        _salvar(destino, respostas, base_url)
        time.sleep(INTERVALO_ENTRE_CHAMADAS_SEGUNDOS)

    print(f"Snapshot gravado em {destino}")


if __name__ == "__main__":
    main()
