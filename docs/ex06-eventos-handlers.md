# Ex. 6: Eventos de hook e tipos de handler

## Eventos relevantes para "formatar e checar lint a cada edição de Python"

| Evento | Quando dispara no ciclo | Relevância para esta automação |
|---|---|---|
| **`PostToolUse`** | **Logo depois** que uma ferramenta termina **com sucesso** (o arquivo já foi gravado) | ✅ **Escolhido.** É o único momento em que o arquivo editado já existe em disco no estado novo. Rodar `ruff format` antes seria formatar a versão velha. O hook recebe `tool_input.file_path`, e um exit 2 devolve o erro de lint ao Claude no mesmo turno, para ele corrigir |
| `PreToolUse` | **Antes** de a ferramenta executar, depois que o Claude montou os parâmetros | Não serve para formatar, porque o arquivo ainda não mudou. Serve para **barrar** a edição (usado no Ex. 8) |
| `PostToolUseFailure` | Depois que a ferramenta **falha** | Não formata nada (não houve gravação). Útil só para registrar falhas |
| `PostToolBatch` | Depois que um **lote** de chamadas paralelas termina | Alternativa para rodar um lint único sobre vários arquivos editados em paralelo. Não foi usado porque perde a correspondência "este arquivo, este erro" |
| `Stop` | Quando o Claude **termina de responder** ao turno | Alternativa para um lint final do projeto inteiro antes de devolver o controle. Mais barato, mas o erro aparece tarde, depois de várias edições |
| `SessionStart` | Início ou retomada da sessão | Pode verificar se `ruff` está instalado no `.venv`. Não faz a checagem em si |
| `FileChanged` | Quando um arquivo **observado** muda no disco, por qualquer origem | Não serve: dispararia também com edições humanas no editor, fora do controle do Claude |

**Matcher.** Em eventos de ferramenta, o `matcher` filtra pelo **nome da ferramenta**: `"Edit|Write"` cobre as duas ferramentas que gravam arquivos `.py`. O filtro pelo **caminho** (`.py`, pasta) é feito pelo campo `if` (Ex. 7).

## Handler `command` especificado

No [`servico-agendamento/.claude/settings.json`](../servico-agendamento/.claude/settings.json) (a versão inicial, antes do refinamento do Ex. 7, era um único handler sem `if`):

```json
"PostToolUse": [
  {
    "matcher": "Edit|Write",
    "hooks": [
      {
        "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/formatar_lint.py\"",
        "timeout": 60,
        "statusMessage": "ruff format + ruff check"
      }
    ]
  }
]
```

Script: [`.claude/hooks/formatar_lint.py`](../servico-agendamento/.claude/hooks/formatar_lint.py).

1. Lê o evento JSON da entrada padrão e pega `tool_input.file_path`.
2. Se não for `.py`, sai com 0 (salvaguarda; o filtro principal é o `if`).
3. Roda o **formatador** `ruff format <arquivo>` e o **lint** `ruff check <arquivo>`, preferindo o `ruff` do `.venv` do projeto (versão fixada para toda a squad).
4. Registra o resultado em `logs/qualidade.log`.
5. Se o lint falhar, sai com **código 2** e escreve o relatório no stderr. Em `PostToolUse`, isso devolve a mensagem ao Claude, que corrige o arquivo no mesmo turno, sem o dev precisar rodar nada.

Comando e ferramenta ficam em [`politica.json`](../servico-agendamento/.claude/hooks/politica.json) (`"formatador": ["ruff","format"]`, `"linter": ["ruff","check"]`). Outra squad troca para `black`/`flake8` sem mexer no script.

Execução real (Ex. 7, [`sessoes/ex07-a-hook-dispara-app.md`](evidencias/sessoes/ex07-a-hook-dispara-app.md)): o Claude inseriu de propósito `def   duracao_turno( nome ):` / `inicio,fim=TURNOS[ nome ]`, e o arquivo ficou em disco como `def duracao_turno(nome):` / `inicio, fim = TURNOS[nome]`. Log:

