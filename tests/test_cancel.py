from decimal import Decimal as D

import pytest

from matching_engine.engine import MatchingEngine
from matching_engine.models import OrderNotFoundError, Side


def order_ids(engine, side):
    return [o.id for o in engine.book.orders(side)]


def test_cancel_removes_order_from_book():
    engine = MatchingEngine()
    order, _ = engine.limit(Side.BUY, D("10"), 100)
    cancelled = engine.cancel(order.id)
    assert cancelled.id == order.id
    assert engine.book.orders(Side.BUY) == []
    assert engine.book.get(order.id) is None


def test_cancelled_order_is_never_matched():
    engine = MatchingEngine()
    sell, _ = engine.limit(Side.SELL, D("10"), 100)
    engine.cancel(sell.id)
    _, trades = engine.market(Side.BUY, 100)
    assert trades == []


def test_cancel_keeps_priority_of_remaining_orders():
    engine = MatchingEngine()
    first, _ = engine.limit(Side.BUY, D("10"), 100)
    middle, _ = engine.limit(Side.BUY, D("10"), 100)
    last, _ = engine.limit(Side.BUY, D("10"), 100)
    engine.cancel(middle.id)
    assert order_ids(engine, Side.BUY) == [first.id, last.id]


def test_cancel_last_order_of_level_updates_best_price():
    engine = MatchingEngine()
    top, _ = engine.limit(Side.BUY, D("10"), 100)
    engine.limit(Side.BUY, D("9"), 100)
    engine.cancel(top.id)
    assert engine.book.best_price(Side.BUY) == D("9")


def test_cancel_partially_executed_order_removes_remainder():
    engine = MatchingEngine()
    sell, _ = engine.limit(Side.SELL, D("10"), 100)
    engine.market(Side.BUY, 30)
    assert engine.cancel(sell.id).qty == 70
    assert engine.book.orders(Side.SELL) == []


def test_cancel_unknown_id_raises():
    with pytest.raises(OrderNotFoundError):
        MatchingEngine().cancel("identificador_99")


def test_cancel_twice_raises():
    engine = MatchingEngine()
    order, _ = engine.limit(Side.BUY, D("10"), 100)
    engine.cancel(order.id)
    with pytest.raises(OrderNotFoundError):
        engine.cancel(order.id)


def test_cancel_fully_executed_order_raises():
    engine = MatchingEngine()
    sell, _ = engine.limit(Side.SELL, D("10"), 100)
    engine.market(Side.BUY, 100)
    with pytest.raises(OrderNotFoundError):
        engine.cancel(sell.id)