#!/usr/bin/env python3
"""Hook PostToolUse (Ex. 6 e 7): formata e checa lint do arquivo Python recém-editado.

Filtros em camadas:
  1. matcher "Edit|Write" (settings.json)      -> só ferramentas de escrita;
  2. campo "if" Edit(/agendamento/**/*.py)     -> só .py do pacote da aplicação;
  3. guarda abaixo (padroes_teste)             -> nunca formata test_*.py, onde quer que esteja,
     porque o campo "if" aceita uma única regra positiva e não tem negação.

Se o lint falhar, sai com código 2: o stderr volta para o Claude, que corrige na hora.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from fnmatch import fnmatch

from _comum import agora, caminho_alvo, carregar_politica, diretorio_projeto, ler_evento, registrar


def resolver_comando(projeto, comando: list[str]) -> list[str]:
    exe = comando[0]
    local = projeto / ".venv" / "bin" / exe
    if local.exists():
        return [str(local), *comando[1:]]
    return [shutil.which(exe) or exe, *comando[1:]]


def main() -> None:
    evento = ler_evento()
    projeto = diretorio_projeto(evento)
    politica = carregar_politica(projeto)
    alvo = caminho_alvo(evento, projeto)
    log = politica["log_qualidade"]
    if alvo is None or alvo.suffix != ".py":
        sys.exit(0)
    if any(fnmatch(alvo.name, padrao) for padrao in politica["padroes_teste"]):
        registrar(projeto, log, f"{agora()} IGNORADO (arquivo de teste) {alvo}")
        sys.exit(0)

    fmt = subprocess.run(
        [*resolver_comando(projeto, politica["formatador"]), str(alvo)],
        capture_output=True, text=True, cwd=projeto,
    )
    lint = subprocess.run(
        [*resolver_comando(projeto, politica["linter"]), str(alvo)],
        capture_output=True, text=True, cwd=projeto,
    )
    registrar(
        projeto,
        log,
        f"{agora()} {evento.get('tool_name')} {alvo} | format: {fmt.stdout.strip() or fmt.stderr.strip()}"
        f" | lint rc={lint.returncode}: {lint.stdout.strip().splitlines()[-1] if lint.stdout.strip() else 'ok'}",
    )
    if lint.returncode != 0:
        print(f"ruff check encontrou problemas em {alvo.name}:\n{lint.stdout}", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
