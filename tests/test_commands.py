import pytest

from matching_engine.commands import HELP_LINES, CommandProcessor

EMPTY_BOOK = [
    "Ordens de Compra".ljust(19) + " | Ordens de Venda",
    "-" * 20 + "|" + "-" * 17,
]


@pytest.fixture
def cli():
    return CommandProcessor()


def test_limit_prints_the_created_order(cli):
    assert cli.execute("limit buy 10 100") == ["Order created: buy 100 @ 10 identificador_1"]


def test_limit_price_is_printed_without_trailing_zeros(cli):
    assert cli.execute("limit sell 10.50 5") == ["Order created: sell 5 @ 10.5 identificador_1"]


def test_limit_that_crosses_prints_the_order_then_the_trades(cli):
    cli.execute("limit sell 20 100")
    assert cli.execute("limit buy 21 150") == [
        "Order created: buy 150 @ 21 identificador_2",
        "Trade, price: 20, qty: 100",
    ]


def test_market_prints_only_the_trades(cli):
    cli.execute("limit sell 20 100")
    assert cli.execute("market buy 60") == ["Trade, price: 20, qty: 60"]


def test_market_without_liquidity_prints_nothing(cli):
    assert cli.execute("market buy 100") == []


def test_commands_are_case_insensitive_and_ignore_extra_spaces(cli):
    assert cli.execute("  LIMIT   Buy  10   100  ") == [
        "Order created: buy 100 @ 10 identificador_1"
    ]


@pytest.mark.parametrize("line", ["", "   ", "\t"])
def test_blank_line_is_ignored(cli, line):
    assert cli.execute(line) == []


def test_peg_prints_the_created_order_with_its_reference(cli):
    assert cli.execute("peg bid buy 150") == ["Order created: buy 150 @ peg bid identificador_1"]
    assert cli.execute("peg offer sell 80") == [
        "Order created: sell 80 @ peg offer identificador_2"
    ]


def test_peg_on_the_opposite_side_is_an_error(cli):
    assert cli.execute("peg bid sell 100") == ["Error: peg to the bid must be a buy order"]
    assert cli.execute("peg offer buy 100") == ["Error: peg to the offer must be a sell order"]


def test_cancel_prints_confirmation_and_removes_the_order(cli):
    cli.execute("limit buy 10 100")
    assert cli.execute("cancel order identificador_1") == ["Order cancelled"]
    assert cli.execute("print book") == EMPTY_BOOK


def test_cancel_unknown_order_is_an_error(cli):
    assert cli.execute("cancel order identificador_99") == [
        "Error: order not found: identificador_99"
    ]


def test_modify_price(cli):
    cli.execute("limit buy 10 200")
    cli.execute("limit buy 9.99 100")
    assert cli.execute("modify order identificador_1 price 9.98") == ["Order modified"]
    assert cli.execute("print book")[2:] == [
        "100 @ 9.99".ljust(19) + " |",
        "200 @ 9.98".ljust(19) + " |",
    ]


def test_modify_quantity_only_keeps_the_price(cli):
    cli.execute("limit buy 10 200")
    assert cli.execute("modify order identificador_1 qty 50") == ["Order modified"]
    assert cli.execute("print book")[2:] == ["50 @ 10".ljust(19) + " |"]


def test_modify_price_and_quantity_in_any_order(cli):
    cli.execute("limit buy 10 200")
    assert cli.execute("modify order identificador_1 qty 50 price 9") == ["Order modified"]
    assert cli.execute("print book")[2:] == ["50 @ 9".ljust(19) + " |"]


def test_modify_that_crosses_prints_the_trades(cli):
    cli.execute("limit sell 11 100")
    cli.execute("limit buy 10 100")
    assert cli.execute("modify order identificador_2 price 11") == [
        "Order modified",
        "Trade, price: 11, qty: 100",
    ]


def test_modify_unknown_order_is_an_error(cli):
    assert cli.execute("modify order identificador_9 qty 5") == [
        "Error: order not found: identificador_9"
    ]


def test_modify_pegged_quantity_is_allowed_but_not_its_price(cli):
    cli.execute("limit buy 10 100")
    cli.execute("peg bid buy 50")
    assert cli.execute("modify order identificador_2 qty 20") == ["Order modified"]
    assert cli.execute("modify order identificador_2 price 9") == [
        "Error: a pegged order has no price of its own; only its qty can be modified"
    ]


def test_print_book_renders_both_sides(cli):
    cli.execute("limit buy 10 200")
    cli.execute("limit sell 10.5 100")
    assert cli.execute("print book") == [
        *EMPTY_BOOK,
        "200 @ 10".ljust(19) + " | 100 @ 10.5",
    ]


def test_help_lists_every_command(cli):
    assert cli.execute("help") == list(HELP_LINES)


@pytest.mark.parametrize(
    "line",
    [
        "foo",
        "limit",
        "limit buy 10",
        "limit buy 10 100 5",
        "market buy",
        "market 100",
        "peg bid",
        "peg bid buy",
        "peg mid buy 100",
        "cancel",
        "cancel identificador_1",
        "cancel order",
        "cancel order identificador_1 extra",
        "modify",
        "modify order",
        "modify order identificador_1",
        "modify order identificador_1 price",
        "modify order identificador_1 price 9 price 8",
        "modify order identificador_1 color 9",
        "print",
        "print orders",
    ],
)
def test_malformed_commands_are_errors(cli, line):
    output = cli.execute(line)
    assert len(output) == 1
    assert output[0].startswith("Error: ")


@pytest.mark.parametrize(
    "line",
    [
        "limit hold 10 100",
        "limit buy abc 100",
        "limit buy 10 abc",
        "limit buy 10 1.5",
        "limit buy -10 100",
        "limit buy 10 -5",
        "limit buy +10 100",
        "limit buy 1e3 100",
        "limit buy nan 100",
        "limit buy inf 100",
        "limit buy 10,5 100",
        "limit buy .5 100",
        "limit buy 0 100",
        "limit buy 10 0",
        "limit buy 10 ٣",
        f"limit buy 10 {'9' * 5000}",
        "market buy 0",
        "peg bid buy 0",
    ],
)
def test_invalid_values_are_errors_and_leave_the_engine_untouched(cli, line):
    output = cli.execute(line)
    assert len(output) == 1
    assert output[0].startswith("Error: ")
    assert cli.execute("print book") == EMPTY_BOOK
    assert cli.execute("limit buy 10 100") == ["Order created: buy 100 @ 10 identificador_1"]


def test_error_messages_are_specific(cli):
    assert cli.execute("limit") == ["Error: usage: limit <buy|sell> <price> <qty>"]
    assert cli.execute("limit hold 10 100") == ["Error: invalid side 'hold' (use buy or sell)"]
    assert cli.execute("limit buy 10 1.5") == [
        "Error: invalid quantity '1.5' (use a positive integer)"
    ]
    assert cli.execute("foo") == ["Error: unknown command 'foo' (type 'help')"]