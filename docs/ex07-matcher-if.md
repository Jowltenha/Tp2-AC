# Ex. 7: Matcher e condição `if` para restringir o hook

## Configuração final

Em [`servico-agendamento/.claude/settings.json`](../servico-agendamento/.claude/settings.json) (trecho; o `command`, o `timeout` e a `statusMessage` são iguais em todos):

```json
"PostToolUse": [
  {
    "matcher": "Edit|Write",
    "hooks": [
      { "type": "command", "if": "Edit(/agendamento/**/[a-su-z0-9_]*.py)",   "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/formatar_lint.py\"" },
      { "type": "command", "if": "Edit(/agendamento/**/t[a-df-z0-9_]*.py)",  "command": "..." },
      { "type": "command", "if": "Edit(/agendamento/**/te[a-rt-z0-9_]*.py)", "command": "..." },
      { "type": "command", "if": "Edit(/agendamento/**/tes[a-su-z0-9_]*.py)","command": "..." },
      { "type": "command", "if": "Edit(/agendamento/**/test[a-z0-9]*.py)",   "command": "..." },
      { "type": "command", "if": "Write(/agendamento/**/[a-su-z0-9_]*.py)",  "command": "..." },
      ... (as mesmas 4 classes restantes para Write)
    ]
  }
]
```

### Três camadas de filtro

| Camada | Onde | O que restringe |
|---|---|---|
| **`matcher: "Edit\|Write"`** | grupo de hooks | Só ferramentas de escrita de arquivo. `Read`, `Bash` e `Grep` nem avaliam este grupo |
| **`if: "Edit(/agendamento/**/….py)"`** | cada handler | Só arquivos `.py` **dentro da pasta da aplicação** (`/` ancora na raiz do projeto). Ficam de fora `docs`, `.md`, `.toml`, `.json`, `.sql` e `.py` de `tests/` ou de `.claude/hooks/`. É isso que resolve a lentidão da liderança: para esses arquivos **nenhum processo é iniciado** |
| **classes de caracteres no `if`** | cada handler | Exclui `test_*.py`. O nome tem que começar com algo que **não** seja o prefixo `test_` (ver abaixo) |
| guarda no script (`padroes_teste` em `politica.json`) | `formatar_lint.py` | Segunda linha de defesa: se algum `test_*.py` passar pelo `if`, o script registra `IGNORADO (arquivo de teste)` e sai sem formatar |

### Por que cinco classes, e não `!**/test_*.py`

O campo `if` aceita **uma única regra de permissão positiva**. Pela documentação: *"The `if` field holds exactly one permission rule. There is no `&&`, `||`, or list syntax"*. Testei as alternativas com debug ligado ([`evidencias/experimentos/if-negacao.md`](evidencias/experimentos/if-negacao.md)):

| Tentativa | Resultado real |
|---|---|
| `Edit(!**/test_*.py)` | **Nunca casa**, nem para `regras.py` (`Skipping hook due to if condition "Edit(!**/test_*.py)" not matching`) |
| `Edit(app/**/[!t]*.py)` | **Casou `test_regras.py`**. A classe negada não exclui |
| Classes com `A-Z` | **Casou `test_conflito_horario.py`**, porque o casamento é case-insensitive e `t` cai em `A-Z`. Ver a primeira execução em [`execucoes-anteriores/`](evidencias/execucoes-anteriores/): 4 handlers dispararam no arquivo de teste e só a guarda do script evitou a formatação |

A solução é expressar "não começa com `test_`" como **união de casos positivos**, um handler por caso, como a documentação recomenda (*"define a separate hook handler for each"*):

| Classe | Casa nomes que… |
|---|---|
| `[a-su-z0-9_]*` | começam com qualquer caractere **menos `t`** |
| `t[a-df-z0-9_]*` | começam com `t` + qualquer coisa **menos `e`** (`turnos.py`, `tela.py`) |
| `te[a-rt-z0-9_]*` | `te` + **menos `s`** (`tela`, `ter`…) |
| `tes[a-su-z0-9_]*` | `tes` + **menos `t`** (`teses.py`) |
| `test[a-z0-9]*` | `test` + **letra ou dígito**, ou seja, **sem `_`** (`testes.py`, `testing.py`) |

As cinco classes são mutuamente exclusivas, então no máximo um handler dispara por arquivo, e juntas cobrem todo nome que não começa com `test_`. A partição foi verificada com 12 nomes (`consultas`, `turnos`, `Turnos`, `teste_carga`, `testes`, `tela`, `testing`, `_interno`, `Modelo` → 1 handler; `test_x`, `TEST_x`, `test_conflito_horario` → 0).

## Demonstração: duas edições reais

### Arquivo de aplicação: o hook dispara ([`sessoes/ex07-a-hook-dispara-app.md`](evidencias/sessoes/ex07-a-hook-dispara-app.md))

O Claude foi instruído a colar código mal formatado em `agendamento/turnos.py`. O nome começa com `t` de propósito, para provar que o filtro não o confunde com teste:

```python
def   duracao_turno( nome ):
    inicio,fim=TURNOS[ nome ]
    return (fim.hour-inicio.hour)*60
```

- Eventos no `.jsonl`: **2** hooks `PostToolUse` iniciados (formatação + auditoria do Ex. 8).
- `logs/qualidade.log`: `Edit …/agendamento/turnos.py | format: 1 file reformatted | lint rc=0: All checks passed!`
- Arquivo final em disco:

```python
def duracao_turno(nome):
    inicio, fim = TURNOS[nome]
    return (fim.hour - inicio.hour) * 60
```

### Arquivo de teste: o hook não dispara ([`sessoes/ex07-b-hook-nao-dispara-teste.md`](evidencias/sessoes/ex07-b-hook-nao-dispara-teste.md))

`agendamento/test_conflito_horario.py` fica **na mesma pasta** da aplicação, ou seja, passa pelo `matcher` e pelo prefixo `/agendamento/**`. A diferença está só no nome. O arquivo tem uma tabela alinhada à mão, que o `ruff format` desmancharia. O Claude adicionou a linha `(  7,        0,     7,        29,    True ),`.

- Eventos no `.jsonl`: **1** hook `PostToolUse` iniciado (só a auditoria). **Nenhum** handler de formatação.
- `logs/qualidade.log`: **nenhuma linha nova**. O script nem foi chamado, então nem a guarda precisou agir.
- Arquivo final: o alinhamento manual foi preservado.

```python
CASOS = [
    #  medico_a  min_a  medico_b  min_b  conflita?
    (  7,        0,     7,        15,    True ),
    (  7,        0,     7,        30,    False),
    (  7,        0,     8,        0,     False),
    (  7,        0,     7,        29,    True ),
]
```

`pytest` continuou verde (`5 passed`) depois das duas edições.
