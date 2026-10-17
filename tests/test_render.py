from decimal import Decimal as D

from matching_engine.book import OrderBook
from matching_engine.formatting import render_book
from matching_engine.models import Order, OrderType, Side


def limit(seq, side, price, qty):
    return Order(f"identificador_{seq}", seq, side, OrderType.LIMIT, qty, D(price))


def test_render_empty_book_shows_only_header():
    lines = render_book(OrderBook()).split("\n")
    assert lines == [
        "Ordens de Compra".ljust(19) + " | Ordens de Venda",
        "-" * 20 + "|" + "-" * 17,
    ]


def test_render_matches_statement_layout():
    book = OrderBook()
    book.add(limit(1, Side.BUY, "10", 200))
    book.add(limit(2, Side.BUY, "9.99", 100))
    book.add(limit(3, Side.SELL, "10.5", 100))
    lines = render_book(book).split("\n")
    assert lines[2] == "200 @ 10".ljust(19) + " | 100 @ 10.5"
    assert lines[3] == "100 @ 9.99".ljust(19) + " |"