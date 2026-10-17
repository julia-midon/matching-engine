from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class InvalidOrderError(ValueError):
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


@dataclass
class Order:
    id: str
    seq: int  # prioridade temporal; muda quando a ordem perde prioridade
    side: Side
    type: OrderType
    qty: int  # quantidade restante
    price: Decimal | None = None

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
        # PEGGED: o preço é derivado do book; as regras entram no Dia 5.


@dataclass(frozen=True)
class Trade:
    price: Decimal
    qty: int
    aggressor_id: str
    passive_id: str