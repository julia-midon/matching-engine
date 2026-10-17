from decimal import Decimal

import pytest

from matching_engine.models import InvalidOrderError, Order, OrderType, Side


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