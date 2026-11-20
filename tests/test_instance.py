"""Schutz gegen den Doppelstart."""
from claudios.ui.instance import acquire


def test_a_second_instance_is_refused_until_the_first_one_lets_go(tmp_path):
    path = tmp_path / "claudios.lock"
    first = acquire(path)
    assert first is not None
    assert acquire(path) is None
    first.unlock()
    again = acquire(path)
    assert again is not None
    again.unlock()
