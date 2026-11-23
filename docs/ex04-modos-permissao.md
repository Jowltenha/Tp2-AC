# Ex. 4: Modos de permissão: avaliação e recomendação

## Por que às vezes o Claude pergunta e às vezes age direto (resposta ao dev júnior)

Para cada ferramenta que o Claude quer usar, o Claude Code decide em camadas, nesta ordem:

1. **Regras `deny`** (de qualquer escopo): se casar, bloqueia. Nenhum modo passa por cima.
2. **Regras `ask`**: se casar, **sempre pergunta**, em qualquer modo, inclusive `acceptEdits` e `bypassPermissions`. É o que acontece com as migrations (Ex. 2 e 3).
3. **Hook `PreToolUse`**: pode devolver `deny` (bloqueia), `ask` (força pergunta) ou `allow` (pula o prompt), mas não derruba um `deny`/`ask` das regras (Ex. 8).
4. **Regras `allow`**: se casar, executa sem perguntar (ex.: `.venv/bin/pytest`).
5. **Modo de permissão**: só decide o que **sobrou**, ou seja, as ações que nenhuma regra cobriu.

Por isso o mesmo Claude, no mesmo modo, edita `agendamento/consultas.py` direto (allow) e para na migration (ask). O modo é o comportamento de fundo, e as regras ficam por cima dele.

## Os modos disponíveis (Claude Code 2.1.281)

| Modo | Leituras no diretório de trabalho | Edição de arquivos | Bash não pré-aprovado | Quando algo precisaria de confirmação | Observações |
|---|---|---|---|---|---|
| `default` (Manual) | Livre | **Pergunta** | **Pergunta** | Pergunta | Comportamento padrão. Rótulo *Manual* na CLI e no VS Code |
| `acceptEdits` | Livre | **Aceita** edições e `mkdir`/`touch`/`mv`/`cp` dentro do diretório de trabalho | Pergunta | Pergunta | Barra de status: `⏵⏵ accept edits on`. `ask` continua perguntando |
| `plan` | Livre (mais comandos só-leitura) | **Não edita** os arquivos-fonte. Escreve só o próprio plano em `~/.claude/plans/` | Pergunta | Ao final apresenta o plano e só sai do modo com aprovação humana (`ExitPlanMode`) | Um `allow` de hook não aprova edição em `plan` |
| `auto` | Livre | Aceita | Um **classificador** em segundo plano aprova ou bloqueia | O classificador decide no lugar do humano | Exige modelo suportado. Pode ser desligado por `disableAutoMode` |
| `dontAsk` | Livre | **Nega** (a menos que haja `allow`) | **Nega** (a menos que haja `allow`) | **Nega sem perguntar**. `ask` vira negação | Para CI e perfis travados. Usado no consultor (Ex. 2) |
| `bypassPermissions` | Livre | Aceita | Aceita | Não pergunta (exceto `ask` explícito, remoções críticas e `AskUserQuestion`) | Só em contêiner ou VM isolada. **Desabilitado** neste projeto com `disableBypassPermissionsMode` |

Ações que **nenhum modo aprova sozinho**: regra `ask` explícita, remoções críticas (`rm -rf /`, `rm -rf ~`), `AskUserQuestion` e leituras fora do diretório quando `blockReadsOutsideWorkingDirectories` está ligado.

## Recomendação por cenário

| Cenário | Modo recomendado | Justificativa técnica |
|---|---|---|
| **Desenvolvimento do dia a dia** | `acceptEdits` (é o `defaultMode` do [`settings.json`](../servico-agendamento/.claude/settings.json) do projeto) | O ciclo editar → testar → corrigir fica sem atrito, porque edições na árvore de trabalho e os comandos do `allow` (`pytest`, `ruff`) rodam direto. A segurança não depende do modo: as migrations continuam no `ask` (testado no Ex. 2: o prompt apareceu com `accept edits on`), `infra/` é bloqueada pelo hook (Ex. 8) e tudo é auditado. O `default` geraria fadiga de prompt e o dev passaria a aprovar sem ler. O `auto` foi descartado porque troca a decisão humana por um classificador justamente nas ações não previstas, e a squad ainda está construindo o histórico de regras. O `bypassPermissions` está desabilitado |
| **Revisão de segurança** (consultor externo) | `dontAsk` + perfil somente-leitura (no escopo managed, ver Ex. 1) | O auditor precisa ler tudo e não pode alterar nada. No `default` ele receberia prompts e poderia aprovar uma escrita. No `plan` a edição fica bloqueada, mas o plano pode ser aprovado e o modo trocado com Shift+Tab. Em `dontAsk`, **o que não está no `allow` de leitura é negado sem pergunta**, inclusive caminhos imprevistos (o teste real mostrou o modelo tentando `printf >> arquivo` e sendo negado). Com `disableBypassPermissionsMode` e `disableAutoMode` no managed, ele não consegue afrouxar |
| **Demonstração para a diretoria** | `plan` | Na frente de uma plateia, o risco é o agente alterar código ao vivo (ou fazer algo destrutivo) a partir de um pedido improvisado de alguém da sala. O `plan` mostra a capacidade real (ler o código, entender, propor uma mudança concreta e testável) e **garante que nada é escrito**. O momento de aprovar o plano vira parte da demo: mostra que há um humano no controle. O `dontAsk` também não escreve, mas falha em silêncio e só mostra negações, o que é ruim para demo. O `default` encheria a tela de prompts |

## Prática: demonstração para a diretoria em `plan`

Sessão **interativa** real, iniciada com `claude --permission-mode plan` em `servico-agendamento/`:

- Tela capturada: [`evidencias/telas/ex04-demo-diretoria-plan.md`](evidencias/telas/ex04-demo-diretoria-plan.md)
- Transcrição completa (gerada do `.jsonl` do Claude Code): [`evidencias/sessoes/ex04-demo-diretoria-interativa.md`](evidencias/sessoes/ex04-demo-diretoria-interativa.md)
- Rodada headless equivalente: [`evidencias/sessoes/ex04-demo-diretoria-plan.md`](evidencias/sessoes/ex04-demo-diretoria-plan.md)

Pedido feito (de propósito, pedindo para **aplicar** a mudança): *"em até 5 linhas explique o que o serviço faz (leia agendamento/) e, em seguida, adicione em agendamento/consultas.py um limite de 3 consultas por paciente por dia."*

Comportamento observado:

1. **Leu livremente** os módulos, os testes e a configuração (`find`, `cat`, `Read`). Dois comandos `cat` compostos pediram confirmação porque o parser não conseguiu provar que só liam dentro do diretório (`blockReadsOutsideWorkingDirectories`, do Ex. 5). Aprovei os dois, porque eram só leitura.
2. **Não editou `consultas.py`.** A única escrita foi o arquivo de plano em `~/.claude/plans/…` (o hook do Ex. 8 libera explicitamente esse caminho).
3. Apresentou o plano e parou:

```
 Claude has written up a plan and is ready to execute. Would you like to proceed?
 ❯ 1. Yes, and use auto mode
   2. Yes, manually approve edits
   3. Tell Claude what to change
```

4. Rejeitei com Esc, encerrando a demo sem aplicar nada. A transcrição registra `ExitPlanMode → The user doesn't want to proceed with this tool use`.
5. **Verificação independente:** `md5sum -c` em `agendamento/consultas.py` antes e depois da demo → `OK` (arquivo idêntico).

Na rodada headless equivalente, o próprio Claude explicou: *"Estou em modo de planejamento, então ainda não alterei o código."*
