"""Funções compartilhadas pelos hooks do projeto (leitura do evento, política e logs)."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

POLITICA_PADRAO = {
    "diretorios_bloqueados_escrita": [],
    "diretorios_confirmacao": [".claude"],
    "padroes_teste": ["test_*.py"],
    "formatador": ["ruff", "format"],
    "linter": ["ruff", "check"],
    "log_auditoria": "logs/auditoria.jsonl",
    "log_qualidade": "logs/qualidade.log",
}


def ler_evento() -> dict:
    """Lê o JSON que o Claude Code envia ao hook pela entrada padrão."""
    return json.load(sys.stdin)


def diretorio_projeto(evento: dict) -> Path:
    raiz = os.environ.get("CLAUDE_PROJECT_DIR") or evento.get("cwd") or "."
    return Path(os.path.realpath(raiz))


def carregar_politica(projeto: Path) -> dict:
    arquivo = projeto / ".claude" / "hooks" / "politica.json"
    politica = dict(POLITICA_PADRAO)
    if arquivo.exists():
        politica.update(json.loads(arquivo.read_text(encoding="utf-8")))
    return politica


def caminho_alvo(evento: dict, projeto: Path) -> Path | None:
    """Caminho real (symlinks e '..' resolvidos) do arquivo que a ferramenta vai tocar."""
    entrada = evento.get("tool_input") or {}
    bruto = entrada.get("file_path") or entrada.get("notebook_path")
    if not bruto:
        return None
    alvo = Path(bruto)
    if not alvo.is_absolute():
        alvo = Path(evento.get("cwd") or projeto) / alvo
    return Path(os.path.realpath(alvo))


def dentro_de(alvo: Path, pasta: Path) -> bool:
    return alvo == pasta or pasta in alvo.parents


def agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def registrar(projeto: Path, relativo: str, linha: str) -> None:
    destino = projeto / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("a", encoding="utf-8") as fh:
        fh.write(linha.rstrip("\n") + "\n")
