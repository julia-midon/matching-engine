import io
import subprocess
import sys
from pathlib import Path

import pytest

from matching_engine.cli import BANNER, PROMPT, main, run

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
CREATE_THEN_CANCEL = "Order created: buy 100 @ 10 identificador_1\nOrder cancelled\n"

# Saídas esperadas, conferidas contra os exemplos do enunciado (PDF).
STATEMENT_OUTPUTS = {
    "statement_market.txt": """\
>>> limit buy 10 100
Order created: buy 100 @ 10 identificador_1
>>> limit sell 20 100
Order created: sell 100 @ 20 identificador_2
>>> limit sell 20 200
Order created: sell 200 @ 20 identificador_3
>>> market buy 150
Trade, price: 20, qty: 150
>>> market buy 200
Trade, price: 20, qty: 150
>>> market sell 200
Trade, price: 10, qty: 100
""",
    "statement_cancel.txt": """\
>>> limit buy 10 100
Order created: buy 100 @ 10 identificador_1
>>> cancel order identificador_1
Order cancelled
""",
    "statement_modify.txt": """\
>>> limit buy 10 200
Order created: buy 200 @ 10 identificador_1
>>> limit buy 9.99 100
Order created: buy 100 @ 9.99 identificador_2
>>> limit sell 10.5 100
Order created: sell 100 @ 10.5 identificador_3
>>> print book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
200 @ 10            | 100 @ 10.5
100 @ 9.99          |
>>> modify order identificador_1 price 9.98
Order modified
>>> print book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
100 @ 9.99          | 100 @ 10.5
200 @ 9.98          |
""",
    "statement_peg.txt": """\
>>> limit buy 10 200
Order created: buy 200 @ 10 identificador_1
>>> limit buy 9.99 100
Order created: buy 100 @ 9.99 identificador_2
>>> limit sell 10.5 100
Order created: sell 100 @ 10.5 identificador_3
>>> print book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
200 @ 10            | 100 @ 10.5
100 @ 9.99          |
>>> peg bid buy 150
Order created: buy 150 @ peg bid identificador_4
>>> print book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
200 @ 10            | 100 @ 10.5
150 @ 10            |
100 @ 9.99          |
>>> limit buy 10.1 300
Order created: buy 300 @ 10.1 identificador_5
>>> print book
Ordens de Compra    | Ordens de Venda
--------------------|-----------------
150 @ 10.1          | 100 @ 10.5
300 @ 10.1          |
200 @ 10            |
100 @ 9.99          |
""",
}


@pytest.mark.parametrize("name", STATEMENT_OUTPUTS)
def test_statement_examples_run_from_a_file(name, capsys):
    assert main([str(EXAMPLES / name), "--echo"]) == 0
    assert capsys.readouterr().out == STATEMENT_OUTPUTS[name]


def test_without_echo_only_the_outputs_are_printed(capsys):
    assert main([str(EXAMPLES / "statement_cancel.txt")]) == 0
    assert capsys.readouterr().out == CREATE_THEN_CANCEL


def test_module_entry_point_runs_the_examples():
    result = subprocess.run(
        [sys.executable, "-m", "matching_engine", str(EXAMPLES / "statement_cancel.txt")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == CREATE_THEN_CANCEL
    assert result.stderr == ""


def test_stdin_that_is_not_a_terminal_runs_without_prompt(monkeypatch, capsys):
    commands = "limit buy 10 100\ncancel order identificador_1\n"
    monkeypatch.setattr(sys, "stdin", io.StringIO(commands))
    assert main([]) == 0
    assert capsys.readouterr().out == CREATE_THEN_CANCEL


def test_missing_script_is_reported_on_stderr(tmp_path, capsys):
    missing = tmp_path / "nope.txt"
    assert main([str(missing)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"Error: cannot read '{missing}'")


def test_script_that_is_not_utf8_is_reported_on_stderr(tmp_path, capsys):
    script = tmp_path / "utf16.txt"
    script.write_text("limit buy 10 100\n", encoding="utf-16")
    assert main([str(script)]) == 1
    assert capsys.readouterr().err.startswith("Error: cannot read")


def test_script_saved_with_bom_is_accepted(tmp_path, capsys):
    script = tmp_path / "bom.txt"
    script.write_text("limit buy 10 100\n", encoding="utf-8-sig")
    assert main([str(script)]) == 0
    assert capsys.readouterr().out == "Order created: buy 100 @ 10 identificador_1\n"


def test_errors_in_a_script_do_not_stop_the_following_commands(tmp_path, capsys):
    script = tmp_path / "errors.txt"
    script.write_text("limit buy abc 100\nfoo\nlimit buy 10 100\n", encoding="utf-8")
    assert main([str(script)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Error: invalid price 'abc' (use a number such as 10 or 9.99)",
        "Error: unknown command 'foo' (type 'help')",
        "Order created: buy 100 @ 10 identificador_1",
    ]


def test_blank_lines_and_comments_are_skipped_even_with_echo():
    out = io.StringIO()
    run(io.StringIO("# comment\n\n   \nlimit buy 10 100\n"), out, echo=True)
    assert out.getvalue() == ">>> limit buy 10 100\nOrder created: buy 100 @ 10 identificador_1\n"


def test_exit_stops_reading_commands():
    out = io.StringIO()
    run(io.StringIO("limit buy 10 100\nEXIT\nlimit buy 11 100\n"), out)
    assert out.getvalue() == "Order created: buy 100 @ 10 identificador_1\n"


def test_interactive_session_shows_banner_and_prompts():
    out = io.StringIO()
    run(io.StringIO("limit buy 10 100\nexit\nlimit buy 11 100\n"), out, interactive=True)
    assert out.getvalue() == (
        f"{BANNER}\n{PROMPT}Order created: buy 100 @ 10 identificador_1\n{PROMPT}"
    )


def test_interactive_session_ends_cleanly_at_end_of_input():
    out = io.StringIO()
    run(io.StringIO("print book\n"), out, interactive=True)
    assert out.getvalue().endswith(f"{PROMPT}\n")