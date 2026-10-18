from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class InvalidOrderError(ValueError):
    pass


class OrderNotFoundError(LookupError):
    pass


class Side(Enum):
    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY


class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"
    PEGGED = "pegged"


class PegReference(Enum):
    """Melhor preço acompanhado por uma pegged order: o bid (compra) ou o offer (venda)."""

    BID = "bid"
    OFFER = "offer"

    @property
    def book_side(self) -> Side:
        """Lado do book onde fica o preço de referência."""
        return Side.BUY if self is PegReference.BID else Side.SELL


@dataclass
class Order:
    id: str
    seq: int  # prioridade temporal; muda quando a ordem perde prioridade
    side: Side
    type: OrderType
    qty: int  # quantidade restante
    price: Decimal | None = None  # em pegged, é derivado do book (None enquanto inativa)
    reference: PegReference | None = None  # apenas para pegged

    def __post_init__(self) -> None:
        if not isinstance(self.qty, int) or isinstance(self.qty, bool) or self.qty <= 0:
            raise InvalidOrderError("qty must be a positive integer")

        if self.price is not None:
            if not isinstance(self.price, Decimal):
                raise InvalidOrderError("price must be a Decimal, never float")
            if not self.price.is_finite() or self.price <= 0:
                raise InvalidOrderError("price must be a finite positive number")

        if self.type is OrderType.LIMIT and self.price is None:
            raise InvalidOrderError("limit order requires a price")
        if self.type is OrderType.MARKET and self.price is not None:
            raise InvalidOrderError("market order must not have a price")

        if self.type is OrderType.PEGGED:
            self._validate_peg()
        elif self.reference is not None:
            raise InvalidOrderError("only pegged orders have a peg reference")

    def _validate_peg(self) -> None:
        if self.reference is None:
            raise InvalidOrderError("pegged order requires a reference (bid or offer)")
        # Escopo: a pegged acompanha o próprio lado do book (peg to bid = compra,
        # peg to offer = venda). Assim, reprecificar nunca gera execução.
        expected_side = self.reference.book_side
        if expected_side is not self.side:
            raise InvalidOrderError(
                f"peg to the {self.reference.value} must be a {expected_side.value} order"
            )


@dataclass(frozen=True)
class Trade:
    """Execução agregada: um Trade por nível de preço consumido pela ordem agressora."""

    price: Decimal
    qty: int
    aggressor_id: str