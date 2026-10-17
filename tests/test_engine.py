from decimal import Decimal as D

from matching_engine.engine import MatchingEngine
from matching_engine.formatting import format_trade
from matching_engine.models import Side


def lines(trades):
    return [format_trade(t) for t in trades]


def test_statement_example():
    engine = MatchingEngine()
    engine.limit(Side.BUY, D("10"), 100)
    engine.limit(Side.SELL, D("20"), 100)
    engine.limit(Side.SELL, D("20"), 200)

    _, trades = engine.market(Side.BUY, 150)
    assert lines(trades) == ["Trade, price: 20, qty: 150"]

    _, trades = engine.market(Side.BUY, 200)
    assert lines(trades) == ["Trade, price: 20, qty: 150"]

    _, trades = engine.market(Side.SELL, 200)
    assert lines(trades) == ["Trade, price: 10, qty: 100"]


def test_order_ids_are_sequential():
    engine = MatchingEngine()
    first, _ = engine.limit(Side.BUY, D("10"), 100)
    second, _ = engine.limit(Side.BUY, D("10"), 100)
    assert (first.id, second.id) == ("identificador_1", "identificador_2")


def test_limit_that_does_not_cross_rests_in_book():
    engine = MatchingEngine()
    engine.limit(Side.SELL, D("11"), 100)
    _, trades = engine.limit(Side.BUY, D("10"), 100)
    assert trades == []
    assert engine.book.best_price(Side.BUY) == D("10")


def test_crossing_buy_limit_executes_at_passive_price_and_rests_remainder():
    engine = MatchingEngine()
    engine.limit(Side.SELL, D("10"), 100)
    order, trades = engine.limit(Side.BUY, D("11"), 150)
    assert lines(trades) == ["Trade, price: 10, qty: 100"]
    assert order.qty == 50
    assert engine.book.best_price(Side.SELL) is None
    assert engine.book.best_price(Side.BUY) == D("11")


def test_crossing_sell_limit_executes_at_passive_price():
    engine = MatchingEngine()
    engine.limit(Side.BUY, D("10"), 100)
    _, trades = engine.limit(Side.SELL, D("9"), 40)
    assert lines(trades) == ["Trade, price: 10, qty: 40"]
    assert engine.book.orders(Side.BUY)[0].qty == 60


def test_market_sweeps_multiple_price_levels():
    engine = MatchingEngine()
    engine.limit(Side.SELL, D("10"), 100)
    engine.limit(Side.SELL, D("11"), 100)
    _, trades = engine.market(Side.BUY, 150)
    assert lines(trades) == ["Trade, price: 10, qty: 100", "Trade, price: 11, qty: 50"]
    assert engine.book.orders(Side.SELL)[0].qty == 50


def test_market_without_liquidity_is_discarded():
    engine = MatchingEngine()
    order, trades = engine.market(Side.BUY, 100)
    assert trades == []
    assert engine.book.orders(Side.BUY) == []
    assert order.qty == 100


def test_time_priority_within_price_level():
    engine = MatchingEngine()
    engine.limit(Side.SELL, D("20"), 100)
    engine.limit(Side.SELL, D("20"), 200)
    engine.market(Side.BUY, 100)
    remaining = engine.book.orders(Side.SELL)
    assert [(o.id, o.qty) for o in remaining] == [("identificador_2", 200)]


def test_partial_fill_of_passive_order_keeps_it_in_book():
    engine = MatchingEngine()
    engine.limit(Side.SELL, D("10"), 100)
    _, trades = engine.market(Side.BUY, 30)
    assert lines(trades) == ["Trade, price: 10, qty: 30"]
    assert engine.book.orders(Side.SELL)[0].qty == 70