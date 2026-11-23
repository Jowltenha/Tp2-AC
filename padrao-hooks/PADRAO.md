# Padrão de runtime do Claude Code para projetos com múltiplos perfis

**Origem:** TP2, serviço de agendamento de consultas (Infnet).
**Para quem:** squads que usam Claude Code num repositório com perfis de acesso diferentes (dev, auditor externo, analista) e querem automação de qualidade sem desalinhar a configuração entre pessoas.
**Validado em:** Claude Code 2.1.281 (Linux/WSL2), em dois projetos: `servico-agendamento` e um projeto novo, `squad-faturamento`, instalado do zero.

---

## 1. Como adotar (5 minutos)

```bash
# 1. copie a pasta padrao-hooks/ para o seu repositório (ou para um repo de ferramentas da empresa)
# 2. edite SÓ o padrao.json: pasta da app, comandos permitidos, pastas restritas, formatador
python3 padrao-hooks/instalar.py <seu-projeto> padrao-hooks/padrao.json
git add <seu-projeto>/.claude && git commit -m "Adota padrão de hooks"
# 3. no CI, falhe o build se alguém editar o settings.json à mão:
python3 padrao-hooks/instalar.py --verificar <seu-projeto> padrao-hooks/padrao.json
# 4. (plataforma) instale managed/managed-settings.org.json em /etc/claude-code/managed-settings.json
#    e managed/managed-settings.consultor.json só nas máquinas de auditores externos
```

Cada pessoa da squad aceita o diálogo *Trust this folder* uma vez. Antes disso os `allow` do projeto não valem, mas os `deny`/`ask` e os hooks já valem (Ex. 2).

## 2. Arquitetura em camadas

```
 managed  (/etc/claude-code)     política da empresa + perfil do auditor externo   ← ninguém sobrescreve
   │
 project  (.claude/settings.json, GERADO)   contrato da squad: allow/ask/deny, modo, diretórios, hooks
   │        └─ .claude/hooks/politica.json (GERADO)   parâmetros lidos pelos hooks
   │        └─ .claude/hooks/*.py                     guarda, auditoria, qualidade
   │        └─ .claude/perfis/*.json                  perfis --settings (consultor, analista)
   │
 local    (.claude/settings.local.json, gitignored)   credenciais e ajustes de UMA pessoa
 user     (~/.claude/settings.json)                    preferências pessoais (idioma, notificação)

 Por chamada de ferramenta, nesta ordem:
   PreToolUse hook ──► deny rules ──► ask rules ──► allow rules ──► modo ──► EXECUTA ──► PostToolUse hooks
   (guarda_escrita)                                                                     (qualidade, auditoria)
```

**Entrada única:** `padrao.json`. **Saídas geradas:** `settings.json` e `politica.json`. **Verificação:** `instalar.py --verificar`.

## 3. Peças do padrão: o problema que cada uma resolve

| # | Peça | Onde fica | Problema real que resolve | Exercício de origem |
|---|---|---|---|---|
| P1 | **Mapa de escopos**: o que vai em managed, project, local e user | `managed/`, `.claude/settings.json`, `.gitignore` | Mudança feita para um público vazar para outro. Credencial pessoal parar no git. Regra da squad depender de cada pessoa | Ex. 1 |
| P2 | **Perfil do auditor no managed** com `allowManagedPermissionRulesOnly` | `managed/managed-settings.consultor.json` | Auditor afrouxar o próprio perfil local, ou herdar o `allow` de escrita do projeto, já que as listas se somam entre escopos | Ex. 1 |
| P3 | **`allow` só para o ciclo de dev** (pastas editáveis, testes e lint) | `settings.json` → `permissions.allow` | Fadiga de prompt no dia a dia sem abrir a porta para tudo | Ex. 2 |
| P4 | **Perfis somente-leitura** com `deny` de ferramentas de escrita + `dontAsk` | `.claude/perfis/*.json` | Auditor ou analista alterar código. Modelo achar um caminho imprevisto (`printf >>`) que o deny não listou | Ex. 2 |
| P5 | **`ask` por wildcard de nome**: `Edit(**/migration_*)` + `Edit(/db/migrations/**)` | `permissions.ask` | Migration nova, ou fora da pasta, alterada sem revisão. Lista manual que envelhece | Ex. 2, Ex. 3 |
| P6 | **Leitura e escrita com specifiers distintos**: `Read(**/*.sql)` × `Edit(...)` | `allow` × `ask` | Proteger a escrita sem bloquear a leitura legítima dos mesmos arquivos | Ex. 3 |
| P7 | **Modo por tipo de sessão**: `acceptEdits` como padrão, `dontAsk` para auditoria, `plan` para demo, `bypass` desabilitado | `defaultMode`, `disableBypassPermissionsMode`, flag `--permission-mode` | Dev júnior sem saber por que às vezes pergunta. Demo alterando código ao vivo. Alguém usando `bypass` fora de contêiner | Ex. 4 |
| P8 | **Diretório de trabalho estreito** + `blockReadsOutsideWorkingDirectories`; dados sensíveis só com `--add-dir` | estrutura de pastas + `permissions` | Infra e dados de paciente entrando no contexto de toda sessão. Exceção persistente esquecida em `additionalDirectories` | Ex. 5 |
| P9 | **Hook PostToolUse de qualidade** (`command`): formatar e checar lint do arquivo editado, devolvendo o erro com exit 2 | `formatar_lint.py` | Depender de o dev lembrar de formatar antes do commit. Lint quebrado descoberto só no CI | Ex. 6 |
| P10 | **Critério de tipo de handler**: `command` para regra local determinística, `http` para integração externa, `prompt` para julgamento semântico | documentação (seção 5) | Usar `curl` em script para auditoria central (segredo exposto) ou regex frágil para SQL destrutivo | Ex. 6 |
| P11 | **`matcher` + `if` em camadas**, com exclusão por classes de caracteres positivas geradas automaticamente | `PostToolUse[0]`, `instalar.py: classes_sem_prefixo()` | Hook lento rodando em docs e config. `test_*.py` com formatação própria desmanchado. O `if` não aceita negação | Ex. 7 |
| P12 | **Guarda PreToolUse** com `permissionDecision` deny/ask/allow, `realpath` e fail-closed | `guarda_escrita.py` + `politica.json` | Escrita em infra mesmo com `--add-dir` ou symlink. Agente editando os próprios guardrails (`.claude/`). Hook quebrado deixando tudo passar | Ex. 8 |
| P13 | **Auditoria PostToolUse** das ferramentas sensíveis, mais o registro da decisão do Pre | `auditar.py`, `logs/auditoria.jsonl` | Não saber depois o que o agente executou, o que tentou e o que foi negado | Ex. 8 |
| P14 | **Gerador e verificador**: `padrao.json` → `settings.json` e `politica.json` | `instalar.py` (+ `--verificar` no CI) | Cada dev editando o settings à mão, configurações divergentes, classes do `if` digitadas erradas | Ex. 9 |

