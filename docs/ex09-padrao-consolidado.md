# Ex. 9: Padrão de hook consolidado e reutilizável

O arquivo reutilizável é [`padrao-hooks/PADRAO.md`](../padrao-hooks/PADRAO.md). Ele acompanha:

| Arquivo | Papel |
|---|---|
| [`padrao-hooks/padrao.json`](../padrao-hooks/padrao.json) | **Única entrada** que a squad edita (pastas, comandos, wildcards, formatador, pastas restritas) |
| [`padrao-hooks/instalar.py`](../padrao-hooks/instalar.py) | Gera `.claude/settings.json` e `.claude/hooks/politica.json` e copia hooks e perfis. Com `--verificar`, detecta desvio (para CI) |
| [`padrao-hooks/modelo/.claude/hooks/`](../padrao-hooks/modelo/.claude/hooks/) | Scripts genéricos: `guarda_escrita.py` (Pre), `formatar_lint.py` e `auditar.py` (Post), `_comum.py` |
| [`padrao-hooks/modelo/.claude/perfis/`](../padrao-hooks/modelo/.claude/perfis/) | Perfis somente-leitura (consultor, analista) |
| [`padrao-hooks/modelo/managed/`](../padrao-hooks/modelo/managed/) | Políticas managed: a da organização e a da máquina do auditor |

O `PADRAO.md` tem a tabela **P1–P14**, que liga cada peça ao problema que ela resolve e ao exercício de origem, mais as regras de composição, o critério de tipo de handler e os limites conhecidos.

## Prova de que o padrão é o mesmo que foi testado nos Ex. 2–8

O `servico-agendamento` foi **reinstalado pelo gerador** depois de todos os testes:

```
$ python3 padrao-hooks/instalar.py servico-agendamento
Padrão instalado em /home/jowlt/TP2-AC/servico-agendamento/.claude
settings idêntico em conteúdo: True          ← igual, campo a campo, ao settings usado nos testes
$ python3 padrao-hooks/instalar.py --verificar servico-agendamento
settings.json ALINHADO com o padrão
```

Ou seja, as evidências dos Ex. 2 a 8 valem para o padrão gerado, e não para uma configuração montada à mão.

## Prova de reuso em outro projeto

Projeto novo `squad-faturamento`, com outra pasta de app e outra pasta restrita, gerado pelo mesmo instalador. Numa sessão real ([`evidencias/sessoes/ex09-reuso-outra-squad.md`](evidencias/sessoes/ex09-reuso-outra-squad.md)): a formatação disparou em `faturamento/notas.py` e não em `test_notas.py`, e a escrita em `../infra-fat/deploy.sh` foi negada pelo PreToolUse **mesmo com `--add-dir ../infra-fat`**. Ao editar o settings à mão (esvaziando o `ask`), o `--verificar` acusou `DIVERGE` e saiu com código 1.

## Justificativa técnica: por que o padrão reduz configurações inconsistentes

1. **Uma fonte de verdade, artefatos derivados.** O que diverge entre devs são edições manuais em JSON, que é verboso e fácil de errar. No padrão, todos editam o mesmo `padrao.json` (versionado e revisado em PR), e `settings.json`/`politica.json` são *saída* de uma função determinística. Duas máquinas com o mesmo `padrao.json` geram arquivos idênticos.
2. **Desvio detectável mecanicamente.** O `--verificar` no CI transforma "alguém mexeu no settings" em build vermelho. Sem isso, um `allow` a mais adicionado num commit qualquer fica invisível.
3. **O conhecimento difícil fica codificado, não repetido.** As cinco classes do `if` para "não é `test_*`" foram a parte mais sujeita a erro do TP: a negação não funciona e `A-Z` casou arquivos de teste por ser case-insensitive. Isso foi descoberto **testando**. No padrão, `classes_sem_prefixo()` gera as classes corretas para qualquer prefixo. Nenhum dev precisa redescobrir essa armadilha, nem consegue reintroduzi-la digitando à mão.
4. **Cada coisa no escopo certo, com precedência a favor da restrição.** As regras da squad ficam no project (versionado e igual para todos). As pessoais ficam em local/user (não contaminam os outros). As do auditor ficam no managed, onde `allowManagedPermissionRulesOnly` impede que se somem com o `allow` do projeto. Como `deny` de qualquer escopo vence `allow` e as listas se somam, uma preferência local **nunca** consegue remover uma restrição da squad. No máximo adiciona outra.
5. **Comportamento que não depende do modo nem da memória de cada pessoa.** As restrições críticas (migrations em `ask`, infra em `deny` no hook, dados fora do working dir) valem em `default`, `acceptEdits`, `auto` e até com `--add-dir`. Isso foi testado. O modo de cada dev muda só o conforto, não a segurança. Dois devs com hábitos diferentes produzem o mesmo resultado nas áreas que importam.
6. **Hooks iguais, política parametrizada.** Os scripts são os mesmos para todas as squads, e só `politica.json` muda. Uma correção (como o caso do `~/.claude/plans`, descoberto no Ex. 4) se propaga reinstalando, sem patches divergentes por squad.
7. **Defesa em profundidade com evidência.** Cada restrição crítica tem dois mecanismos independentes. Nos testes, a segunda camada absorveu duas falhas reais da primeira. Num time grande, alguém sempre vai errar uma regra, e o padrão garante que um erro isolado não vira incidente.
