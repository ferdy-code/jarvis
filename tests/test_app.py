import pytest

from jarvis.app import is_yes


@pytest.mark.parametrize("answer", ["y", "yes", "Yes.", " ya ", "iya", "YES!"])
def test_clear_agreement_counts_as_yes(answer):
    assert is_yes(answer)


@pytest.mark.parametrize("answer", ["", "n", "no", "tidak", "yes but wait", "maybe"])
def test_anything_else_counts_as_no(answer):
    assert not is_yes(answer)
