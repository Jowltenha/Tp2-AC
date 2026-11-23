# Experimento: o campo `if` aceita negação `!`?

Projeto descartável `/tmp/exp-if`, Claude Code 2.1.281, `claude -p ... --debug-file`. Seis handlers PostToolUse no mesmo matcher `Edit|Write`; o Claude editou `app/regras.py` e depois `app/test_regras.py`.

Configuração testada:

```json
{ "type": "command", "command": "echo NOIF" },
{ "type": "command", "if": "Edit(!**/test_*.py)",   "command": "echo E-NEG" },
{ "type": "command", "if": "Edit(**/*.py)",         "command": "echo E-PY" },
{ "type": "command", "if": "Edit(app/**/[!t]*.py)", "command": "echo E-BRACKET" },
{ "type": "command", "if": "Edit(app/**/test_*.py)","command": "echo E-TEST" },
{ "type": "command", "if": "Write(app/**/[!t]*.py)","command": "echo W-BRACKET" }
```

## Log de debug ao editar `regras.py`

```
2026-11-23T11:45:57.168Z [DEBUG] Skipping hook due to if condition "Edit(!**/test_*.py)" not matching
2026-11-23T11:45:57.169Z [DEBUG] Skipping hook due to if condition "Edit(app/**/[!t]*.py)" not matching
2026-11-23T11:45:57.169Z [DEBUG] Skipping hook due to if condition "Edit(app/**/test_*.py)" not matching
2026-11-23T11:45:57.169Z [DEBUG] Skipping hook due to if condition "Write(app/**/[!t]*.py)" not matching
```

## Log de debug ao editar `test_regras.py`

```
2026-11-23T11:46:06.395Z [DEBUG] Skipping hook due to if condition "Edit(!**/test_*.py)" not matching
2026-11-23T11:46:06.395Z [DEBUG] Skipping hook due to if condition "Write(app/**/[!t]*.py)" not matching
```

## Conclusões usadas no Ex. 7

1. `Edit(!**/test_*.py)` **nunca** casa: a negação `!` não funciona no `if` (só funciona como carve-out dentro de listas `deny`/`ask`). A documentação confirma: "The `if` field holds exactly one permission rule. There is no `&&`, `||`, or list syntax".
2. `[!t]` em `app/**/[!t]*.py` também não exclui `test_regras.py`; numa segunda rodada, `[!t]` e `[^t]` casaram `test_turnos.py`. Classe negada não é confiável.
3. Na primeira execução real do Ex. 7 (guardada em `../execucoes-anteriores/ex07-*`), as classes tinham `A-Z` e o hook disparou **quatro vezes** em `test_conflito_horario.py`: o casamento de caminho é **case-insensitive**, então `t` cai em `A-Z`. A formatação só não estragou o arquivo porque a guarda no script o ignorou (`qualidade-antes-da-correcao.log`: "IGNORADO (arquivo de teste)" 4×). Por isso as classes finais usam só minúsculas, dígitos e `_`.
4. Solução adotada: cinco classes de caracteres positivas que, juntas, cobrem todo nome que **não** começa com `test_` (ver `docs/ex07-matcher-if.md`), mais a guarda no script como segunda camada.
