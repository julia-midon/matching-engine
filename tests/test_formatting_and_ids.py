from decimal import Decimal

from matching_engine.formatting import format_price, format_trade
from matching_engine.ids import SequenceGenerator, make_order_id
from matching_engine.models import Trade


def test_sequence_is_monotonic():
    gen = SequenceGenerator()
    assert [gen.next(), gen.next(), gen.next()] == [1, 2, 3]


def test_order_id_format():
    assert make_order_id(1) == "identificador_1"


def test_format_price_has_no_trailing_zeros_or_exponent():
    assert format_price(Decimal("20")) == "20"
    assert format_price(Decimal("100")) == "100"
    assert format_price(Decimal("10.50")) == "10.5"
    assert format_price(Decimal("9.99")) == "9.99"


def test_trade_output_matches_statement():
    trade = Trade(Decimal("20"), 150, "identificador_4")
    assert format_trade(trade) == "Trade, price: 20, qty: 150"