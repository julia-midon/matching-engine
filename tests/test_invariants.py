"""Teste de propriedades: sequências aleatórias de operações nunca quebram as regras do book."""

import random
from decimal import Decimal

import pytest

from matching_engine.engine import MatchingEngine
from matching_engine.models import (
    InvalidOrderError,
    OrderNotFoundError,
    OrderType,
    PegReference,
    Side,
)

PRICES = [Decimal(price) for price in ("9", "9.5", "10", "10.5", "11")]


def assert_invariants(engine: MatchingEngine) -> None:
    book = engine.book

    best_bid = book.best_price(Side.BUY)
    best_ask = book.best_price(Side.SELL)
    if best_bid is not None and best_ask is not None:
        assert best_bid < best_ask, "book cruzado"

    resting_pegs = set()
    for side in (Side.BUY, Side.SELL):
        orders = book.orders(side)
        # prioridade: melhor preço primeiro e, no mesmo preço, seq crescente
        keys = [(-o.price if side is Side.BUY else o.price, o.seq) for o in orders]
        assert keys == sorted(keys), "fila fora da ordem de prioridade"
        for order in orders:
            assert order.qty > 0
            assert order.side is side
            assert book.get(order.id) is order
            if order.type is OrderType.PEGGED:
                resting_pegs.add(order.id)

    live_pegs = engine.pegged_orders()
    for peg in live_pegs:
        assert peg.price == book.best_anchor_price(peg.reference.book_side)
        assert (peg.id in resting_pegs) == (peg.price is not None)
    assert resting_pegs <= {peg.id for peg in live_pegs}


def random_step(engine: MatchingEngine, rng: random.Random, created: list[str]) -> None:
    action = rng.choice(["limit", "limit", "market", "peg", "cancel", "modify"])
    side = rng.choice(list(Side))
    qty = rng.randint(1, 5) * 10

    if action == "limit":
        order, _ = engine.limit(side, rng.choice(PRICES), qty)
        created.append(order.id)
    elif action == "market":
        engine.market(side, qty)
    elif action == "peg":
        reference = PegReference.BID if side is Side.BUY else PegReference.OFFER
        created.append(engine.peg(side, reference, qty).id)
    elif created:
        order_id = rng.choice(created)
        try:
            if action == "cancel":
                engine.cancel(order_id)
            else:
                engine.modify(order_id, rng.choice([None, *PRICES]), qty)
        except (OrderNotFoundError, InvalidOrderError):
            pass  # ordem já executada/cancelada, ou preço informado para uma pegged


@pytest.mark.parametrize("seed", range(40))
def test_random_operations_preserve_book_invariants(seed):
    rng = random.Random(seed)
    engine = MatchingEngine()
    created: list[str] = []
    for _ in range(300):
        random_step(engine, rng, created)
        assert_invariants(engine)