class SequenceGenerator:
    """Contador monotônico usado como prioridade temporal (não depende do relógio)."""

    def __init__(self, start: int = 1) -> None:
        self._next = start

    def next(self) -> int:
        value = self._next
        self._next += 1
        return value


def make_order_id(seq: int) -> str:
    return f"identificador_{seq}"