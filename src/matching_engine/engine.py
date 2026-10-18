from dataclasses import replace
from decimal import Decimal

from matching_engine.book import OrderBook
from matching_engine.ids import SequenceGenerator, make_order_id
from matching_engine.models import (
    InvalidOrderError,
    Order,
    OrderNotFoundError,
    OrderType,
    PegReference,
    Side,
    Trade,
)


class MatchingEngine:
    def __init__(self) -> None:
        self.book = OrderBook()
        self._sequence = SequenceGenerator()
        # Pegged orders vivas (no book ou inativas), por id, na ordem de criação.
        self._pegs: dict[str, Order] = {}

    def limit(self, side: Side, price: Decimal, qty: int) -> tuple[Order, list[Trade]]:
        """Executa o que cruzar; o saldo vira ordem resting no book."""
        order = self._new_order(side, OrderType.LIMIT, qty, price)
        trades = self._match(order)
        if order.qty > 0:
            self.book.add(order)
        self._reprice_pegs()
        return order, trades

    def market(self, side: Side, qty: int) -> tuple[Order, list[Trade]]:
        """Executa contra a liquidez disponível; o saldo não executado é descartado."""
        order = self._new_order(side, OrderType.MARKET, qty)
        trades = self._match(order)
        self._reprice_pegs()
        return order, trades

    def peg(self, side: Side, reference: PegReference, qty: int) -> Order:
        """Cria uma pegged order que acompanha o melhor preço não-pegged do seu lado.

        Sem referência no book, a ordem fica inativa (fora do book) até surgir uma.
        Como acompanha o próprio lado, nunca executa ao ser criada nem reprecificada.
        """
        order = self._new_order(side, OrderType.PEGGED, qty, reference=reference)
        self._pegs[order.id] = order
        self._reprice_pegs()
        return order

    def cancel(self, order_id: str) -> Order:
        """Remove a ordem. Ordem inexistente (ou já executada) é um erro explícito."""
        order = self._find(order_id)
        self.book.remove(order_id)  # sem efeito para pegged inativa, que não está no book
        self._pegs.pop(order_id, None)
        self._reprice_pegs()
        return order

    def modify(self, order_id: str, price: Decimal | None, qty: int) -> list[Trade]:
        """Altera preço e quantidade restante de uma ordem resting.

        - `price=None` mantém o preço atual (único valor aceito em pegged, cujo preço é derivado);
        - mesmo preço e quantidade menor ou igual: mantém a posição na fila;
        - preço diferente ou quantidade maior: perde prioridade (fim da fila do nível);
        - se a ordem alterada passar a cruzar o book, executa como agressora.
        """
        order = self._find(order_id)
        if order.type is OrderType.PEGGED:
            return self._modify_pegged(order, price, qty)

        new_price = order.price if price is None else price
        replace(order, price=new_price, qty=qty)  # revalida sem alterar a ordem original

        if new_price == order.price and qty <= order.qty:
            order.qty = qty
            return []

        self.book.remove(order.id)
        order.price = new_price
        order.qty = qty
        order.seq = self._sequence.next()
        trades = self._match(order)
        if order.qty > 0:
            self.book.add(order)
        self._reprice_pegs()
        return trades

    def pegged_orders(self) -> list[Order]:
        """Pegged orders vivas, inclusive as inativas (sem referência no book)."""
        return list(self._pegs.values())

    def _find(self, order_id: str) -> Order:
        order = self.book.get(order_id)
        if order is None:
            order = self._pegs.get(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        return order

    def _modify_pegged(self, order: Order, price: Decimal | None, qty: int) -> list[Trade]:
        if price is not None:
            raise InvalidOrderError(
                "a pegged order has no price of its own; only its qty can be modified"
            )
        replace(order, qty=qty)  # revalida sem alterar a ordem original

        if qty <= order.qty:
            order.qty = qty
            return []

        # Aumento de quantidade perde prioridade, como em qualquer ordem.
        is_active = order.price is not None
        if is_active:
            self.book.remove(order.id)
        order.qty = qty
        order.seq = self._sequence.next()
        if is_active:
            self.book.add(order)
        return []

    def _new_order(
        self,
        side: Side,
        order_type: OrderType,
        qty: int,
        price: Decimal | None = None,
        reference: PegReference | None = None,
    ) -> Order:
        # O número só é consumido depois da validação: entrada inválida não abre buraco nos ids.
        seq = self._sequence.peek()
        order = Order(make_order_id(seq), seq, side, order_type, qty, price, reference)
        self._sequence.next()
        return order

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
                self._pegs.pop(passive.id, None)
            if trades and trades[-1].price == passive.price:
                last = trades[-1]
                trades[-1] = Trade(last.price, last.qty + fill, last.aggressor_id)
            else:
                trades.append(Trade(passive.price, fill, order.id))
        return trades

    def _reprice_pegs(self) -> None:
        """Realinha cada pegged ao melhor preço não-pegged da sua referência.

        Roda ao fim de cada operação, nunca no meio de um matching. Mantém o `seq` original:
        reposicionar automaticamente não é uma alteração da ordem, então não perde prioridade.
        """
        for peg in self._pegs.values():
            target = self.book.best_anchor_price(peg.reference.book_side)
            if peg.price == target:
                continue
            if peg.price is not None:
                self.book.remove(peg.id)
            peg.price = target
            if target is not None:
                self.book.add(peg)

    @staticmethod
    def _crosses(order: Order, passive: Order) -> bool:
        if order.side is Side.BUY:
            return order.price >= passive.price
        return order.price <= passive.price