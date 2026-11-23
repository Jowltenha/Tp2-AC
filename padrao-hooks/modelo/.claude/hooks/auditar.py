#!/usr/bin/env python3
"""Hook PostToolUse (Ex. 8): registra no log local cada ferramenta sensível executada.

Ferramentas sensíveis para a squad (definidas no matcher do settings.json):
Write, Edit, NotebookEdit e Bash. Para ferramentas de arquivo grava o arquivo afetado;
para Bash grava o comando. Nunca bloqueia: auditoria não deve interromper o trabalho.
"""

from __future__ import annotations

import json
import sys

from _comum import agora, caminho_alvo, carregar_politica, diretorio_projeto, ler_evento, registrar


def main() -> None:
    try:
        evento = ler_evento()
        projeto = diretorio_projeto(evento)
        entrada = evento.get("tool_input") or {}
        alvo = caminho_alvo(evento, projeto)
        registro = {
            "ts": agora(),
            "evento": "PostToolUse",
            "ferramenta": evento.get("tool_name"),
            "arquivo": str(alvo) if alvo else None,
            "comando": (entrada.get("command") or "")[:300] or None,
            "modo": evento.get("permission_mode"),
            "sessao": evento.get("session_id"),
        }
        registrar(projeto, carregar_politica(projeto)["log_auditoria"], json.dumps(registro, ensure_ascii=False))
    except Exception as erro:
        print(f"auditoria falhou: {erro!r}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
