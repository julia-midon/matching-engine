from bisect import insort
from collections import deque
from decimal import Decimal

from matching_engine.models import Order, Side


class OrderBook:
    """Níveis de preço por lado; dentro de cada nível, FIFO por ordem de chegada."""

    def __init__(self) -> None:
        self._levels: dict[Side, dict[Decimal, deque[Order]]] = {Side.BUY: {}, Side.SELL: {}}
        self._prices: dict[Side, list[Decimal]] = {Side.BUY: [], Side.SELL: []}  # crescente
        self._index: dict[str, Order] = {}

    def add(self, order: Order) -> None:
        if order.price is None:
            raise ValueError("only priced orders can rest in the book")
        levels = self._levels[order.side]
        if order.price not in levels:
            levels[order.price] = deque()
            insort(self._prices[order.side], order.price)
        levels[order.price].append(order)
        self._index[order.id] = order

    def best_price(self, side: Side) -> Decimal | None:
        prices = self._prices[side]
        if not prices:
            return None
        return prices[-1] if side is Side.BUY else prices[0]

    def best_order(self, side: Side) -> Order | None:
        price = self.best_price(side)
        if price is None:
            return None
        return self._levels[side][price][0]

    def get(self, order_id: str) -> Order | None:
        return self._index.get(order_id)

    def remove(self, order_id: str) -> Order | None:
        order = self._index.pop(order_id, None)
        if order is None:
            return None
        level = self._levels[order.side][order.price]
        level.remove(order)
        if not level:
            del self._levels[order.side][order.price]
            self._prices[order.side].remove(order.price)
        return order

    def orders(self, side: Side) -> list[Order]:
        """Ordens na ordem de prioridade: melhor preço primeiro, depois chegada."""
        prices = reversed(self._prices[side]) if side is Side.BUY else self._prices[side]
        return [order for price in prices for order in self._levels[side][price]]