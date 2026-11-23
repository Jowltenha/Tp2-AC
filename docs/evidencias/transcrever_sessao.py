#!/usr/bin/env python3
"""Gera transcrição legível (.md) de uma sessão INTERATIVA a partir do .jsonl que o
Claude Code grava em ~/.claude/projects/<projeto>/<session_id>.jsonl.

Uso: python3 -I transcrever_sessao.py <sessao.jsonl> <saida.md> "<título>"
"""

from __future__ import annotations

import json
import sys


def resumir(valor, limite: int = 700) -> str:
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)
    texto = texto.replace("\n", " ⏎ ")
    return texto if len(texto) <= limite else texto[:limite] + " …[truncado]"


def main() -> None:
    origem, destino, titulo = sys.argv[1:4]
    linhas = [f"# {titulo}", "", f"Fonte: [`{origem.split('/')[-1]}`]({origem.split('/')[-1]}) (gravado pelo Claude Code).", ""]
    modos: list[str] = []
    for bruto in open(origem, encoding="utf-8"):
        try:
            ev = json.loads(bruto)
        except json.JSONDecodeError:
            continue
        modo = ev.get("permissionMode")
        if modo and (not modos or modos[-1] != modo):
            modos.append(modo)
            linhas.append(f"- **modo de permissão**: `{modo}`")
        msg = ev.get("message") or {}
        conteudo = msg.get("content")
        if ev.get("type") == "user":
            if isinstance(conteudo, str) and not conteudo.startswith("<"):
                linhas.append(f"- **Usuário**: {resumir(conteudo, 1200)}")
            elif isinstance(conteudo, list):
                for b in conteudo:
                    if b.get("type") == "tool_result":
                        c = b.get("content")
                        if isinstance(c, list):
                            c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                        rot = "ERRO/BLOQUEIO" if b.get("is_error") else "resultado"
                        linhas.append(f"  - ↳ {rot}: `{resumir(c, 500)}`")
                    elif b.get("type") == "text" and not b.get("text", "").startswith("<"):
                        linhas.append(f"- **Usuário**: {resumir(b['text'], 1200)}")
        elif ev.get("type") == "assistant" and isinstance(conteudo, list):
            for b in conteudo:
                if b.get("type") == "tool_use":
                    linhas.append(f"- **Claude chama `{b['name']}`**: `{resumir(b.get('input'), 400)}`")
                elif b.get("type") == "text" and b.get("text", "").strip():
                    linhas.append(f"- **Claude**: {resumir(b['text'], 1500)}")
        elif ev.get("type") == "system" and ev.get("content"):
            linhas.append(f"- *sistema*: {resumir(ev['content'], 300)}")
    open(destino, "w", encoding="utf-8").write("\n".join(linhas) + "\n")
    print(destino, len(linhas), "linhas; modos:", modos)


if __name__ == "__main__":
    main()
