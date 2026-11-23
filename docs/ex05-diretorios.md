# Ex. 5: Diretórios de trabalho e acesso a arquivos sensíveis

## Layout do repositório

```
TP2-AC/                         ← raiz do git
├── servico-agendamento/        ← ÚNICO diretório de trabalho da squad de aplicação
│   └── .claude/settings.json
├── infra/                      ← scripts de infraestrutura (squad de plataforma)
│   ├── deploy_producao.sh
│   └── terraform/main.tf
└── dados-teste/                ← dados SINTÉTICOS de pacientes (nome, CPF, telefone)
    └── pacientes_sinteticos.csv
```

A decisão estrutural é **tirar `infra/` e `dados-teste/` de dentro do diretório de trabalho**. Por padrão, o Claude Code só lê livremente o diretório onde foi iniciado (e os `additionalDirectories`). Ao iniciar em `servico-agendamento/`, as duas pastas ficam fora do alcance padrão.

## Configuração

Em [`servico-agendamento/.claude/settings.json`](../servico-agendamento/.claude/settings.json):

```json
"permissions": {
  "blockReadsOutsideWorkingDirectories": true
  // sem "additionalDirectories": nenhuma pasta extra é incluída por padrão
}
```

e, no hook do Ex. 8 ([`politica.json`](../servico-agendamento/.claude/hooks/politica.json)):

```json
"diretorios_bloqueados_escrita": ["../infra", "../dados-teste"]
```

| Restrição | Mecanismo | Efeito |
|---|---|---|
| `infra/` fora do alcance de leitura | diretório fora do working dir + `blockReadsOutsideWorkingDirectories` | `Read`/`Grep`/`Glob` são **recusados** em qualquer modo, inclusive `bypassPermissions`. Comandos Bash que leem fora do diretório também são barrados |
| `infra/` fora do alcance de escrita | hook PreToolUse (Ex. 8) | `deny` em qualquer escrita, **mesmo se alguém fizer `--add-dir ../infra`** ou criar um symlink para lá (o hook resolve `realpath`) |
| `dados-teste/` só sob pedido explícito | fora do working dir + `blockReadsOutsideWorkingDirectories`; liberação **por sessão** com `--add-dir ../dados-teste` ou `/add-dir` | Nunca entra no contexto de uma sessão comum. Quem precisa (ex.: geração de massa de teste) pede explicitamente ao iniciar a sessão, e a liberação morre com ela |
| `dados-teste/` nunca é alterado pelo agente | hook PreToolUse | `deny` na escrita mesmo com `--add-dir` |

**Por que não usei `additionalDirectories` para `dados-teste/`:** a chave persiste no settings, e a pasta passaria a fazer parte de **toda** sessão, que é exatamente o que o enunciado proíbe. O `--add-dir` é efêmero e explícito: fica registrado na linha de comando de quem pediu.

**Por que não só `Read(../infra/**)` em deny:** funcionaria para a ferramenta `Read`, mas um deny por caminho só cobre o que se previu. O bloqueio por *working directory* inverte a lógica: tudo que está fora é negado, inclusive pastas novas criadas amanhã ao lado de `infra/`.

## Testes reais

### 1. Tentativa bloqueada ([`sessoes/ex05-a-dados-pacientes-bloqueado.md`](evidencias/sessoes/ex05-a-dados-pacientes-bloqueado.md))

Sessão comum (`claude -p` em `servico-agendamento/`, sem `--add-dir`). Pedido: ler o CSV de pacientes e depois `../infra/terraform/main.tf`.

```
Claude chama Bash: wc -l /home/jowlt/TP2-AC/dados-teste/pacientes_sinteticos.csv; head -3 ...
  ↳ ERRO/BLOQUEIO: Reads outside the working directories are blocked
    (permissions.blockReadsOutsideWorkingDirectories). Add the directory with /add-dir, or remove that setting.
Claude chama Read: /home/jowlt/TP2-AC/infra/terraform/main.tf
  ↳ ERRO/BLOQUEIO: ... is outside /home/jowlt/TP2-AC/servico-agendamento; the
    permissions.blockReadsOutsideWorkingDirectories setting blocks reads outside the working directories.
```

Resposta final: *"Não consegui ler nenhum dos dois arquivos, então não sei quantos pacientes tem o CSV."* Nenhum dado de paciente entrou no contexto.

### 2. Tentativa explicitamente autorizada ([`sessoes/ex05-b-dados-pacientes-autorizado.md`](evidencias/sessoes/ex05-b-dados-pacientes-autorizado.md))

Mesma pasta, mesma configuração, mas a sessão foi iniciada com **`--add-dir ../dados-teste`**:

```
Claude chama Bash: wc -l .../dados-teste/pacientes_sinteticos.csv; head -5 ...
  ↳ resultado: 4 /home/jowlt/TP2-AC/dados-teste/pacientes_sinteticos.csv ...
Claude chama Read: /home/jowlt/TP2-AC/infra/terraform/main.tf
  ↳ ERRO/BLOQUEIO: ... is outside /home/jowlt/TP2-AC/servico-agendamento, /home/jowlt/TP2-AC/dados-teste; ...
```

Resposta: *"3 pacientes … Convênios: Plano Ouro, Particular e Plano Prata"*. A liberação foi **só** da pasta pedida: `infra/` continuou bloqueada na mesma sessão, e a própria mensagem de erro lista os dois diretórios de trabalho ativos.

### 3. Escrita em `infra/` mesmo com o diretório adicionado

Ver Ex. 8: com `--add-dir ../infra`, a **leitura** passou, mas o `Edit` em `infra/deploy_producao.sh` foi negado pelo hook PreToolUse (`permissionDecision: "deny"`), e o arquivo ficou byte a byte idêntico (`diff` vazio).

## Limites conhecidos (documentados, não escondidos)

- `blockReadsOutsideWorkingDirectories` atua sobre as ferramentas de arquivo e sobre os comandos Bash que o Claude Code consegue analisar. Um script Python que abre arquivos por conta própria não é coberto. Para garantia no nível do sistema operacional, a documentação recomenda o **sandbox** (`sandbox.enabled`), previsto no perfil managed do consultor.
- `blockWritesOutsideWorkingDirectories` só existe a partir da v2.1.314. Esta máquina roda a 2.1.281, por isso a escrita é controlada pelo hook do Ex. 8, que além de tudo funciona em qualquer versão com hooks.
