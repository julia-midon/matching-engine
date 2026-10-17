from decimal import Decimal

from matching_engine.book import OrderBook
from matching_engine.models import Side, Trade


def format_price(price: Decimal) -> str:
    # normalize() tira zeros à direita (10.50 -> 10.5); 'f' evita notação científica (1E+2 -> 100)
    return format(price.normalize(), "f")


def format_trade(trade: Trade) -> str:
    return f"Trade, price: {format_price(trade.price)}, qty: {trade.qty}"


def render_book(book: OrderBook) -> str:
    bids = [f"{o.qty} @ {format_price(o.price)}" for o in book.orders(Side.BUY)]
    asks = [f"{o.qty} @ {format_price(o.price)}" for o in book.orders(Side.SELL)]
    lines = [
        "Ordens de Compra".ljust(19) + " | Ordens de Venda",
        "-" * 20 + "|" + "-" * 17,
    ]
    for i in range(max(len(bids), len(asks))):
        left = bids[i] if i < len(bids) else ""
        right = asks[i] if i < len(asks) else ""
        lines.append(f"{left:<19} | {right}".rstrip())
    return "\n".join(lines)