from dataclasses import replace
from decimal import Decimal

from matching_engine.book import OrderBook
from matching_engine.ids import SequenceGenerator, make_order_id
from matching_engine.models import Order, OrderNotFoundError, OrderType, Side, Trade


class MatchingEngine:
    def __init__(self) -> None:
        self.book = OrderBook()
        self._sequence = SequenceGenerator()

    def limit(self, side: Side, price: Decimal, qty: int) -> tuple[Order, list[Trade]]:
        """Executa o que cruzar; o saldo vira ordem resting no book."""
        order = self._new_order(side, OrderType.LIMIT, qty, price)
        trades = self._match(order)
        if order.qty > 0:
            self.book.add(order)
        return order, trades

    def market(self, side: Side, qty: int) -> tuple[Order, list[Trade]]:
        """Executa contra a liquidez disponível; o saldo não executado é descartado."""
        order = self._new_order(side, OrderType.MARKET, qty)
        return order, self._match(order)

    def cancel(self, order_id: str) -> Order:
        """Remove a ordem do book. Ordem inexistente (ou já executada) é um erro explícito."""
        order = self.book.remove(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        return order

    def modify(self, order_id: str, new_price: Decimal, new_qty: int) -> list[Trade]:
        """Altera preço e quantidade restante de uma ordem resting.

        - mesmo preço e quantidade menor ou igual: mantém a posição na fila;
        - preço diferente ou quantidade maior: perde prioridade (fim da fila do nível);
        - se a ordem alterada passar a cruzar o book, executa como agressora.
        """
        order = self.book.get(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        replace(order, price=new_price, qty=new_qty)  # revalida sem alterar a ordem original

        if new_price == order.price and new_qty <= order.qty:
            order.qty = new_qty
            return []

        self.book.remove(order.id)
        order.price = new_price
        order.qty = new_qty
        order.seq = self._sequence.next()
        trades = self._match(order)
        if order.qty > 0:
            self.book.add(order)
        return trades

    def _new_order(
        self, side: Side, order_type: OrderType, qty: int, price: Decimal | None = None
    ) -> Order:
        seq = self._sequence.next()
        return Order(make_order_id(seq), seq, side, order_type, qty, price)

    def _match(self, order: Order) -> list[Trade]:
        trades: list[Trade] = []
        opposite = order.side.opposite
        while order.qty > 0:
            passive = self.book.best_order(opposite)
            if passive is None:
                break
            if order.type is OrderType.LIMIT and not self._crosses(order, passive):
                break
            fill = min(order.qty, passive.qty)
            order.qty -= fill
            passive.qty -= fill
            if passive.qty == 0:
                self.book.remove(passive.id)
            if trades and trades[-1].price == passive.price:
                last = trades[-1]
                trades[-1] = Trade(last.price, last.qty + fill, last.aggressor_id)
            else:
                trades.append(Trade(passive.price, fill, order.id))
        return trades

    @staticmethod
    def _crosses(order: Order, passive: Order) -> bool:
        if order.side is Side.BUY:
            return order.price >= passive.price
        return order.price <= passive.price