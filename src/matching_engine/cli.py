"""Linha de comando: modo interativo (com prompt) e modo arquivo/stdin (um comando por linha)."""

import argparse
import io
import sys
from pathlib import Path
from typing import TextIO

from matching_engine.commands import CommandProcessor

PROMPT = ">>> "
BANNER = "Matching engine. Type 'help' for the commands and 'exit' to quit."
EXIT_COMMANDS = {"exit", "quit"}


def run(
    source: TextIO,
    out: TextIO,
    processor: CommandProcessor | None = None,
    *,
    interactive: bool = False,
    echo: bool = False,
) -> None:
    """Lê comandos de `source` até o fim ou até `exit`, escrevendo as saídas em `out`.

    Linhas em branco e comentários (`#`) são ignorados. Com `echo`, cada comando é repetido
    como `>>> comando` antes da sua saída, o formato dos exemplos do enunciado.
    """
    processor = processor if processor is not None else CommandProcessor()
    if interactive:
        print(BANNER, file=out)

    while True:
        if interactive:
            out.write(PROMPT)
            out.flush()
        raw = source.readline()
        if raw == "":  # fim da entrada (Ctrl+D / Ctrl+Z)
            if interactive:
                print(file=out)
            return

        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower() in EXIT_COMMANDS:
            return
        if echo and not interactive:
            print(f"{PROMPT}{line}", file=out)
        for text in processor.execute(line):
            print(text, file=out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m matching_engine",
        description="Matching engine de um ativo, em memória. Sem arquivo, abre o modo interativo.",
    )
    parser.add_argument(
        "script",
        nargs="?",
        type=Path,
        help="arquivo de texto com um comando por linha",
    )
    parser.add_argument(
        "--echo",
        action="store_true",
        help="repete cada comando como '>>> comando' antes da saída (modo arquivo ou stdin)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.script is None:
            run(sys.stdin, sys.stdout, interactive=sys.stdin.isatty(), echo=args.echo)
            return 0

        # utf-8-sig aceita arquivos salvos com BOM; ler tudo antes evita saída parcial se falhar.
        try:
            text = args.script.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as error:
            print(f"Error: cannot read '{args.script}': {error}", file=sys.stderr)
            return 1
        run(io.StringIO(text), sys.stdout, echo=args.echo)
        return 0
    except KeyboardInterrupt:
        print()
        return 130