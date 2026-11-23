# Ex. 1: Contratos de configuração por escopo

**Projeto:** serviço de agendamento de consultas (`servico-agendamento/`).
**Públicos:** squad de back-end (escreve e testa), consultor externo de segurança (só lê), analista de dados (só consulta relatórios).

## Regra que orienta a divisão

Cada contrato fica no escopo **mais estreito que ainda alcança todo o público dele**. Se o escopo for largo demais, a mudança vaza para outros públicos. Se for estreito demais, a regra fica dependendo de cada pessoa lembrar de configurá-la.

A precedência no Claude Code é: managed > linha de comando (`--settings`) > local > project > user. Listas como `permissions.allow`/`deny`/`ask` **se somam** entre escopos, e um `deny` em qualquer escopo vence um `allow` em qualquer outro.

## O que fica em cada escopo

| Escopo | Arquivo (destino real) | Quem atinge | O que guarda neste projeto | Exemplo concreto (arquivo da entrega) |
|---|---|---|---|---|
| **managed** | `/etc/claude-code/managed-settings.json` (MDM/imagem) | Todas as máquinas que recebem a política; ninguém sobrescreve | Política corporativa inegociável, mais o **perfil do consultor externo** na máquina dele | [`escopos/managed-org/managed-settings.json`](../escopos/managed-org/managed-settings.json): `deny` para `Read(//**/.env)`, `Read(~/.ssh/**)`, `Bash(terraform apply *)` e `disableBypassPermissionsMode`. [`escopos/managed-consultor/managed-settings.json`](../escopos/managed-consultor/managed-settings.json): `allowManagedPermissionRulesOnly: true`, `defaultMode: dontAsk`, `deny: [Edit, Write, ...]` |
| **user** | `~/.claude/settings.json` | Uma pessoa, em todos os projetos dela | Preferências pessoais que não mudam o comportamento da squad | [`escopos/user/settings.json`](../escopos/user/settings.json): `"language": "portuguese"`, hook `Notification` com `notify-send` e `allow` de `git status`/`git log` |
| **project** | `servico-agendamento/.claude/settings.json` (**versionado**) | Todo mundo que clona o repo | Contrato da squad: allow/ask/deny, hooks de qualidade e de auditoria, bloqueio de leitura fora do diretório | [`servico-agendamento/.claude/settings.json`](../servico-agendamento/.claude/settings.json): `ask: Edit(/db/migrations/**)` e `Edit(**/migration_*)`, hook `PreToolUse` de guarda de escrita e `blockReadsOutsideWorkingDirectories: true` |
| **local** | `servico-agendamento/.claude/settings.local.json` (**no `.gitignore`**) | Uma pessoa, só neste projeto | Credenciais e ajustes pessoais deste repo | [`escopos/local/settings.local.json.exemplo`](../escopos/local/settings.local.json.exemplo): `env.AGENDAMENTO_DB_URL` com a senha pessoal do Postgres local e `allow` de `docker compose up -d db` |

Os perfis do consultor e do analista também existem como arquivos do projeto, em [`servico-agendamento/.claude/perfis/`](../servico-agendamento/.claude/perfis/). Eles servem para **demonstrar e versionar** o contrato e foram carregados nos testes com `claude --settings <perfil>`. Na operação real, o perfil do consultor é copiado para o escopo managed da máquina dele (ver risco abaixo). O do analista pode ficar como perfil `--settings`, porque o analista é interno e o pior caso dele é ler código da aplicação.

## Project × local: quem guarda o quê

| | **project** (`.claude/settings.json`) | **local** (`.claude/settings.local.json`) |
|---|---|---|
| Vai para o git? | Sim, é revisado em PR como código | Não, fica no `.gitignore` (ver [`.gitignore`](../.gitignore)) |
| Quem recebe | Todos que clonam | Só quem criou o arquivo |
| Confiança | `allow` só vale depois do diálogo *Trust this folder* | Vale sem o diálogo enquanto não estiver no git |
| **Credencial pessoal** (senha do Postgres local, token) | ❌ Nunca: vazaria no histórico do git para toda a squad | ✅ **Aqui** |
| **Regra que toda a squad precisa seguir** (ex.: migration pede confirmação) | ✅ **Aqui** | ❌ Não: seria uma regra de uma pessoa só, que some quando ela troca de máquina |

O teste real mostrou essa fronteira na prática. Antes de a pasta ser confiada, o Claude Code descartou os `allow` do project e manteve os `deny`/`ask` ([`evidencias/sessoes/ex02-0-debug-confianca.md`](evidencias/sessoes/ex02-0-debug-confianca.md)):

```
Dropped 8 project-scoped permissions.allow entries — workspace not yet trusted
Adding 4 deny rule(s) to destination 'projectSettings' ...
Adding 2 ask rule(s) to destination 'projectSettings' ...
```

Ou seja: o escopo project **restringe** sempre, mas só **concede** depois que um humano confia no repositório.

## Risco de colocar a regra do consultor no escopo errado

**Cenário de risco:** o perfil somente-leitura do consultor fica no escopo **local** (ou **user**) da máquina dele.

1. **Ele mesmo pode desfazer a regra.** O arquivo local é dele. Basta apagar o `deny: ["Edit", "Write"]`, rodar com `--permission-mode acceptEdits` ou aceitar "Yes, and don't ask again" num prompt (o Claude Code grava esse `allow` no próprio `settings.local.json`). A restrição vira uma sugestão.
2. **O `allow` do projeto soma com o dele.** As listas se combinam. Se o `deny` do consultor sumir, os `allow` do projeto (`Edit(/agendamento/**)`, `Bash(.venv/bin/pytest *)`) passam a valer para ele, e o auditor externo ganha poder de escrita da squad de dev.
3. **Ninguém percebe.** O arquivo local não entra no git, então não há PR, diff nem revisão que mostre a mudança.

O erro oposto também tem risco: colocar o perfil do consultor no **project**. Como o arquivo é versionado e aplicado a todos, `deny: ["Edit","Write"]` bloquearia **a squad de back-end inteira**. Esse é exatamente o "mudança destinada a um público afeta os outros" que a liderança quer evitar.

**Escopo correto: managed, na máquina/VM entregue ao consultor**, com [`escopos/managed-consultor/managed-settings.json`](../escopos/managed-consultor/managed-settings.json):

- `allowManagedPermissionRulesOnly: true` faz o Claude Code **ignorar** `allow`/`ask`/`deny` de user, project, local e `--settings`, além de esconder o "don't ask again". O `allow` do projeto não alcança o consultor.
- `defaultMode: "dontAsk"` faz tudo o que não estiver pré-aprovado ser negado sem perguntar.
- `disableBypassPermissionsMode` e `disableAutoMode` impedem que ele mesmo afrouxe o modo.
- `allowManagedHooksOnly: true` só deixa rodar hooks da política, nunca hooks do repositório auditado.

O comportamento do perfil foi testado de verdade (ver Ex. 2): leitura liberada; Edit, pytest e `git commit` negados.

### O que não pude demonstrar e por quê

A política managed precisa ser instalada em `/etc/claude-code/`, que exige `sudo` (o teste com `sudo -n` pediu senha). Os arquivos managed da entrega estão prontos para instalar. O **conteúdo** de permissões foi exercitado pelo perfil equivalente via `--settings` ([`evidencias/sessoes/ex02-b-consultor-deny.md`](evidencias/sessoes/ex02-b-consultor-deny.md)). As chaves que só existem no managed (`allowManagedPermissionRulesOnly`, `allowManagedHooksOnly`) seguem a documentação oficial, mas não foram executadas neste ambiente.
