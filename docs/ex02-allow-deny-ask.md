# Ex. 2: allow, deny e ask por perfil de acesso

## Configuração

### Equipe de desenvolvimento: [`servico-agendamento/.claude/settings.json`](../servico-agendamento/.claude/settings.json)

```json
"allow": [
  "Edit(/agendamento/**)", "Edit(/tests/**)",
  "Read(**/*.sql)",
  "Bash(.venv/bin/pytest *)", "Bash(.venv/bin/ruff *)",
  "Bash(git status *)", "Bash(git diff *)", "Bash(git log *)"
],
"ask":  [ "Edit(/db/migrations/**)", "Edit(**/migration_*)" ],
"deny": [ "Read(./.env)", "Read(./.env.*)", "Bash(git push *)", "Bash(rm -rf *)" ]
```

- **allow**: editar a aplicação e os testes, rodar testes e lint. O `/` no início ancora o caminho na raiz do projeto, então `Edit(/agendamento/**)` não casa uma pasta `agendamento` aninhada em outro lugar. `Edit` cobre todas as ferramentas que alteram arquivo (Edit, Write, NotebookEdit). Uma regra `Write(path)` não teria efeito.
- **ask**: qualquer alteração na pasta de migrações pede confirmação **mesmo para o dev interno**. Uma regra `ask` explícita está na lista de ações que *nenhum modo aprova sozinho*: ela vence o `acceptEdits`, que é o modo padrão da squad (`defaultMode`), e vence até um `permissionDecision: "allow"` devolvido pelo hook do Ex. 8.
- **deny**: credenciais e ações destrutivas que ninguém da squad faz pelo agente.

### Consultor externo de segurança: [`servico-agendamento/.claude/perfis/consultor-seguranca.json`](../servico-agendamento/.claude/perfis/consultor-seguranca.json)

- `defaultMode: "dontAsk"`: o que não está pré-aprovado é **negado sem perguntar**.
- `allow`: só comandos de leitura (`ls`, `grep`, `rg`, `find`, `wc`, `git log/diff/status`).
- `deny`: as ferramentas de escrita inteiras (`Edit`, `Write`, `NotebookEdit`). Um deny de nome de ferramenta sem especificador **remove a ferramenta do contexto do Claude**, de modo que ela nem aparece para o modelo. Também negados: interpretadores e executores (`python*`, `.venv/*`, `pytest`, `bash`, `sh`), comandos que alteram arquivo (`rm`, `mv`, `cp`, `touch`, `tee`, `sed -i`), git de escrita, `terraform`, `psql` e rede.

Por que **deny explícito + dontAsk**, e não só a ausência de allow: o `dontAsk` cobre o que ninguém previu (ex.: `printf >> arquivo`). O deny explícito continua valendo se alguém trocar o modo, e deixa a intenção documentada. Ex. 1 explica por que, em produção, esse perfil vive no escopo managed.

### Analista de dados (extra): [`servico-agendamento/.claude/perfis/analista-dados.json`](../servico-agendamento/.claude/perfis/analista-dados.json)

Lê `relatorios/` e `db/consultas/`. Leitura de `agendamento/`, `tests/` e dos hooks negada; nenhuma escrita.

## Testes reais e comportamento observado

Todas as sessões foram executadas com Claude Code 2.1.281. Cada transcrição tem um `.md` legível, gerado a partir do `.jsonl` bruto por [`rodar_cenario.py`](evidencias/rodar_cenario.py).

### 0. Antes de confiar na pasta (achado do teste)

Na primeira rodada, o `pytest` foi **negado** mesmo estando no `allow`. O log de debug mostrou o motivo: o Claude Code descarta os `allow` do escopo project até alguém aceitar *Trust this folder* ([`ex02-0-debug-confianca.md`](evidencias/sessoes/ex02-0-debug-confianca.md), [`ex02-0-antes-da-confianca.md`](evidencias/sessoes/ex02-0-antes-da-confianca.md)). Os `deny`/`ask` continuaram valendo. O diálogo de confiança real lista as 8 regras que serão concedidas ([`telas/ex02-dialogo-confianca.md`](evidencias/telas/ex02-dialogo-confianca.md)):

