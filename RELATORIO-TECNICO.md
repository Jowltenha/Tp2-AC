# Relatório Técnico: TP2, Contratos de configuração, permissões e hooks no Claude Code

**Projeto:** Serviço de Agendamento de Consultas Médicas
**Autor:** João Pedro Barboza
**Ambiente:** Claude Code 2.1.281 (binário Linux, WSL2), Python 3.14, ruff 0.17.6, pytest 9.2
**Data:** 23/11/2026

## Visão geral

Todos os exercícios foram feitos sobre **um único repositório** (`TP2-AC/`). A aplicação fica em `servico-agendamento/`, ao lado de `infra/` e `dados-teste/`, que são as pastas restritas. A configuração do Claude Code fica em `servico-agendamento/.claude/`, e toda ela é gerada pelo padrão do Ex. 9 (`padrao-hooks/`).

**Evidências.** Toda demonstração vem de **sessões reais** do Claude Code:

- **Interativas** (Ex. 2 e Ex. 4), conduzidas em `tmux` e capturadas com `tmux capture-pane`, em [`docs/evidencias/telas/`](docs/evidencias/telas/). O `.jsonl` que o próprio Claude Code grava foi convertido em transcrição.
- **Headless** (`claude -p --output-format stream-json --include-hook-events`), conduzidas por [`rodar_cenario.py`](docs/evidencias/rodar_cenario.py), que grava o `.jsonl` bruto e gera o `.md` sem edição manual, em [`docs/evidencias/sessoes/`](docs/evidencias/sessoes/).
- **Logs dos hooks**, em [`docs/evidencias/logs/`](docs/evidencias/logs/).
- Execuções que revelaram problemas foram **mantidas** em [`execucoes-anteriores/`](docs/evidencias/execucoes-anteriores/), porque elas justificam decisões.

Estado final verificado: `pytest` → **5 passed**. `ruff check` dos módulos da aplicação → **All checks passed**. `instalar.py --verificar servico-agendamento` → **ALINHADO**.

---

## Ex. 1: Escopos ([`docs/ex01-escopos.md`](docs/ex01-escopos.md))

**Solução:** cada contrato fica no escopo mais estreito que alcança todo o seu público.

| Escopo | Conteúdo | Exemplo |
|---|---|---|
| managed | Política da empresa e perfil do consultor (na máquina dele) | `deny` de `.env`/`~/.ssh`; `allowManagedPermissionRulesOnly` |
| user | Preferências pessoais | `language`, hook de notificação |
| project | Contrato da squad | `ask` em migrations, hooks |
| local | Credenciais e ajustes de uma pessoa | `AGENDAMENTO_DB_URL` com senha |

**Project × local:** credencial pessoal vai no **local** (gitignored). Regra da squad vai no **project** (versionado).

**Risco:** o perfil do consultor no escopo local pode ser apagado ou afrouxado por ele mesmo. Além disso, as listas se somam entre escopos, então ele herdaria o `allow` de escrita do projeto, sem rastro no git. No project, o perfil bloquearia a squad de dev. **Escopo correto: managed**, com `allowManagedPermissionRulesOnly`.

**Achado do teste:** antes do *Trust this folder*, o Claude Code descarta os `allow` do project e mantém os `deny`/`ask` (log de debug), o que mostra que o project restringe sempre mas só concede com confiança.

## Ex. 2: allow / deny / ask ([`docs/ex02-allow-deny-ask.md`](docs/ex02-allow-deny-ask.md))

**Solução:**

- **Dev** (`settings.json`): `allow` de `Edit(/agendamento/**)`, `Edit(/tests/**)`, `pytest`, `ruff` e git de leitura; `ask` de `Edit(/db/migrations/**)`.
- **Consultor** (`perfis/consultor-seguranca.json`): `defaultMode: dontAsk`, `allow` só de comandos de leitura, `deny` de `Edit`/`Write`/`NotebookEdit` (a ferramenta some do contexto) e de executores e comandos que alteram arquivo.

**Comportamento observado:**

