# Testes Automatizados — AURA (Banco Aurora)

Projeto final da disciplina de Testes Automatizados de Modelos de IA - Trilha 2 (LLM/RAG) - Pós Graduação em Engenharia de Inteligência Artificial e MLOps - PUC Minas.

Suíte de testes para a AURA, assistente virtual do Banco Aurora (fictício).

A documentação consolidada da entrega (contexto, dataset, execução da
suíte com log, e falhas encontradas) está em [`2-entrega_final.ipynb`](2-entrega_final.ipynb).

Este README cobre apenas como rodar o projeto.

## Estrutura

```
├── README.md
├── FALHAS.md                          # falhas documentadas (teste, pergunta, resposta, data)
├── requirements.txt
├── pytest.ini
├── .env.example
├── knowledge/                         # enunciado do trabalho e doc da API da AURA
├── src/
│   ├── aura_client.py                 # cliente HTTP (login, chat via SSE, rate limit)
│   └── fact_extractor.py              # extrai valores/percentuais/prazos/sim-não de um texto
├── data/
│   ├── golden_dataset.json            # perguntas + fatos esperados + pares de fairness
│   ├── snapshot_respostas.json        # respostas gravadas (o que a suíte padrão usa)
│   └── repeticoes_fairness.json       # amostras repetidas dos pares de fairness (ver FALHAS.md)
├── scripts/
│   ├── gravar_snapshot.py             # grava snapshot_respostas.json contra a API real
│   └── medir_taxa_falha_fairness.py   # repete perguntas de fairness N vezes p/ medir taxa de falha
├── docs_referencia/                    # cópia dos 4 documentos do banco (para checar alucinação)
│   ├── politica-credito.md
│   ├── tarifas-cartao.md
│   ├── faq-aumento-limite.md
│   └── termos-de-uso.md
├── tests/
│   ├── conftest.py
│   ├── test_basico_api.py             # smoke test (health/login/chat), @pytest.mark.live
│   ├── test_avaliacao_respostas.py    # bloco 1
│   ├── test_alucinacao.py             # bloco 2
│   ├── test_fairness.py               # bloco 3
│   └── test_regressao_prompts.py      # bloco 4 (snapshot + @pytest.mark.live)
├── 0-testes_iniciais.ipynb            # smoke test interativo, célula a célula
├── 1-gerar_snapshot_respostas.ipynb   # grava/completa o snapshot contra a API real
└── 2-entrega_final.ipynb              # documentação final consolidada (a entrega)
```

## Como rodar

### Setup (comum aos três jeitos abaixo)

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # Linux/Mac
pip install -r requirements.txt
cp .env.example .env             # preencha com o usuário/senha do grupo
```

### Opção A: pelos notebooks, nessa ordem

1. `0-testes_iniciais.ipynb`: smoke test célula a célula (health, login, chat) pra confirmar que as credenciais em `.env` estão certas e a API está respondendo.
2. `1-gerar_snapshot_respostas.ipynb`: grava/completa `data/snapshot_respostas.json` contra a API real. Só chama a API para as perguntas que ainda não têm resposta válida gravada, então pode rodar de novo se a cota acabar no meio.
3. `2-entrega_final.ipynb`: roda a suíte inteira contra o snapshot e monta a documentação final com a evidência de execução. Esse é o notebook da entrega.

### Opção B: pelos scripts, direto no terminal

```bash
python scripts/gravar_snapshot.py   # grava/completa o snapshot (equivalente ao notebook 1)
pytest -v                           # roda a suíte padrão contra o snapshot (não consome cota)
pytest -v -m live --live            # opcional: roda a suíte também contra a API real (regressão, consome cota da turma)
```

### Opção C: pelo Makefile

```bash
make install_venv     # cria/atualiza o .venv, instala dependências, registra o kernel do Jupyter
make record-snapshot  # grava/completa o snapshot (chama scripts/gravar_snapshot.py)
make test             # roda a suíte padrão contra o snapshot
make test-live        # roda a suíte contra a API real (regressão, consome cota da turma)
make notebook         # reexecuta 2-entrega_final.ipynb do zero e sobrescreve as saídas
make test-basico      # smoke test rápido (equivalente ao notebook 0)
make clean            # limpa cache do pytest e __pycache__
```

Rode `make help` pra ver essa lista com as descrições direto no terminal.

## Os 4 blocos de teste

| Bloco | Arquivo | O que verifica |
|---|---|---|
| Avaliação de respostas | `tests/test_avaliacao_respostas.py` | fato certo aparece na resposta; `sources` cita o documento certo; resposta fica no escopo do banco |
| Detecção de alucinação | `tests/test_alucinacao.py` | pergunta fora de escopo recebe "essa informação não está disponível"; nenhum valor/prazo/percentual citado é inventado (checagem cruzada contra os 4 documentos) |
| Fairness | `tests/test_fairness.py` | pares contrafactuais (gênero, idade, raça, estado civil, região) produzem os mesmos fatos |
| Regressão de prompts | `tests/test_regressao_prompts.py` | golden dataset contra snapshot (padrão) e contra API real (`--live`) |

Todos os testes comparam **fatos extraídos** (`src/fact_extractor.py`), não
a frase exata, a mesma pergunta pode voltar com texto diferente a cada
chamada.

## Falhas encontradas

Rodando `pytest -v` contra o snapshot real, a suíte hoje dá **11 failed, 84
passed, 17 skipped**. Cada falha está documentada em
[`FALHAS.md`](FALHAS.md), no formato pedido pelo enunciado (teste, pergunta,
resposta recebida, data):

- Falhas do sistema AURA: tabela resumo no topo do arquivo, com link pra cada seção de detalhe.
- Respostas malformadas nas perguntas de fairness: o par gênero vem malformado em 10 de 10 chamadas; investigação com repetição (`data/repeticoes_fairness.json`, gerado por `scripts/medir_taxa_falha_fairness.py`).
- Recusa fora de escopo não usa a frase padrão: as 5 perguntas fora de escopo do golden dataset nunca usam a frase "essa informação não está disponível" pedida no enunciado.
- Falso positivo conhecido na checagem de alucinação: um caso em que o extrator de fatos confunde um número que o próprio usuário informou com um fato do banco; não é falha da AURA.
- Indisponibilidade de infraestrutura: ocorrências de cota esgotada e erro interno do servidor durante os testes.
