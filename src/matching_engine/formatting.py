from decimal import Decimal

from matching_engine.models import Trade


def format_price(price: Decimal) -> str:
    # normalize() tira zeros à direita (10.50 -> 10.5); 'f' evita notação científica (1E+2 -> 100)
    return format(price.normalize(), "f")


def format_trade(trade: Trade) -> str:
    return f"Trade, price: {format_price(trade.price)}, qty: {trade.qty}"