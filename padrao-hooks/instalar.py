#!/usr/bin/env python3
"""Instala o padrão de hooks/permissões do TP2 num projeto.

Uso:
  python3 instalar.py <diretorio-do-projeto> [padrao.json]   # instala/atualiza
  python3 instalar.py --verificar <diretorio-do-projeto> [padrao.json]

Gera, a partir de UM arquivo de entrada (padrao.json):
  <projeto>/.claude/settings.json        (escopo project: permissões + hooks)
  <projeto>/.claude/hooks/politica.json  (parâmetros lidos pelos hooks em runtime)
  <projeto>/.claude/hooks/*.py           (scripts copiados do modelo)
  <projeto>/.claude/perfis/*.json        (perfis consultor/analista)

--verificar compara o settings.json do projeto com o que o padrão geraria e sai com 1
se houver divergência (uso em CI: impede que alguém edite o settings à mão e desalinhe).
"""

from __future__ import annotations

import json
import shutil
import string
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
MODELO = AQUI / "modelo" / ".claude"
ALFABETO = string.ascii_lowercase + string.digits + "_"


def classe(excluir: str) -> str:
    """Classe [..] com letras minúsculas, dígitos e _, menos o caractere `excluir`.

    O casamento de caminho do Claude Code é case-insensitive, por isso não usamos A-Z.
    """
    resto = [c for c in ALFABETO if c != excluir]
    # comprime em faixas (a-s, u-z, 0-9) para legibilidade
    faixas, i = [], 0
    while i < len(resto):
        j = i
        while j + 1 < len(resto) and ord(resto[j + 1]) == ord(resto[j]) + 1:
            j += 1
        faixas.append(resto[i] if i == j else f"{resto[i]}-{resto[j]}")
        i = j + 1
    return "[" + "".join(faixas) + "]"


def classes_sem_prefixo(prefixo: str) -> list[str]:
    """Padrões glob positivos cuja união = 'nome NÃO começa com prefixo'.

    O campo `if` de um hook aceita uma única regra positiva, sem negação; então
    'não começa com test_' vira len(prefixo) handlers mutuamente exclusivos.
    """
    padroes = []
    for k, ch in enumerate(prefixo):
        padroes.append(prefixo[:k] + classe(ch))
    return padroes


def gerar_settings(p: dict) -> dict:
    app = p["pasta_app"].strip("/")
    cmd_fmt = 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/formatar_lint.py"'
    handlers_qualidade = [
        {
            "type": "command",
            "if": f"{ferr}(/{app}/**/{c}*.{p['extensao']})",
            "command": cmd_fmt,
            "timeout": 60,
            "statusMessage": " + ".join([" ".join(p["formatador"]), " ".join(p["linter"])]),
        }
        for ferr in ("Edit", "Write")
        for c in classes_sem_prefixo(p["prefixo_teste"])
    ]
    return {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "permissions": {
            "defaultMode": p["modo_padrao"],
            "disableBypassPermissionsMode": "disable",
            "blockReadsOutsideWorkingDirectories": True,
            "allow": [f"Edit(/{d.strip('/')}/**)" for d in p["pastas_editaveis"]]
            + [f"Read({g})" for g in p["leitura_livre"]]
            + [f"Bash({c})" for c in p["comandos_permitidos"]],
            "ask": [f"Edit({g})" for g in p["confirmar_escrita"]],
            "deny": list(p["negar"]),
        },
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit|NotebookEdit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/guarda_escrita.py"',
                            "timeout": 15,
                            "statusMessage": "Checando política de escrita da squad",
                        }
                    ],
                }
            ],
            "PostToolUse": [
                {"matcher": "Edit|Write", "hooks": handlers_qualidade},
                {
                    "matcher": "|".join(p["ferramentas_auditadas"]),
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/auditar.py"',
                            "timeout": 15,
                        }
                    ],
                },
            ],
        },
    }


def gerar_politica(p: dict) -> dict:
    chaves = [
        "diretorios_bloqueados_escrita", "diretorios_confirmacao", "liberados_fora_do_projeto",
        "padroes_teste", "formatador", "linter", "log_auditoria", "log_qualidade",
    ]
    return {"_comentario": "Gerado por padrao-hooks/instalar.py a partir de padrao.json. Não edite à mão."} | {
        k: p[k] for k in chaves
    }


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    args = sys.argv[1:]
    verificar = args[:1] == ["--verificar"]
    if verificar:
        args = args[1:]
    if not args:
        sys.exit(__doc__)
    projeto = Path(args[0]).resolve()
    padrao = json.loads(Path(args[1] if len(args) > 1 else AQUI / "padrao.json").read_text(encoding="utf-8"))
    settings, politica = dump(gerar_settings(padrao)), dump(gerar_politica(padrao))

    if verificar:
        atual = (projeto / ".claude" / "settings.json")
        ok = atual.exists() and json.loads(atual.read_text(encoding="utf-8")) == json.loads(settings)
        print("settings.json ALINHADO com o padrão" if ok else "settings.json DIVERGE do padrão")
        sys.exit(0 if ok else 1)

    destino = projeto / ".claude"
    (destino / "hooks").mkdir(parents=True, exist_ok=True)
    (destino / "perfis").mkdir(parents=True, exist_ok=True)
    for script in (MODELO / "hooks").glob("*.py"):
        shutil.copy2(script, destino / "hooks" / script.name)
    for perfil in (MODELO / "perfis").glob("*.json"):
        shutil.copy2(perfil, destino / "perfis" / perfil.name)
    (destino / "settings.json").write_text(settings, encoding="utf-8")
    (destino / "hooks" / "politica.json").write_text(politica, encoding="utf-8")
    gi = projeto / ".gitignore"
    linhas = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    for item in (".claude/settings.local.json", padrao["log_auditoria"].split("/")[0] + "/"):
        if item not in linhas:
            linhas.append(item)
    gi.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"Padrão instalado em {destino}")


if __name__ == "__main__":
    main()
