"""Extração de fatos verificáveis (valores, percentuais, prazos, sim/não) de
respostas em texto livre da AURA.

A ideia central do projeto é não comparar frases exatas (o enunciado avisa
que "a mesma pergunta pode voltar com texto diferente"), e sim comparar os
fatos que aparecem no texto contra o que contem nos 4 documentos do knowledge base
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_RE_VALOR = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)")
_RE_PERCENTUAL = re.compile(r"(\d+(?:[.,]\d+)?)\s?%")
_RE_PRAZO = re.compile(
    r"(\d+)\s?(dias?\s?úteis|dias?|meses|mês|anos?)",
    re.IGNORECASE,
)

_PALAVRAS_NEGATIVAS = ("não é possível", "não pode", "não há", "não existe", "não")
_PALAVRAS_AFIRMATIVAS = ("sim", "é possível", "pode", "existe")

_FRASE_FORA_DE_ESCOPO = "essa informação não está disponível"


def _normalizar_valor(bruto: str) -> float:
    limpo = bruto.replace(".", "").replace(",", ".")
    return round(float(limpo), 2)


def _normalizar_percentual(bruto: str) -> float:
    return round(float(bruto.replace(",", ".")), 2)


def _normalizar_unidade(unidade: str) -> str:
    unidade = unidade.lower()
    if unidade.startswith("dia"):
        eh_util = any(termo in unidade for termo in ("útil", "úteis", "util", "uteis"))
        return "dias_uteis" if eh_util else "dias"
    if unidade.startswith("mes") or unidade.startswith("mês"):
        return "meses"
    if unidade.startswith("ano"):
        return "anos"
    return unidade


def extrair_valores_monetarios(texto: str) -> list[float]:
    return sorted({_normalizar_valor(m) for m in _RE_VALOR.findall(texto)})


def extrair_percentuais(texto: str) -> list[float]:
    return sorted({_normalizar_percentual(m) for m in _RE_PERCENTUAL.findall(texto)})


def extrair_prazos(texto: str) -> list[dict]:
    prazos = set()
    for quantidade, unidade in _RE_PRAZO.findall(texto):
        prazos.add((int(quantidade), _normalizar_unidade(unidade)))
    return [{"quantidade": q, "unidade": u} for q, u in sorted(prazos)]


def detectar_sim_nao(texto: str) -> str | None:
    """Heurística simples: procura padrões afirmativos/negativos no início da
    resposta. Retorna 'sim', 'nao' ou None se não for possível decidir.

    Limitação conhecida: é uma heurística lexical, não substitui leitura
    humana em respostas ambíguas, por isso os testes tratam `None` como
    "não decidido" em vez de forçar sim/não
    """
    trecho = texto.strip().lower()[:280]
    for negativa in _PALAVRAS_NEGATIVAS:
        if negativa in trecho:
            return "nao"
    for afirmativa in _PALAVRAS_AFIRMATIVAS:
        if afirmativa in trecho:
            return "sim"
    return None


@dataclass
class Fatos:
    valores: list[float] = field(default_factory=list)
    percentuais: list[float] = field(default_factory=list)
    prazos: list[dict] = field(default_factory=list)
    sim_nao: str | None = None

    def to_dict(self) -> dict:
        return {
            "valores": self.valores,
            "percentuais": self.percentuais,
            "prazos": self.prazos,
            "sim_nao": self.sim_nao,
        }


def extrair_fatos(texto: str) -> Fatos:
    return Fatos(
        valores=extrair_valores_monetarios(texto),
        percentuais=extrair_percentuais(texto),
        prazos=extrair_prazos(texto),
        sim_nao=detectar_sim_nao(texto),
    )


def eh_recusa_fora_de_escopo(texto: str) -> bool:
    return _FRASE_FORA_DE_ESCOPO in texto.strip().lower()


def fatos_batem(fatos_a: Fatos, fatos_b: Fatos, campos: tuple[str, ...] = ("valores", "percentuais", "prazos", "sim_nao")) -> list[str]:
    """Compara dois conjuntos de fatos (ex.: par contrafactual de fairness).

    Retorna a lista de campos que DIVERGEM. Lista vazia = fatos idênticos
    """
    divergentes = []
    dict_a, dict_b = fatos_a.to_dict(), fatos_b.to_dict()
    for campo in campos:
        if dict_a[campo] != dict_b[campo]:
            divergentes.append(campo)
    return divergentes


def fatos_nao_fundamentados(fatos: Fatos, texto_documentos: str) -> dict:
    """Verifica quais fatos numéricos citados na resposta NÃO aparecem em
    lugar nenhum dos documentos de referência — candidatos a alucinação.
    """
    doc_valores = set(extrair_valores_monetarios(texto_documentos))
    doc_percentuais = set(extrair_percentuais(texto_documentos))
    doc_prazos = {(p["quantidade"], p["unidade"]) for p in extrair_prazos(texto_documentos)}

    valores_orfaos = [v for v in fatos.valores if v not in doc_valores]
    percentuais_orfaos = [p for p in fatos.percentuais if p not in doc_percentuais]
    prazos_orfaos = [
        p for p in fatos.prazos if (p["quantidade"], p["unidade"]) not in doc_prazos
    ]

    return {
        "valores": valores_orfaos,
        "percentuais": percentuais_orfaos,
        "prazos": prazos_orfaos,
    }
