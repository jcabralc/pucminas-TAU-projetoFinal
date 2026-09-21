NOTEBOOK := 2-entrega_final.ipynb

.DEFAULT_GOAL := help

PYTHON ?= python3
VENV := .venv
VENV_PY := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
VENV_PYTEST := $(VENV)/bin/pytest
KERNEL_NAME := pucminas-tau-projetofinal

.PHONY: help venv install test test-basico test-live record-snapshot notebook clean

# Lista os comandos disponíveis
help: 
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install_venv: ## cria/atualiza o .venv, instala dependências e registra o kernel do Jupyter
	@if [ -d "$(VENV)" ]; then \
		echo "venv já existe em $(VENV), atualizando bibliotecas..."; \
	else \
		echo "criando venv em $(VENV)..."; \
		$(PYTHON) -m venv $(VENV); \
	fi
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements.txt
	$(VENV_PY) -m ipykernel install --user --name=$(KERNEL_NAME) --display-name "$(KERNEL_NAME)"
	@echo "venv pronto, bibliotecas atualizadas e kernel '$(KERNEL_NAME)' registrado"

test: ## roda a suíte padrão contra o snapshot gravado (não consome cota da API)
	$(VENV_PYTEST) -v

test-basico: ## smoke test rápido (health/login/chat) contra a API real
	$(VENV_PYTEST) -v -m live --live tests/test_basico_api.py

test-live: ## roda TODOS os testes @pytest.mark.live contra a API real (consome cota da turma)
	$(VENV_PYTEST) -v -m live --live

record-snapshot: ## grava/completa data/snapshot_respostas.json chamando a API real (usa .env)
	$(VENV_PY) scripts/gravar_snapshot.py

notebook: ## reexecuta o notebook de entrega e sobrescreve as saídas (requer jupyter instalado)
	$(VENV_PY) -m jupyter nbconvert --to notebook --execute --inplace $(NOTEBOOK)

clean: ## remove caches e artefatos de execução (não mexe em .venv nem em dados)
	rm -rf .pytest_cache
	find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} +
