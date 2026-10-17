from decimal import Decimal as D

from matching_engine.book import OrderBook
from matching_engine.models import Order, OrderType, Side


def limit(seq, side, price, qty):
    return Order(f"identificador_{seq}", seq, side, OrderType.LIMIT, qty, D(price))


def ids(orders):
    return [o.id for o in orders]


def test_empty_book_has_no_best_price():
    book = OrderBook()
    assert book.best_price(Side.BUY) is None
    assert book.best_price(Side.SELL) is None
    assert book.best_order(Side.BUY) is None


def test_bids_sorted_by_price_desc_then_arrival():
    book = OrderBook()
    book.add(limit(1, Side.BUY, "9.99", 100))
    book.add(limit(2, Side.BUY, "10", 200))
    book.add(limit(3, Side.BUY, "10", 150))
    assert ids(book.orders(Side.BUY)) == ["identificador_2", "identificador_3", "identificador_1"]
    assert book.best_price(Side.BUY) == D("10")


def test_asks_sorted_by_price_asc_then_arrival():
    book = OrderBook()
    book.add(limit(1, Side.SELL, "10.5", 100))
    book.add(limit(2, Side.SELL, "10.1", 100))
    book.add(limit(3, Side.SELL, "10.1", 50))
    assert ids(book.orders(Side.SELL)) == ["identificador_2", "identificador_3", "identificador_1"]
    assert book.best_price(Side.SELL) == D("10.1")


def test_same_price_with_different_decimal_form_shares_level():
    book = OrderBook()
    book.add(limit(1, Side.BUY, "10", 100))
    book.add(limit(2, Side.BUY, "10.00", 100))
    assert ids(book.orders(Side.BUY)) == ["identificador_1", "identificador_2"]


def test_remove_drops_empty_level_and_unknown_id_returns_none():
    book = OrderBook()
    book.add(limit(1, Side.SELL, "10", 5))
    assert book.remove("identificador_1") is not None
    assert book.best_price(Side.SELL) is None
    assert book.remove("identificador_1") is None