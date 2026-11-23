# Ex. 8: PreToolUse com `permissionDecision` e PostToolUse de auditoria

## Configuração

Em [`servico-agendamento/.claude/settings.json`](../servico-agendamento/.claude/settings.json):

```json
"PreToolUse": [
  {
    "matcher": "Write|Edit|NotebookEdit",
    "hooks": [
      { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/guarda_escrita.py\"",
        "timeout": 15,
        "statusMessage": "Checando política de escrita da squad" }
    ]
  }
],
"PostToolUse": [
  ... (formatação do Ex. 7) ...,
  {
    "matcher": "Write|Edit|NotebookEdit|Bash",
    "hooks": [
      { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/auditar.py\"",
        "timeout": 15 }
    ]
  }
]
```

### Hook de controle: [`guarda_escrita.py`](../servico-agendamento/.claude/hooks/guarda_escrita.py)

O matcher **sem `if`** intercepta **toda** ferramenta de escrita de arquivo (`Write`, `Edit` e `NotebookEdit`), em qualquer caminho. O hook resolve o caminho real (`realpath`, que desfaz `..` e symlinks) e devolve, sempre com exit 0, um JSON como este:

```json
{ "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Bloqueado pela política da squad: '…/infra/deploy_producao.sh' está em 'infra/', pasta restrita …" } }
```

| Situação | `permissionDecision` | Por quê |
|---|---|---|
| Alvo em `../infra` ou `../dados-teste` (inclusive via symlink) | **`deny`** | Pasta restrita do Ex. 5 |
| Alvo em `.claude/` do projeto | `ask` | O agente não altera os próprios guardrails sem um humano |
| Alvo em `~/.claude/plans/` | `allow` | Arquivo interno do modo `plan` (achado no teste do Ex. 4) |
| Alvo fora do projeto (outros casos) | `ask` | O hook não aprova às cegas o que não conhece |
| **Demais casos** (dentro do projeto) | **`allow`** | Conforme o enunciado |
| Evento sem `file_path`, JSON inválido ou exceção | **`deny`** | **Fail-closed:** se a checagem quebrar, a escrita não passa sem checagem |

**Interação com as regras (documentação + teste):** o `allow` do hook pula o prompt do modo, mas **não** derruba `deny` nem `ask` das regras. As migrations continuaram pedindo confirmação com o hook devolvendo `allow` (Ex. 2 e 3). Já o `deny` do hook vence até um `allow` das regras.

### Hook de registro: [`auditar.py`](../servico-agendamento/.claude/hooks/auditar.py)

Ferramentas **consideradas sensíveis pela squad** (definidas no matcher): `Write`, `Edit`, `NotebookEdit` (alteram arquivo) e `Bash` (executa comando). Para cada execução bem-sucedida, grava uma linha JSON em `logs/auditoria.jsonl` com `ts`, `ferramenta`, `arquivo` (ou `comando`, no caso de Bash), `modo` de permissão e `sessao`. O `guarda_escrita.py` também registra a **decisão** de cada PreToolUse no mesmo arquivo, então a trilha mostra o que foi tentado e negado e o que foi executado. O hook de auditoria **nunca bloqueia**: sai com 0 mesmo se falhar, para auditoria não travar o trabalho.

`logs/` está no `.gitignore`: o log é local, como pede o enunciado.

## Demonstração

### Caso bloqueado ([`sessoes/ex08-a-pretooluse-deny-infra.md`](evidencias/sessoes/ex08-a-pretooluse-deny-infra.md))

Sessão iniciada com **`--add-dir ../infra`**: a pasta entrou no diretório de trabalho, então nem o Ex. 5 nem as regras impediriam a edição. O Claude foi instruído a editar `../infra/deploy_producao.sh` e depois `agendamento/notificacoes.py`.

```
Claude chama Edit: /home/jowlt/TP2-AC/infra/deploy_producao.sh
hook_response PreToolUse:Edit {"hookSpecificOutput": {"hookEventName": "PreToolUse",
   "permissionDecision": "deny", "permissionDecisionReason": "Bloqueado pela política da squad:
   '/home/jowlt/TP2-AC/infra/deploy_producao.sh' está em 'infra/', pasta restrita ..."}}
  ↳ ERRO/BLOQUEIO: PreToolUse:Edit hook error: Bloqueado pela política da squad: ...

Claude chama Edit: /home/jowlt/TP2-AC/servico-agendamento/agendamento/notificacoes.py
hook_response PreToolUse:Edit {... "permissionDecision": "allow", "permissionDecisionReason":
   "Checagem de escrita OK: alvo dentro do projeto e fora de pastas restritas."}
  ↳ resultado: The file ... has been updated successfully.
```

Verificação independente: `diff` entre a cópia de antes e `infra/deploy_producao.sh` saiu **vazio**, com o arquivo intacto. A linha adicionada em `notificacoes.py` foi revertida depois do teste.

Teste unitário dos casos de borda (fora do Claude, mandando JSON ao script): symlink `atalho-infra → ../infra` deu **deny**; `/tmp/fora.txt` deu **ask**; entrada `not json` deu **deny** por fail-closed.

### Caso registrado ([`sessoes/ex08-b-posttooluse-registro.md`](evidencias/sessoes/ex08-b-posttooluse-registro.md))

O Claude rodou `.venv/bin/pytest -q` e editou a docstring de `agendamento/notificacoes.py`. Linhas novas em `logs/auditoria.jsonl` ([`evidencias/sessoes/ex08-b-trecho-auditoria.jsonl`](evidencias/sessoes/ex08-b-trecho-auditoria.jsonl)):

```json
{"ts": "2026-11-23T12:54:07-03:00", "evento": "PostToolUse", "ferramenta": "Bash", "arquivo": null, "comando": ".venv/bin/pytest -q 2>&1 | tail -30", "modo": "acceptEdits", "sessao": "7cf8fc37-…"}
{"ts": "2026-11-23T12:54:09-03:00", "evento": "PreToolUse", "ferramenta": "Edit", "arquivo": "/home/jowlt/TP2-AC/servico-agendamento/agendamento/notificacoes.py", "decisao": "allow", "modo": "acceptEdits", "sessao": "7cf8fc37-…"}
{"ts": "2026-11-23T12:54:09-03:00", "evento": "PostToolUse", "ferramenta": "Edit", "arquivo": "/home/jowlt/TP2-AC/servico-agendamento/agendamento/notificacoes.py", "comando": null, "modo": "acceptEdits", "sessao": "7cf8fc37-…"}
```

### Log completo do TP

[`evidencias/logs/auditoria.jsonl`](evidencias/logs/auditoria.jsonl) acumula todas as sessões feitas em `servico-agendamento/`: **47 registros**, sendo 26 PostToolUse, 17 PreToolUse `allow`, 2 `ask` e 2 **`deny`** (`infra/main.tf` no teste unitário e `infra/deploy_producao.sh` na sessão real).