```
Edit .../agendamento/turnos.py | format: 1 file reformatted | lint rc=0: All checks passed!
```

`$CLAUDE_PROJECT_DIR` garante que o script é achado mesmo se o Claude tiver feito `cd` para uma subpasta.

## Quando `http` ou `prompt` seriam mais adequados que `command`

### `http`: notificar o sistema de auditoria central quando uma migration for aprovada

**Situação concreta no mesmo projeto:** o compliance do hospital quer que **toda alteração em `migration_*` aprovada no prompt** (Ex. 3) chegue, em tempo real, ao serviço central de trilha de auditoria que já existe na empresa (`https://auditoria.interno/api/eventos`), junto com as alterações feitas fora do Claude.

```json
"PostToolUse": [
  {
    "matcher": "Edit|Write",
    "hooks": [
      {
        "type": "http",
        "if": "Edit(**/migration_*)",
        "url": "https://auditoria.interno/api/claude-code/eventos",
        "headers": { "Authorization": "Bearer $AUDITORIA_TOKEN" },
        "allowedEnvVars": ["AUDITORIA_TOKEN"],
        "timeout": 10
      }
    ]
  }
]
```

**Por que `http` e não `command` + `curl`:**

- O Claude Code faz o POST do JSON do evento diretamente. Não há script para manter, quotar ou versionar em cada máquina, nem dependência de `curl`/`jq` instalados.
- **Segredo controlado:** o token só é interpolado porque está em `allowedEnvVars`. Qualquer outra variável vira string vazia. Num `command`, o script tem acesso a todo o ambiente.
- A resposta do servidor usa o **mesmo formato de saída** dos hooks. O serviço central pode responder `{"decision": "block", ...}` e a política passa a ser decidida centralmente, sem redistribuir scripts.
- Falha de rede é tratada como erro não bloqueante. A auditoria não trava o trabalho, mas pode ser endurecida com `onFailure: "block"` quando a versão suportar.

### `prompt`: julgar se um comando SQL é destrutivo antes de rodar

**Situação concreta:** devs às vezes pedem ao Claude para rodar `psql -c "..."` contra o banco **local** de desenvolvimento. Bloquear `psql` inteiro atrapalha, e escrever uma regex que distinga `DELETE FROM consultas WHERE id = 3` (ok em dev) de `DELETE FROM consultas` sem `WHERE`, `TRUNCATE` ou `UPDATE` sem filtro é frágil (CTEs, comentários, maiúsculas, múltiplas instruções).

```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      {
        "type": "prompt",
        "if": "Bash(psql *)",
        "prompt": "Você é o revisor de SQL da squad de agendamento. Analise o comando abaixo. Se ele contiver DELETE ou UPDATE sem WHERE, TRUNCATE, DROP ou ALTER, responda com permissionDecision \"ask\" e explique o risco em permissionDecisionReason. Caso contrário responda \"allow\". Responda só JSON no formato {\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"allow|ask\",\"permissionDecisionReason\":\"...\"}}.\n\n$ARGUMENTS",
        "timeout": 30
      }
    ]
  }
]
```

**Por que `prompt` e não `command`:** a decisão exige **interpretar semântica** (o `WHERE` está dentro de uma subquery? É um comentário?), e não casar texto. O handler `prompt` manda o evento (`$ARGUMENTS`) para um modelo rápido e usa a resposta como decisão, com o mesmo `permissionDecision` dos outros handlers. O `if: "Bash(psql *)"` garante que o custo e a latência de uma chamada de modelo só ocorrem para comandos `psql`, e não para todo Bash.

**Regra geral usada pela squad:**

| Tipo | Quando usar |
|---|---|
| `command` | Ação **determinística e local**: formatar, rodar lint, checar caminho, gravar log. Rápido, testável, sem rede (Ex. 6, 7, 8) |
| `http` | Integrar com **serviço externo** já existente (auditoria, SIEM, Slack, aprovação central), com segredos controlados por `allowedEnvVars` |
| `prompt` | Decisão que exige **julgamento** sobre texto livre, que regex não resolve com segurança. Sempre com `if` estreito, pelo custo e latência |