| Perfil | Ação | Resultado |
|---|---|---|
| Dev (interativo, `acceptEdits`) | Edit da app | executou sem perguntar |
| Dev | pytest | `5 passed`, sem perguntar |
| Dev | Edit da migration | **prompt** `Do you want to make this edit…?`, mesmo com o hook devolvendo `allow`; respondi *No* e o arquivo ficou intacto |
| Consultor | ls, grep, Read | permitidos |
| Consultor | escrita | o modelo tentou `printf >>` e foi negado pelo `dontAsk` |
| Consultor | pytest, `git commit` | negados (`permission_denials` = 3) |

**Decisão justificada:** deny explícito **e** `dontAsk`. O teste mostrou o modelo procurando um caminho que o deny não previa.

## Ex. 3: Specifier e wildcard ([`docs/ex03-specifier-wildcard.md`](docs/ex03-specifier-wildcard.md))

**Solução:** `allow: Read(**/*.sql)` e `ask: Edit(**/migration_*)`. São specifiers diferentes (`Read` × `Edit`) para leitura e escrita, e `**/` torna a regra independente de pasta.

**Demonstração (6 caminhos reais):**

- 3 leituras de `.sql` livres, inclusive de arquivos `migration_*`.
- Edit em `db/consultas/ocupacao_por_medico.sql` passou (controle: a regra não pega todo `.sql`).
- Edit em `relatorios/sql/migration_003_view_ocupacao.sql`, **fora** de `db/migrations/`, pediu confirmação. Edit em `db/migrations/migration_002…` também.

**Justificativa:** o wildcard protege migrations futuras e fora do lugar. A lista manual envelhece e falha em silêncio. O custo do falso positivo (um prompt) é muito menor que o do falso negativo (migration alterada sem revisão).

## Ex. 4: Modos de permissão ([`docs/ex04-modos-permissao.md`](docs/ex04-modos-permissao.md))

**Avaliação:** `default`, `acceptEdits`, `plan`, `auto`, `dontAsk` e `bypassPermissions`, com a ordem de decisão deny → ask → hook → allow → modo, que responde à dúvida do dev júnior.

**Recomendação:**

- **Dia a dia:** `acceptEdits`. A segurança vem das regras e dos hooks, que valem em qualquer modo.
- **Revisão de segurança:** `dontAsk` + perfil somente-leitura no managed.
- **Diretoria:** `plan`.

**Prática:** sessão **interativa** com `--permission-mode plan`, pedindo explicitamente para *aplicar* a mudança. O Claude leu o código, escreveu só o plano em `~/.claude/plans/`, parou em *"Would you like to proceed?"* e eu rejeitei. `md5sum -c` de `consultas.py` deu **OK** (inalterado).

**Achado:** a primeira rodada headless mostrou que o hook do Ex. 8 pedia confirmação para o arquivo de plano (fora do projeto). O hook foi ajustado para liberar `~/.claude/plans`.

## Ex. 5: Diretórios ([`docs/ex05-diretorios.md`](docs/ex05-diretorios.md))

**Solução:** `infra/` e `dados-teste/` ficam **fora** do diretório de trabalho (`servico-agendamento/`), com `blockReadsOutsideWorkingDirectories: true` e sem `additionalDirectories`. Os dados de paciente só entram com `--add-dir ../dados-teste`, que é explícito e dura uma sessão. A escrita nas duas pastas é negada pelo hook do Ex. 8, inclusive com `--add-dir` e via symlink.

**Teste:**

- **Bloqueado:** `Reads outside the working directories are blocked`, tanto para o CSV quanto para `infra/`.
- **Autorizado:** com `--add-dir ../dados-teste`, o Claude leu o CSV (3 pacientes, 3 convênios), e `infra/` continuou bloqueada na mesma sessão.

## Ex. 6: Eventos e handlers ([`docs/ex06-eventos-handlers.md`](docs/ex06-eventos-handlers.md))

**Eventos avaliados:** `PostToolUse` (escolhido: o arquivo já está gravado), `PreToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Stop`, `SessionStart` e `FileChanged`, com o momento de cada um e o motivo de uso ou descarte.

**Handler `command`:** `formatar_lint.py` roda `ruff format` e `ruff check` no `file_path` e, se o lint falhar, sai com exit 2 para o Claude corrigir no mesmo turno. Os comandos ficam parametrizados em `politica.json`.

**`http`:** enviar alterações de `migration_*` à trilha de auditoria central, com o token só via `allowedEnvVars`.

**`prompt`:** julgar se um `psql -c` é destrutivo (DELETE sem WHERE etc.), onde regex é frágil. Sempre com `if: "Bash(psql *)"`.

