"""Cliente HTTP para a API da AURA (Banco Aurora)"""
from __future__ import annotations

import json
import time

import requests

TIMEOUT_PADRAO = 900 #180
MARGEM_SEGURANCA_TOKEN_SEGUNDOS = 25 * 60  # token expira em 30 min
MENSAGEM_COTA_ESGOTADA = "cota da api do provedor de ia esgotada"
MENSAGEM_ERRO_INTERNO = "ocorreu um erro ao processar sua mensagem"


class AuraAPIError(RuntimeError):
    """Erro de transporte/HTTP não recuperável (ex.: rate limit persistente)."""


class AuraQuotaExhausted(RuntimeError):
    """A cota compartilhada do provedor de IA foi esgotada pela turma."""


class AuraServerError(RuntimeError):
    """A API respondeu HTTP 200 mas com mensagem de erro interno."""


class AuraClient:
    def __init__(self, base_url: str, username: str, password: str, timeout: int = TIMEOUT_PADRAO):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._token: str | None = None
        self._token_expira_em: float = 0.0

    def health(self) -> dict:
        resposta = requests.get(f"{self.base_url}/health", timeout=30)
        resposta.raise_for_status()
        return resposta.json()

    def _login(self) -> None:
        resposta = requests.post(
            f"{self.base_url}/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=self.timeout,
        )
        resposta.raise_for_status()
        dados = resposta.json()
        self._token = dados.get("token") or dados.get("access_token")
        if not self._token:
            raise AuraAPIError(f"Login não retornou token reconhecível: {dados}")
        self._token_expira_em = time.time() + MARGEM_SEGURANCA_TOKEN_SEGUNDOS

    def _token_valido(self) -> bool:
        return self._token is not None and time.time() < self._token_expira_em

    def _garantir_login(self) -> None:
        if not self._token_valido():
            self._login()

    def chat(self, message: str, history: list | None = None, max_tentativas: int = 3) -> dict:
        self._garantir_login()
        history = history or []

        for tentativa in range(1, max_tentativas + 1):
            resposta = requests.post(
                f"{self.base_url}/chat",
                json={"message": message, "history": history},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=self.timeout,
                stream=True,
            )

            if resposta.status_code == 403:
                # token pode ter expirado entre a checagem e o envio
                self._login()
                continue

            if resposta.status_code == 429:
                if tentativa == max_tentativas:
                    raise AuraAPIError(
                        f"Rate limit (429) persistente após {max_tentativas} tentativas"
                    )
                espera = int(resposta.headers.get("Retry-After", "5"))
                time.sleep(espera)
                continue

            resposta.raise_for_status()
            payload = self._parse_sse(resposta)
            texto = (payload.get("message") or "").lower()

            if MENSAGEM_COTA_ESGOTADA in texto:
                raise AuraQuotaExhausted(payload.get("message", ""))
            if MENSAGEM_ERRO_INTERNO in texto:
                raise AuraServerError(payload.get("message", ""))

            return payload

        raise AuraAPIError("Não foi possível obter resposta da AURA (tentativas esgotadas)")

    @staticmethod
    def _parse_sse(resposta: requests.Response) -> dict:
        payload: dict = {}
        for linha in resposta.iter_lines(decode_unicode=True):
            if not linha:
                continue
            if linha.startswith("data:"):
                bruto = linha[len("data:") :].strip()
                if not bruto:
                    continue
                try:
                    dados = json.loads(bruto)
                except json.JSONDecodeError:
                    continue
                if dados:
                    payload = dados
            elif linha.startswith("event:") and linha.split(":", 1)[1].strip() == "done":
                break
        return payload
