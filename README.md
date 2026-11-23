# TP2: Contratos de configuração, permissões e hooks no Claude Code

**Aluno:** João Pedro Barboza · **Disciplina:** DR3

Comece pelo **[RELATORIO-TECNICO.md](RELATORIO-TECNICO.md)**: ele resume a solução de cada exercício e aponta para o documento detalhado e para as evidências reais.

| Exercício | Documento | Evidência principal |
|---|---|---|
| 1. Escopos | [docs/ex01-escopos.md](docs/ex01-escopos.md) | [escopos/](escopos/), [debug de confiança](docs/evidencias/sessoes/ex02-0-debug-confianca.md) |
| 2. allow/deny/ask | [docs/ex02-allow-deny-ask.md](docs/ex02-allow-deny-ask.md) | [tela interativa](docs/evidencias/telas/ex02-dev-allow-e-ask.md), [consultor](docs/evidencias/sessoes/ex02-b-consultor-deny.md) |
| 3. Specifier/wildcard | [docs/ex03-specifier-wildcard.md](docs/ex03-specifier-wildcard.md) | [sessão](docs/evidencias/sessoes/ex03-sql-leitura-e-migration-escrita.md) |
| 4. Modos | [docs/ex04-modos-permissao.md](docs/ex04-modos-permissao.md) | [tela plan](docs/evidencias/telas/ex04-demo-diretoria-plan.md), [transcrição](docs/evidencias/sessoes/ex04-demo-diretoria-interativa.md) |
| 5. Diretórios | [docs/ex05-diretorios.md](docs/ex05-diretorios.md) | [bloqueado](docs/evidencias/sessoes/ex05-a-dados-pacientes-bloqueado.md), [autorizado](docs/evidencias/sessoes/ex05-b-dados-pacientes-autorizado.md) |
| 6. Eventos/handlers | [docs/ex06-eventos-handlers.md](docs/ex06-eventos-handlers.md) | [formatar_lint.py](servico-agendamento/.claude/hooks/formatar_lint.py) |
| 7. matcher + if | [docs/ex07-matcher-if.md](docs/ex07-matcher-if.md) | [dispara](docs/evidencias/sessoes/ex07-a-hook-dispara-app.md), [não dispara](docs/evidencias/sessoes/ex07-b-hook-nao-dispara-teste.md), [experimento](docs/evidencias/experimentos/if-negacao.md) |
| 8. Pre/PostToolUse | [docs/ex08-pre-post-tooluse.md](docs/ex08-pre-post-tooluse.md) | [deny](docs/evidencias/sessoes/ex08-a-pretooluse-deny-infra.md), [log](docs/evidencias/logs/auditoria.jsonl) |
| 9. Padrão | [padrao-hooks/PADRAO.md](padrao-hooks/PADRAO.md), [docs/ex09-padrao-consolidado.md](docs/ex09-padrao-consolidado.md) | [reuso em outro projeto](docs/evidencias/sessoes/ex09-reuso-outra-squad.md) |

## Reproduzir

```bash
cd servico-agendamento
python3 -m venv .venv && .venv/bin/pip install ruff pytest
.venv/bin/pytest -q                                   # 5 passed
claude                                                # aceite "Trust this folder"
python3 ../padrao-hooks/instalar.py --verificar .     # settings.json ALINHADO com o padrão
```

Os cenários headless podem ser repetidos com `python3 -I docs/evidencias/rodar_cenario.py <nome> <dir> "<prompt>" [-- flags]`.
