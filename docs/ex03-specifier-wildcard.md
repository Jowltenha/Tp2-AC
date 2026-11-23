# Ex. 3: Specifier e wildcard para `.sql` × `migration_*`

## Regras

```json
"allow": [ "Read(**/*.sql)" ],
"ask":   [ "Edit(/db/migrations/**)", "Edit(**/migration_*)" ]
```

| Regra | Especificador | O que significa |
|---|---|---|
| `Read(**/*.sql)` | `Read` + glob gitignore | Leitura livre de qualquer `.sql`, em qualquer profundidade do projeto |
| `Edit(**/migration_*)` | `Edit` + glob | Qualquer **alteração** (Edit, Write, NotebookEdit) em arquivo cujo **nome** começa com `migration_`, **em qualquer pasta** |
| `Edit(/db/migrations/**)` | `Edit` + caminho ancorado | Mantida do Ex. 2: qualquer arquivo na pasta de migrações, mesmo que não siga o prefixo |

Detalhes de sintaxe que pesaram na escolha (documentação oficial, *Permissions › Read and Edit*):

- Caminhos usam **sintaxe gitignore**: `*` casa dentro de um segmento e `**` atravessa diretórios.
- `/caminho` ancora no diretório do arquivo de settings (raiz do projeto). `caminho` sem barra é relativo ao diretório atual. `//caminho` é absoluto.
- O `**/` na frente de `migration_*` torna a regra **independente de pasta**, que é o requisito "independentemente da pasta em que estiver".
- O especificador separa leitura de escrita: a mesma árvore de arquivos tem `Read(...)` em `allow` e `Edit(...)` em `ask`. Não existe regra `Write(path)` efetiva. `Edit` é o especificador que cobre todas as ferramentas de escrita.
- Ordem de avaliação: **deny → ask → allow**. Por isso o `Read(**/*.sql)` em `allow` não "vaza" para escrita: escrita é `Edit`, outro especificador, e cai no `ask`.

## Demonstração com caminhos reais do projeto

Sessão headless com a pasta já confiada: [`evidencias/sessoes/ex03-sql-leitura-e-migration-escrita.md`](evidencias/sessoes/ex03-sql-leitura-e-migration-escrita.md). Em `-p` não há quem responda ao prompt, então um `ask` aparece como *"requested permissions … but you haven't granted it yet"*. A versão interativa do mesmo `ask`, com a tela de confirmação, está no Ex. 2.

| # | Caminho real | Ação | Regra que casou | Resultado observado |
|---|---|---|---|---|
| 1 | `db/migrations/migration_001_criar_consultas.sql` | Read | `Read(**/*.sql)` | ✅ Lido sem perguntar |
| 2 | `relatorios/sql/migration_003_view_ocupacao.sql` | Read | `Read(**/*.sql)` | ✅ Lido sem perguntar, **apesar** de ser `migration_` (leitura legítima não é bloqueada) |
| 3 | `db/consultas/ocupacao_por_medico.sql` | Read | `Read(**/*.sql)` | ✅ Lido sem perguntar |
| 4 | `db/consultas/ocupacao_por_medico.sql` | Edit (**controle**) | nenhuma ask (`.sql`, mas não `migration_`) | ✅ Editado (o `acceptEdits` aprovou). Prova que a regra **não** pega todo `.sql`. O arquivo foi restaurado depois do teste |
| 5 | `relatorios/sql/migration_003_view_ocupacao.sql` | Edit | `Edit(**/migration_*)`. **Fora** de `db/migrations/` | ⏸ Pediu confirmação: `Claude requested permissions to write to …/relatorios/sql/migration_003_view_ocupacao.sql, but you haven't granted it yet.` |
| 6 | `db/migrations/migration_002_indice_medico_data.sql` | Edit | `Edit(**/migration_*)` e `Edit(/db/migrations/**)` | ⏸ Pediu confirmação (mesma mensagem) |

O caso 5 é o que justifica o wildcard: a migration `003` mora em `relatorios/sql/`, fora da pasta de migrações. Só a regra do Ex. 2 (`/db/migrations/**`) a deixaria passar direto pelo `acceptEdits`.

Nos casos 5 e 6, o hook PreToolUse devolveu `allow` (ver o `.md` da sessão), e mesmo assim o `ask` prevaleceu.

## Por que wildcard é mais seguro do que listar cada arquivo

1. **Falha para o lado seguro diante do futuro.** A lista manual (`Edit(/db/migrations/migration_001_criar_consultas.sql)`, `Edit(/db/migrations/migration_002_...)`) protege só o que existe hoje. A `migration_004` criada amanhã nasce **sem proteção**, e no modo `acceptEdits` seria alterada sem pergunta. Com `**/migration_*`, todo arquivo novo que siga a convenção nasce protegido, sem ninguém precisar lembrar de atualizar o settings.
2. **Independe de onde o arquivo mora.** O caso real `relatorios/sql/migration_003_view_ocupacao.sql` mostra que migrations escapam da pasta convencional. Com lista manual ou regra só de pasta, esse arquivo fica de fora. O `**/` pega o nome em qualquer profundidade.
3. **Expressa a política, não o inventário.** A regra lê como a decisão da liderança ("arquivo `migration_*` só muda com confirmação"). Uma lista de 30 caminhos esconde a intenção e é difícil de revisar em PR: ninguém percebe que faltou um item.
4. **Sem conflito com renomeações.** Mover ou renomear um arquivo listado à mão quebra a proteção em silêncio. O padrão continua casando.
5. **Custo do falso positivo é baixo.** Se algum arquivo não-migration começar com `migration_`, o pior caso é um prompt a mais (é `ask`, não `deny`). O falso negativo da lista manual é uma migration de produção alterada sem revisão. Entre os dois erros possíveis, o wildcard escolhe o barato.
