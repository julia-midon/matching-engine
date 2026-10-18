from decimal import Decimal

import pytest

from matching_engine.models import InvalidOrderError, Order, OrderType, PegReference, Side


def make(**overrides):
    params = dict(
        id="identificador_1",
        seq=1,
        side=Side.BUY,
        type=OrderType.LIMIT,
        qty=100,
        price=Decimal("10"),
    )
    params.update(overrides)
    return Order(**params)


def test_valid_limit_order():
    order = make()
    assert order.qty == 100 and order.price == Decimal("10")


def test_valid_market_order_has_no_price():
    assert make(type=OrderType.MARKET, price=None).price is None


def test_limit_requires_price():
    with pytest.raises(InvalidOrderError):
        make(price=None)


def test_market_rejects_price():
    with pytest.raises(InvalidOrderError):
        make(type=OrderType.MARKET, price=Decimal("10"))


@pytest.mark.parametrize("qty", [0, -5])
def test_qty_must_be_positive(qty):
    with pytest.raises(InvalidOrderError):
        make(qty=qty)


@pytest.mark.parametrize("qty", [1.5, "10", True])
def test_qty_must_be_int(qty):
    with pytest.raises(InvalidOrderError):
        make(qty=qty)


@pytest.mark.parametrize(
    "price",
    [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")],
)
def test_price_must_be_finite_positive(price):
    with pytest.raises(InvalidOrderError):
        make(price=price)


def test_price_rejects_float():
    with pytest.raises(InvalidOrderError):
        make(price=10.5)


def test_side_opposite():
    assert Side.BUY.opposite is Side.SELL
    assert Side.SELL.opposite is Side.BUY


def test_peg_reference_book_side():
    assert PegReference.BID.book_side is Side.BUY
    assert PegReference.OFFER.book_side is Side.SELL


@pytest.mark.parametrize(
    ("side", "reference"),
    [(Side.BUY, PegReference.BID), (Side.SELL, PegReference.OFFER)],
)
def test_pegged_order_may_have_no_price_while_inactive(side, reference):
    order = make(side=side, type=OrderType.PEGGED, price=None, reference=reference)
    assert order.price is None


def test_pegged_order_requires_reference():
    with pytest.raises(InvalidOrderError):
        make(type=OrderType.PEGGED, price=None)


@pytest.mark.parametrize(
    ("side", "reference"),
    [(Side.SELL, PegReference.BID), (Side.BUY, PegReference.OFFER)],
)
def test_pegged_order_must_follow_its_own_side(side, reference):
    with pytest.raises(InvalidOrderError):
        make(side=side, type=OrderType.PEGGED, price=None, reference=reference)


@pytest.mark.parametrize("order_type", [OrderType.LIMIT, OrderType.MARKET])
def test_only_pegged_orders_have_a_reference(order_type):
    price = Decimal("10") if order_type is OrderType.LIMIT else None
    with pytest.raises(InvalidOrderError):
        make(type=order_type, price=price, reference=PegReference.BID)