```
⚠ This folder pre-approves 8 tool permissions in .claude/settings.json:
  Edit(/agendamento/**), Edit(/tests/**), Bash(.venv/bin/pytest *), Bash(.venv/bin/ruff *), Bash(git status *), ...
```

### 1. Desenvolvedor: allow e ask (sessão interativa, pasta confiada)

Prompt: (1) trocar a docstring de `cancelar` em `agendamento/consultas.py`; (2) rodar `.venv/bin/pytest -q`; (3) acrescentar uma linha a `db/migrations/migration_002_indice_medico_data.sql`.
Telas: [`telas/ex02-dev-allow-e-ask.md`](evidencias/telas/ex02-dev-allow-e-ask.md) e [`telas/ex02-dev-transcricao-expandida.md`](evidencias/telas/ex02-dev-transcricao-expandida.md). Log bruto: [`sessoes/ex02-a-dev-interativa.jsonl`](evidencias/sessoes/ex02-a-dev-interativa.jsonl).

| Tentativa | Regra | Comportamento observado |
|---|---|---|
| Edit em `agendamento/consultas.py` | allow `Edit(/agendamento/**)` | Executou **sem perguntar** (`● Update(agendamento/consultas.py) ⎿ Added 1 line, removed 1 line`) |
| `.venv/bin/pytest -q` | allow `Bash(.venv/bin/pytest *)` | Executou **sem perguntar**: `5 passed in 0.01s` |
| Edit em `db/migrations/migration_002_...sql` | ask `Edit(/db/migrations/**)` | **Parou e pediu confirmação** mesmo em `⏵⏵ accept edits on`: `Do you want to make this edit to migration_002_indice_medico_data.sql? ❯ 1. Yes 2. No`. Respondi **No**: `User rejected update`. O arquivo ficou intacto |

O log de auditoria do Ex. 8 registrou que o hook PreToolUse devolveu `"decisao": "allow"` para a migration ([`logs/auditoria.jsonl`](evidencias/logs/auditoria.jsonl), 12:48:29), e ainda assim o Claude Code perguntou. Isso prova que **a regra `ask` prevalece sobre o `allow` do hook**.

### 2. Consultor de segurança: deny ([`sessoes/ex02-b-consultor-deny.md`](evidencias/sessoes/ex02-b-consultor-deny.md))

Comando: `claude -p "..." --settings .claude/perfis/consultor-seguranca.json` (o init registra `permissionMode=dontAsk`).

| Tentativa | Comportamento observado |
|---|---|
| `ls agendamento` | ✅ Permitido |
| `grep -rn cancelar agendamento/` | ✅ Permitido (`agendamento/consultas.py:41:def cancelar...`) |
| `Read agendamento/consultas.py` | ✅ Permitido |
| Acrescentar `# auditado` ao arquivo | ⛔ O Claude **não tinha** a ferramenta Edit/Write ("Não tenho uma ferramenta Edit/Write nesta sessão") e tentou `printf ... >> consultas.py`, que foi **negado**: `Permission to use Bash has been denied because Claude Code is running in don't ask mode` |
| `.venv/bin/pytest -q` | ⛔ `Permission to use Bash with command .venv/bin/pytest -q has been denied.` |
| `git commit -m auditoria` | ⛔ `Permission to use Bash with command git commit -m auditoria has been denied.` |

`permission_denials` traz as 3 negações, e `consultas.py` não foi alterado. A tentativa do `printf` mostra por que o `dontAsk` é necessário além do deny: o modelo procurou outro caminho de escrita, e o modo fechou esse caminho sem que alguém precisasse prevê-lo.

### 3. Analista de dados ([`sessoes/ex01-analista-dados.md`](evidencias/sessoes/ex01-analista-dados.md))

Leu `relatorios/ocupacao.md` e `db/consultas/ocupacao_por_medico.sql` ✅. A leitura de `agendamento/consultas.py` foi negada (`File is in a directory that is denied by your permission settings`), e a criação de `relatorios/novo.md` via shell também (`don't ask mode`).
