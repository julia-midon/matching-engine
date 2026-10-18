from decimal import Decimal as D

import pytest

from matching_engine.engine import MatchingEngine
from matching_engine.formatting import format_trade
from matching_engine.models import InvalidOrderError, OrderNotFoundError, Side


def order_ids(engine, side):
    return [o.id for o in engine.book.orders(side)]


def two_bids_at_10():
    engine = MatchingEngine()
    first, _ = engine.limit(Side.BUY, D("10"), 100)
    second, _ = engine.limit(Side.BUY, D("10"), 100)
    return engine, first, second


def test_statement_price_change_example():
    engine = MatchingEngine()
    first, _ = engine.limit(Side.BUY, D("10"), 200)
    second, _ = engine.limit(Side.BUY, D("9.99"), 100)
    ask, _ = engine.limit(Side.SELL, D("10.5"), 100)

    trades = engine.modify(first.id, D("9.98"), 200)

    assert trades == []
    bids = [(o.id, o.qty, o.price) for o in engine.book.orders(Side.BUY)]
    assert bids == [(second.id, 100, D("9.99")), (first.id, 200, D("9.98"))]
    assert order_ids(engine, Side.SELL) == [ask.id]


def test_reducing_quantity_keeps_priority():
    engine, first, second = two_bids_at_10()
    engine.modify(first.id, D("10"), 40)
    assert order_ids(engine, Side.BUY) == [first.id, second.id]
    assert first.qty == 40


def test_unchanged_price_and_quantity_is_a_no_op():
    engine, first, second = two_bids_at_10()
    assert engine.modify(first.id, D("10"), 100) == []
    assert order_ids(engine, Side.BUY) == [first.id, second.id]


def test_same_price_in_another_decimal_form_keeps_priority_on_reduce():
    engine, first, second = two_bids_at_10()
    engine.modify(first.id, D("10.00"), 50)
    assert order_ids(engine, Side.BUY) == [first.id, second.id]


def test_increasing_quantity_loses_priority():
    engine, first, second = two_bids_at_10()
    engine.modify(first.id, D("10"), 150)
    assert order_ids(engine, Side.BUY) == [second.id, first.id]
    assert first.qty == 150


def test_omitted_price_keeps_current_price():
    engine, first, second = two_bids_at_10()
    engine.modify(first.id, None, 150)
    assert first.price == D("10")
    assert order_ids(engine, Side.BUY) == [second.id, first.id]
    

def test_quantity_is_the_remaining_quantity():
    engine = MatchingEngine()
    first, _ = engine.limit(Side.SELL, D("10"), 100)
    second, _ = engine.limit(Side.SELL, D("10"), 100)
    engine.market(Side.BUY, 30)  # first passa a ter 70 restantes
    engine.modify(first.id, D("10"), 80)  # 80 > 70: é um aumento, perde prioridade
    assert order_ids(engine, Side.SELL) == [second.id, first.id]


def test_price_change_goes_to_end_of_the_new_level():
    engine = MatchingEngine()
    first, _ = engine.limit(Side.BUY, D("10"), 100)
    second, _ = engine.limit(Side.BUY, D("10"), 100)
    third, _ = engine.limit(Side.BUY, D("9"), 100)
    engine.modify(first.id, D("9"), 100)
    assert order_ids(engine, Side.BUY) == [second.id, third.id, first.id]


def test_better_price_without_crossing_becomes_best_bid():
    engine = MatchingEngine()
    engine.limit(Side.BUY, D("10"), 100)
    low, _ = engine.limit(Side.BUY, D("9"), 100)
    engine.limit(Side.SELL, D("12"), 100)
    engine.modify(low.id, D("11"), 100)
    assert engine.book.best_order(Side.BUY).id == low.id
    assert engine.book.best_price(Side.BUY) == D("11")


def test_price_and_quantity_can_change_together():
    engine = MatchingEngine()
    order, _ = engine.limit(Side.SELL, D("10"), 100)
    engine.modify(order.id, D("12"), 30)
    assert (order.price, order.qty) == (D("12"), 30)
    assert engine.book.best_price(Side.SELL) == D("12")


def test_modify_that_crosses_executes_at_passive_price():
    engine = MatchingEngine()
    engine.limit(Side.SELL, D("11"), 100)
    bid, _ = engine.limit(Side.BUY, D("10"), 100)
    trades = engine.modify(bid.id, D("11"), 100)
    assert [format_trade(t) for t in trades] == ["Trade, price: 11, qty: 100"]
    assert engine.book.get(bid.id) is None
    assert engine.book.orders(Side.SELL) == []


def test_modify_that_partially_crosses_rests_remainder_with_same_id():
    engine = MatchingEngine()
    engine.limit(Side.SELL, D("11"), 40)
    bid, _ = engine.limit(Side.BUY, D("10"), 100)
    trades = engine.modify(bid.id, D("11"), 100)
    assert [format_trade(t) for t in trades] == ["Trade, price: 11, qty: 40"]
    assert engine.book.get(bid.id).qty == 60
    assert engine.book.best_price(Side.BUY) == D("11")


def test_sell_side_modify_that_crosses_executes():
    engine = MatchingEngine()
    engine.limit(Side.BUY, D("10"), 100)
    ask, _ = engine.limit(Side.SELL, D("11"), 60)
    trades = engine.modify(ask.id, D("10"), 60)
    assert [format_trade(t) for t in trades] == ["Trade, price: 10, qty: 60"]
    assert engine.book.orders(Side.SELL) == []


def test_modify_unknown_id_raises():
    with pytest.raises(OrderNotFoundError):
        MatchingEngine().modify("identificador_99", D("10"), 10)


def test_modify_fully_executed_order_raises():
    engine = MatchingEngine()
    sell, _ = engine.limit(Side.SELL, D("10"), 100)
    engine.market(Side.BUY, 100)
    with pytest.raises(OrderNotFoundError):
        engine.modify(sell.id, D("11"), 100)


@pytest.mark.parametrize(
    ("price", "qty"),
    [(D("10"), 0), (D("10"), -1), (D("0"), 10), (10.5, 10), (D("10"), 1.5)],
)
def test_invalid_modify_raises_and_leaves_order_untouched(price, qty):
    engine, first, second = two_bids_at_10()
    with pytest.raises(InvalidOrderError):
        engine.modify(first.id, price, qty)
    assert (first.price, first.qty) == (D("10"), 100)
    assert order_ids(engine, Side.BUY) == [first.id, second.id]