## 4. Regras de composição (o que torna o padrão coerente)

1. **Restringir tem precedência sobre conceder, em todas as camadas.** `deny` de qualquer escopo vence `allow`. `ask` vence o modo e o `allow` de hook. `deny` de hook vence `allow` de regra. O padrão nunca depende de um `allow` para garantir segurança, só para dar conforto.
2. **Cada restrição crítica tem dois mecanismos independentes.**
   - `infra/`: fora do working dir (P8) **e** deny no hook (P12).
   - Arquivos de teste: classes no `if` (P11) **e** a guarda `padroes_teste` no script.
   - Auditor: `deny` explícito **e** `dontAsk` (P4).

   Nos testes reais, a segunda camada pegou duas falhas da primeira: a classe com `A-Z` que casou `test_*.py`, e o `printf >>` do modelo.
3. **Hooks leem parâmetros, não constantes.** Os scripts são idênticos em todas as squads, e tudo o que muda (pastas, comandos, logs) fica em `politica.json`. Atualizar os scripts não exige mexer na política de ninguém.
4. **Uma fonte, artefatos gerados.** Ninguém edita `settings.json` à mão. O `--verificar` no CI transforma "configuração inconsistente" em build vermelho.
5. **Falhar fechado no controle, aberto na observação.** A guarda nega quando quebra. A auditoria e a qualidade nunca travam o trabalho por falha própria.

## 5. Escolha do tipo de handler (P10)

| Use | Quando | Exemplo neste padrão |
|---|---|---|
| `command` | Regra determinística, local, testável sem rede | guarda de escrita, `ruff`, auditoria |
| `http` | Enviar ou consultar um serviço que já existe na empresa. Segredo via `allowedEnvVars` | Enviar alterações em `migration_*` para a trilha de auditoria central (ver `docs/ex06-eventos-handlers.md`) |
| `prompt` | Decisão que exige ler semântica de texto livre. Sempre com `if` estreito | Classificar `psql -c "..."` como destrutivo ou não |

## 6. Personalização para outra squad (testado)

O projeto `squad-faturamento` foi gerado com o mesmo `instalar.py`, alterando no `padrao.json` só a `pasta_app` (`faturamento`), as `pastas_editaveis`, os `comandos_permitidos` e os `diretorios_bloqueados_escrita` (`../infra-fat`). Numa sessão real do Claude Code, com `--add-dir ../infra-fat` ([evidência](../docs/evidencias/sessoes/ex09-reuso-outra-squad.md)):

| Ação | Resultado |
|---|---|
| Edit em `faturamento/notas.py` (`x   =   2`) | Hook de qualidade disparou: `format: 1 file reformatted`. Arquivo final `x = 2` |
| Edit em `faturamento/test_notas.py` (`x   =   2`) | Hook de qualidade **não** disparou. Arquivo mantido como escrito |
| Write em `../infra-fat/deploy.sh` | **deny** do PreToolUse. Arquivo não criado |
| Settings alterado à mão (`ask` esvaziado) | `instalar.py --verificar` → `settings.json DIVERGE do padrão`, exit 1 |

## 7. Limites conhecidos

- Regras Bash e o `if` casam o **texto** do comando. `/usr/bin/rm` ou `sh -c '...'` não casam `Bash(rm *)`. Para garantia no nível do sistema operacional, use o sandbox (`sandbox.enabled`), já previsto no perfil managed do auditor.
- `blockWritesOutsideWorkingDirectories` (v2.1.314+) pode substituir parte da guarda P12 em versões novas. A guarda continua útil para pastas **dentro** do working dir e para o caso `--add-dir`.
- As chaves exclusivas do managed (`allowManagedPermissionRulesOnly`, `allowManagedHooksOnly`) exigem instalação em `/etc/claude-code` com privilégio de administrador. No TP o conteúdo foi exercitado via `--settings`.