## Ex. 7: matcher + if ([`docs/ex07-matcher-if.md`](docs/ex07-matcher-if.md))

**Solução:**

- `matcher: "Edit|Write"` restringe às ferramentas de escrita.
- `if: "Edit(/agendamento/**/<classe>*.py)"` restringe a `.py` da pasta da app.
- **Cinco classes positivas** cuja união é "nome não começa com `test_`".
- A guarda no script é a segunda camada.

**Decisão justificada por experimento:**

- `Edit(!**/test_*.py)` nunca casa. `[!t]` casou `test_*.py`.
- Classes com `A-Z` casaram `test_conflito_horario.py` na primeira execução real, porque o casamento é case-insensitive. Só a guarda do script evitou o estrago.
- Por isso as classes finais usam só minúsculas, dígitos e `_`. A partição foi verificada com 12 nomes.

**Demonstração:**

- `agendamento/turnos.py` (começa com `t`): o hook disparou e `def   duracao_turno( nome ):` virou `def duracao_turno(nome):`.
- `agendamento/test_conflito_horario.py`, na **mesma pasta**: o hook não disparou (só a auditoria rodou) e a tabela alinhada à mão foi preservada.

## Ex. 8: PreToolUse / PostToolUse ([`docs/ex08-pre-post-tooluse.md`](docs/ex08-pre-post-tooluse.md))

**PreToolUse** (`Write|Edit|NotebookEdit`, sem `if`): o `guarda_escrita.py` resolve `realpath` e devolve `permissionDecision`:

- `deny` para `infra/` e `dados-teste/`;
- `ask` para `.claude/` e para caminhos fora do projeto;
- `allow` nos demais casos;
- **fail-closed** se o próprio hook falhar.

**PostToolUse** (`Write|Edit|NotebookEdit|Bash`): o `auditar.py` grava em `logs/auditoria.jsonl` a ferramenta, o arquivo ou comando, o modo e a sessão. A decisão do Pre também é registrada.

**Demonstração:**

- Com `--add-dir ../infra`, o Edit em `infra/deploy_producao.sh` recebeu **deny** (`diff` vazio) e o Edit na app recebeu **allow**.
- Registro: `pytest` (Bash) e Edit de `notificacoes.py` aparecem no log.
- Log total do TP: 47 registros, 2 `deny`.

## Ex. 9: Padrão consolidado ([`padrao-hooks/PADRAO.md`](padrao-hooks/PADRAO.md), [`docs/ex09-padrao-consolidado.md`](docs/ex09-padrao-consolidado.md))

**Solução:**

- `padrao.json` (fonte única) → `instalar.py` → `settings.json` + `politica.json` + hooks + perfis.
- `--verificar` serve como checagem de CI.
- O `PADRAO.md` documenta as peças **P1–P14**, cada uma com o problema que resolve e o exercício de origem, mais as regras de composição.

**Provas:**

1. O `servico-agendamento` reinstalado pelo gerador ficou **idêntico** ao settings testado nos Ex. 2–8.
2. Um projeto novo (`squad-faturamento`), gerado do zero, teve formatação no app e não no teste, deny em `../infra-fat` com `--add-dir`, e `--verificar` acusou a edição manual.

**Justificativa** (resumo da seção do doc):

- uma fonte e artefatos gerados;
- desvio detectável no CI;
- a armadilha do `if` codificada no gerador;
- escopos certos com precedência a favor da restrição;
- segurança independente do modo de cada dev;
- defesa em profundidade que se mostrou necessária nos testes.

---

## Mapa da entrega

```
TP2-AC/
├── RELATORIO-TECNICO.md            ← este arquivo
├── README.md
├── servico-agendamento/            ← projeto (código, SQL, testes)
│   └── .claude/  settings.json · hooks/ · perfis/
├── infra/  dados-teste/            ← pastas restritas (Ex. 5, 8)
├── escopos/                        ← exemplos managed / user / local (Ex. 1)
├── padrao-hooks/                   ← padrão reutilizável (Ex. 9)
└── docs/
    ├── ex01…ex09-*.md              ← um documento por exercício
    └── evidencias/
        ├── sessoes/  telas/  logs/  experimentos/  execucoes-anteriores/
        └── rodar_cenario.py · transcrever_sessao.py
```
