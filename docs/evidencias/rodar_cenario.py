#!/usr/bin/env python3
"""Executa um cenário real do Claude Code em modo headless e grava a transcrição.

Uso:
  python3 -I rodar_cenario.py <nome> <diretorio> "<prompt>" [-- <args extras do claude>]

Grava em docs/evidencias/sessoes/:
  <nome>.jsonl  saída stream-json bruta do Claude Code (inclui eventos de hook)
  <nome>.md     transcrição legível: prompt, cada chamada de ferramenta, o resultado
                (inclusive mensagens de bloqueio), eventos de hook e a resposta final.

Nada é editado à mão: o .md é gerado a partir do .jsonl.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CLAUDE = os.environ.get(
    "CLAUDE_BIN",
    str(
        Path.home()
        / ".vscode-server/extensions/anthropic.claude-code-2.1.281-linux-x64"
        / "resources/native-binary/claude"
    ),
)
SAIDA = Path(__file__).resolve().parent / "sessoes"


def resumir(valor, limite: int = 900) -> str:
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)
    return texto if len(texto) <= limite else texto[:limite] + " …[truncado]"


def conteudo_resultado(bloco: dict) -> str:
    c = bloco.get("content")
    if isinstance(c, list):
        c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
    return str(c)


def main() -> None:
    nome, diretorio, prompt, *resto = sys.argv[1:]
    extras = resto[1:] if resto[:1] == ["--"] else resto
    SAIDA.mkdir(parents=True, exist_ok=True)
    cmd = [
        CLAUDE, "-p", prompt,
        "--output-format", "stream-json", "--verbose", "--include-hook-events",
        *extras,
    ]
    inicio = datetime.now().astimezone()
    proc = subprocess.run(cmd, cwd=diretorio, capture_output=True, text=True, timeout=600)
    (SAIDA / f"{nome}.jsonl").write_text(proc.stdout, encoding="utf-8")

    linhas = [
        f"# Sessão `{nome}`",
        "",
        f"- Data: {inicio:%Y-%m-%d %H:%M:%S %z}",
        f"- Diretório de trabalho: `{diretorio}`",
        f"- Comando: `claude -p \"…\" {' '.join(extras)}`",
        f"- Claude Code: {subprocess.run([CLAUDE, '--version'], capture_output=True, text=True).stdout.strip()}",
        f"- Log bruto: [`{nome}.jsonl`]({nome}.jsonl)",
        "",
        "## Prompt do usuário",
        "",
        *[f"> {l}" for l in prompt.splitlines()],
        "",
        "## Linha do tempo",
        "",
    ]
    final = {}
    for bruto in proc.stdout.splitlines():
        try:
            ev = json.loads(bruto)
        except json.JSONDecodeError:
            continue
        tipo, sub = ev.get("type"), ev.get("subtype")
        if tipo == "system" and sub == "init":
            linhas.append(
                f"- **init**: permissionMode=`{ev.get('permissionMode')}`, cwd=`{ev.get('cwd')}`"
            )
        elif tipo == "system" and sub and sub.startswith("hook"):
            nome_hook = ev.get("hook_name") or ev.get("hook_event") or ""
            detalhe = ev.get("output") or ev.get("stdout") or ev.get("outcome") or ""
            if sub == "hook_response" or detalhe:
                linhas.append(f"- **{sub}** `{nome_hook}` {resumir(detalhe, 400)}")
        elif tipo == "assistant":
            for bloco in ev.get("message", {}).get("content", []):
                if bloco.get("type") == "tool_use":
                    linhas.append(
                        f"- **Claude chama `{bloco['name']}`**: `{resumir(bloco.get('input'), 400)}`"
                    )
                elif bloco.get("type") == "text" and bloco.get("text", "").strip():
                    linhas.append(f"- **Claude (texto)**: {resumir(bloco['text'], 600)}")
        elif tipo == "user":
            for bloco in ev.get("message", {}).get("content", []):
                if isinstance(bloco, dict) and bloco.get("type") == "tool_result":
                    rotulo = "ERRO/BLOQUEIO" if bloco.get("is_error") else "resultado"
                    linhas.append(
                        f"  - ↳ {rotulo}: `{resumir(conteudo_resultado(bloco), 600)}`"
                    )
        elif tipo == "result":
            final = ev
    linhas += [
        "",
        "## Resposta final do Claude Code",
        "",
        final.get("result", "(sem resposta)"),
        "",
        "## Negações de permissão registradas pelo Claude Code (`permission_denials`)",
        "",
        "```json",
        json.dumps(final.get("permission_denials", []), ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    if proc.returncode != 0 and proc.stderr.strip():
        linhas += ["## stderr", "", "```", proc.stderr.strip()[-2000:], "```", ""]
    (SAIDA / f"{nome}.md").write_text("\n".join(linhas), encoding="utf-8")
    print(f"{nome}: rc={proc.returncode}, denials={len(final.get('permission_denials', []))}")


if __name__ == "__main__":
    main()
