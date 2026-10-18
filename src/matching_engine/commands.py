"""Tradução de comandos de texto em operações do MatchingEngine."""

import re
from collections.abc import Callable
from decimal import Decimal

from matching_engine.engine import MatchingEngine
from matching_engine.formatting import format_price, format_trade, render_book
from matching_engine.models import InvalidOrderError, OrderNotFoundError, PegReference, Side

# Formatos estritos: sem sinal, sem notação científica, sem NaN/Infinity e sem vírgula decimal.
# `[0-9]` (e não `\d`) recusa dígitos de outros alfabetos; o limite de tamanho evita que um
# número gigante estoure o limite de conversão de int do Python.
_PRICE = re.compile(r"[0-9]+(\.[0-9]+)?")
_QTY = re.compile(r"[0-9]{1,15}")

HELP_LINES = (
    "Commands:",
    "  limit <buy|sell> <price> <qty>",
    "  market <buy|sell> <qty>",
    "  peg <bid|offer> <buy|sell> <qty>",
    "  cancel order <id>",
    "  modify order <id> [price <price>] [qty <qty>]",
    "  print book",
    "  help",
    "  exit",
)


class CommandError(ValueError):
    """Comando mal formado: sintaxe, argumentos faltando ou valores que não são números."""


def _parse_side(token: str) -> Side:
    try:
        return Side(token)
    except ValueError:
        raise CommandError(f"invalid side '{token}' (use buy or sell)") from None


def _parse_reference(token: str) -> PegReference:
    try:
        return PegReference(token)
    except ValueError:
        raise CommandError(f"invalid peg reference '{token}' (use bid or offer)") from None


def _parse_price(token: str) -> Decimal:
    if not _PRICE.fullmatch(token):
        raise CommandError(f"invalid price '{token}' (use a number such as 10 or 9.99)")
    return Decimal(token)


def _parse_qty(token: str) -> int:
    if not _QTY.fullmatch(token):
        raise CommandError(f"invalid quantity '{token}' (use a positive integer)")
    return int(token)


def _require_arguments(args: list[str], count: int, usage: str) -> None:
    if len(args) != count:
        raise CommandError(f"usage: {usage}")


class CommandProcessor:
    """Interpreta uma linha de comando, executa no engine e devolve as linhas de saída.

    Nunca levanta exceção por entrada inválida: o erro vira uma linha `Error: ...` e o estado
    do engine não muda.
    """

    def __init__(self, engine: MatchingEngine | None = None) -> None:
        self.engine = engine if engine is not None else MatchingEngine()
        self._handlers: dict[str, Callable[[list[str]], list[str]]] = {
            "limit": self._limit,
            "market": self._market,
            "peg": self._peg,
            "cancel": self._cancel,
            "modify": self._modify,
            "print": self._print,
            "help": self._help,
        }

    def execute(self, line: str) -> list[str]:
        tokens = line.lower().split()
        if not tokens:
            return []
        try:
            handler = self._handlers.get(tokens[0])
            if handler is None:
                raise CommandError(f"unknown command '{tokens[0]}' (type 'help')")
            return handler(tokens[1:])
        except OrderNotFoundError as error:
            return [f"Error: order not found: {error}"]
        except (CommandError, InvalidOrderError) as error:
            return [f"Error: {error}"]

    def _limit(self, args: list[str]) -> list[str]:
        _require_arguments(args, 3, "limit <buy|sell> <price> <qty>")
        side, price, qty = _parse_side(args[0]), _parse_price(args[1]), _parse_qty(args[2])
        order, trades = self.engine.limit(side, price, qty)
        # A quantidade impressa é a original; `order.qty` já é o saldo após o matching.
        created = f"Order created: {side.value} {qty} @ {format_price(price)} {order.id}"
        return [created, *map(format_trade, trades)]

    def _market(self, args: list[str]) -> list[str]:
        _require_arguments(args, 2, "market <buy|sell> <qty>")
        _, trades = self.engine.market(_parse_side(args[0]), _parse_qty(args[1]))
        return [format_trade(trade) for trade in trades]

    def _peg(self, args: list[str]) -> list[str]:
        _require_arguments(args, 3, "peg <bid|offer> <buy|sell> <qty>")
        reference, side, qty = _parse_reference(args[0]), _parse_side(args[1]), _parse_qty(args[2])
        order = self.engine.peg(side, reference, qty)
        return [f"Order created: {side.value} {qty} @ peg {reference.value} {order.id}"]

    def _cancel(self, args: list[str]) -> list[str]:
        usage = "cancel order <id>"
        _require_arguments(args, 2, usage)
        if args[0] != "order":
            raise CommandError(f"usage: {usage}")
        self.engine.cancel(args[1])
        return ["Order cancelled"]

    def _modify(self, args: list[str]) -> list[str]:
        usage = "modify order <id> [price <price>] [qty <qty>]"
        options = args[2:]
        if len(args) < 4 or args[0] != "order" or len(options) % 2 != 0:
            raise CommandError(f"usage: {usage}")

        price: Decimal | None = None
        qty: int | None = None
        for key, value in zip(options[::2], options[1::2], strict=True):
            if key == "price" and price is None:
                price = _parse_price(value)
            elif key == "qty" and qty is None:
                qty = _parse_qty(value)
            else:
                raise CommandError(f"usage: {usage}")

        trades = self.engine.modify(args[1], price, qty)
        return ["Order modified", *map(format_trade, trades)]

    def _print(self, args: list[str]) -> list[str]:
        if args != ["book"]:
            raise CommandError("usage: print book")
        return render_book(self.engine.book).split("\n")

    def _help(self, args: list[str]) -> list[str]:
        return list(HELP_LINES)