from decimal import Decimal as D

import pytest

from matching_engine.engine import MatchingEngine
from matching_engine.formatting import format_trade, render_book
from matching_engine.models import InvalidOrderError, OrderNotFoundError, PegReference, Side

HEADER = [
    "Ordens de Compra".ljust(19) + " | Ordens de Venda",
    "-" * 20 + "|" + "-" * 17,
]


def row(left="", right=""):
    return f"{left:<19} | {right}".rstrip()


def rendered(engine):
    return render_book(engine.book).split("\n")


def bid_prices(engine):
    return [o.price for o in engine.book.orders(Side.BUY)]


def bid_ids(engine):
    return [o.id for o in engine.book.orders(Side.BUY)]


def peg_bid(engine, qty):
    return engine.peg(Side.BUY, PegReference.BID, qty)


def peg_offer(engine, qty):
    return engine.peg(Side.SELL, PegReference.OFFER, qty)


def statement_book():
    """Book do enunciado: compras 200 @ 10 e 100 @ 9.99; venda 100 @ 10.5."""
    engine = MatchingEngine()
    engine.limit(Side.BUY, D("10"), 200)
    engine.limit(Side.BUY, D("9.99"), 100)
    engine.limit(Side.SELL, D("10.5"), 100)
    return engine


def test_statement_example_peg_to_bid():
    engine = statement_book()

    peg_bid(engine, 150)
    assert rendered(engine) == [
        *HEADER,
        row("200 @ 10", "100 @ 10.5"),
        row("150 @ 10"),
        row("100 @ 9.99"),
    ]

    engine.limit(Side.BUY, D("10.1"), 300)
    assert rendered(engine) == [
        *HEADER,
        row("150 @ 10.1", "100 @ 10.5"),
        row("300 @ 10.1"),
        row("200 @ 10"),
        row("100 @ 9.99"),
    ]


def test_peg_to_offer_follows_best_ask():
    engine = statement_book()
    peg = peg_offer(engine, 80)
    assert peg.price == D("10.5")

    engine.limit(Side.SELL, D("10.2"), 50)
    assert peg.price == D("10.2")
    assert [(o.qty, o.price) for o in engine.book.orders(Side.SELL)] == [
        (80, D("10.2")),
        (50, D("10.2")),
        (100, D("10.5")),
    ]


def test_peg_keeps_its_original_time_priority_when_repriced():
    engine = MatchingEngine()
    early, _ = engine.limit(Side.BUY, D("10"), 100)
    peg = peg_bid(engine, 50)
    late, _ = engine.limit(Side.BUY, D("11"), 100)
    # a pegged nasceu depois de `early` e antes de `late`: ao subir para 11, fica à frente de `late`
    assert peg.price == D("11")
    assert bid_ids(engine) == [peg.id, late.id, early.id]


def test_peg_follows_best_bid_down_when_it_is_cancelled():
    engine = MatchingEngine()
    top, _ = engine.limit(Side.BUY, D("10"), 100)
    engine.limit(Side.BUY, D("9"), 100)
    peg = peg_bid(engine, 50)
    assert peg.price == D("10")

    engine.cancel(top.id)
    assert peg.price == D("9")
    assert engine.book.best_price(Side.BUY) == D("9")


def test_pegs_do_not_follow_each_other():
    engine = MatchingEngine()
    first = peg_bid(engine, 10)
    second = peg_bid(engine, 20)
    assert first.price is None and second.price is None
    assert engine.book.orders(Side.BUY) == []

    engine.limit(Side.BUY, D("10"), 100)
    assert first.price == second.price == D("10")


def test_peg_without_reference_is_inactive_until_one_appears():
    engine = MatchingEngine()
    peg = peg_bid(engine, 100)
    assert peg.price is None
    assert engine.book.orders(Side.BUY) == []
    assert engine.pegged_orders() == [peg]

    engine.limit(Side.BUY, D("10"), 50)
    assert peg.price == D("10")
    assert engine.book.get(peg.id) is peg


def test_peg_becomes_inactive_when_its_reference_disappears():
    engine = MatchingEngine()
    only, _ = engine.limit(Side.BUY, D("10"), 100)
    peg = peg_bid(engine, 50)
    engine.cancel(only.id)
    assert peg.price is None
    assert engine.book.orders(Side.BUY) == []
    assert engine.pegged_orders() == [peg]


def test_peg_is_matched_as_a_passive_order_in_time_priority():
    engine = MatchingEngine()
    first, _ = engine.limit(Side.BUY, D("10"), 100)
    peg = peg_bid(engine, 50)
    engine.limit(Side.BUY, D("9"), 100)

    _, trades = engine.market(Side.SELL, 120)

    assert [format_trade(t) for t in trades] == ["Trade, price: 10, qty: 120"]
    assert engine.book.get(first.id) is None
    assert peg.qty == 30


