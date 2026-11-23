#!/usr/bin/env python3
"""Hook PreToolUse (Ex. 8): checagem automática antes de toda ferramenta de escrita.

Decisão devolvida em hookSpecificOutput.permissionDecision:
  deny  -> alvo dentro de um diretório bloqueado (infra/, dados-teste/), mesmo via symlink;
  ask   -> alvo em .claude/ (o agente não altera os próprios guardrails sem um humano)
           ou fora do projeto (o hook não aprova escrita fora do diretório de trabalho);
  allow -> demais casos. Regras ask/deny do settings.json continuam valendo por cima do allow
           (ex.: migrations seguem pedindo confirmação).

Fail-closed: se o próprio hook falhar, a escrita é negada em vez de seguir sem checagem.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from _comum import (
    agora,
    caminho_alvo,
    carregar_politica,
    dentro_de,
    diretorio_projeto,
    ler_evento,
    registrar,
)


def decidir(evento: dict) -> tuple[str, str, str]:
    projeto = diretorio_projeto(evento)
    politica = carregar_politica(projeto)
    alvo = caminho_alvo(evento, projeto)
    if alvo is None:
        return "deny", "Checagem de escrita: a ferramenta não informou o arquivo alvo.", "?"
    for relativo in politica["diretorios_bloqueados_escrita"]:
        bloqueado = (projeto / relativo).resolve()
        if dentro_de(alvo, bloqueado):
            return (
                "deny",
                f"Bloqueado pela política da squad: '{alvo}' está em '{bloqueado.name}/', "
                "pasta restrita (responsabilidade de outra squad ou dados sensíveis).",
                str(alvo),
            )
    for relativo in politica.get("diretorios_confirmacao", []):
        sensivel = (projeto / relativo).resolve()
        if dentro_de(alvo, sensivel):
            return (
                "ask",
                f"'{alvo}' altera a própria configuração do Claude Code ({relativo}/); "
                "exige confirmação humana.",
                str(alvo),
            )
    for liberado in politica.get("liberados_fora_do_projeto", []):
        if dentro_de(alvo, Path(os.path.realpath(os.path.expanduser(liberado)))):
            return "allow", f"Arquivo interno do Claude Code ({liberado}).", str(alvo)
    if not dentro_de(alvo, projeto):
        return "ask", f"'{alvo}' está fora do projeto; confirme manualmente.", str(alvo)
    return "allow", "Checagem de escrita OK: alvo dentro do projeto e fora de pastas restritas.", str(alvo)


def main() -> None:
    evento: dict = {}
    try:
        evento = ler_evento()
        decisao, motivo, alvo = decidir(evento)
    except Exception as erro:  # fail-closed
        decisao, motivo, alvo = "deny", f"Falha na checagem de escrita ({erro!r}); bloqueado por segurança.", "?"
    try:
        projeto = diretorio_projeto(evento)
        registro = {
            "ts": agora(),
            "evento": "PreToolUse",
            "ferramenta": evento.get("tool_name"),
            "arquivo": alvo,
            "decisao": decisao,
            "modo": evento.get("permission_mode"),
            "sessao": evento.get("session_id"),
        }
        registrar(projeto, carregar_politica(projeto)["log_auditoria"], json.dumps(registro, ensure_ascii=False))
    except Exception:
        pass
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decisao,
                    "permissionDecisionReason": motivo,
                }
            },
            ensure_ascii=False,
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