def test_peg_is_repriced_after_the_match_not_during_it():
    engine = MatchingEngine()
    engine.limit(Side.BUY, D("10"), 200)
    engine.limit(Side.BUY, D("9"), 100)
    peg = peg_bid(engine, 150)

    _, trades = engine.market(Side.SELL, 300)

    # a pegged ainda estava a 10 quando foi executada; só depois acompanha o novo bid
    assert [format_trade(t) for t in trades] == ["Trade, price: 10, qty: 300"]
    assert peg.qty == 50
    assert peg.price == D("9")
    assert bid_prices(engine) == [D("9"), D("9")]


def test_fully_executed_peg_is_forgotten():
    engine = MatchingEngine()
    engine.limit(Side.BUY, D("10"), 100)
    peg_bid(engine, 50)
    engine.market(Side.SELL, 150)
    assert engine.pegged_orders() == []
    assert engine.book.orders(Side.BUY) == []


def test_peg_never_trades_when_created_or_repriced():
    engine = statement_book()
    peg_bid(engine, 100)
    peg_offer(engine, 100)
    _, trades = engine.limit(Side.BUY, D("10.4"), 100)
    assert trades == []
    assert engine.book.best_price(Side.BUY) == D("10.4")
    assert engine.book.best_price(Side.SELL) == D("10.5")


def test_cancel_active_peg():
    engine = statement_book()
    peg = peg_bid(engine, 150)
    assert engine.cancel(peg.id) is peg
    assert engine.pegged_orders() == []
    assert peg.id not in bid_ids(engine)


def test_cancel_inactive_peg():
    engine = MatchingEngine()
    peg = peg_bid(engine, 150)
    assert engine.cancel(peg.id) is peg
    assert engine.pegged_orders() == []
    with pytest.raises(OrderNotFoundError):
        engine.cancel(peg.id)


def test_reducing_peg_quantity_keeps_priority():
    engine = statement_book()
    peg = peg_bid(engine, 150)
    other, _ = engine.limit(Side.BUY, D("10"), 10)
    engine.modify(peg.id, None, 100)
    assert bid_ids(engine)[:3] == ["identificador_1", peg.id, other.id]
    assert peg.qty == 100


def test_increasing_peg_quantity_loses_priority():
    engine = statement_book()
    peg = peg_bid(engine, 150)
    other, _ = engine.limit(Side.BUY, D("10"), 10)
    engine.modify(peg.id, None, 200)
    assert bid_ids(engine)[:3] == ["identificador_1", other.id, peg.id]
    assert peg.qty == 200


def test_modify_quantity_of_inactive_peg():
    engine = MatchingEngine()
    peg = peg_bid(engine, 100)
    engine.modify(peg.id, None, 40)
    assert peg.qty == 40
    engine.modify(peg.id, None, 90)
    assert peg.qty == 90
    assert peg.price is None


def test_modify_peg_price_is_rejected():
    engine = statement_book()
    peg = peg_bid(engine, 150)
    with pytest.raises(InvalidOrderError):
        engine.modify(peg.id, D("9"), 150)
    assert (peg.price, peg.qty) == (D("10"), 150)


def test_modify_peg_with_invalid_quantity_leaves_it_untouched():
    engine = statement_book()
    peg = peg_bid(engine, 150)
    with pytest.raises(InvalidOrderError):
        engine.modify(peg.id, None, 0)
    assert peg.qty == 150


def test_modify_of_regular_order_moves_the_peg():
    engine = MatchingEngine()
    bid, _ = engine.limit(Side.BUY, D("10"), 100)
    engine.limit(Side.SELL, D("12"), 100)
    peg = peg_bid(engine, 50)
    engine.modify(bid.id, D("11"), 100)
    assert peg.price == D("11")


@pytest.mark.parametrize(
    ("side", "reference"),
    [(Side.SELL, PegReference.BID), (Side.BUY, PegReference.OFFER)],
)
def test_peg_on_the_opposite_side_is_rejected_without_consuming_an_id(side, reference):
    engine = MatchingEngine()
    with pytest.raises(InvalidOrderError):
        engine.peg(side, reference, 100)
    order, _ = engine.limit(Side.BUY, D("10"), 100)
    assert order.id == "identificador_1"


def test_peg_with_invalid_quantity_is_rejected():
    engine = MatchingEngine()
    with pytest.raises(InvalidOrderError):
        peg_bid(engine, 0)
    assert engine.pegged_orders() == []