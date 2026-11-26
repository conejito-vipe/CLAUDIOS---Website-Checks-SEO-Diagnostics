"""Fortschrittsbeobachter für stille Downloads."""
from claudios.components.dlwatch import SizeWatcher, folder_bytes, progress_fraction


def test_fraction_is_monotone_and_below_one():
    values = [progress_fraction(size, 1000) for size in (0, 100, 1000, 10_000, 10**12)]
    assert values[0] == 0.0
    assert values == sorted(values)
    assert values[-1] < 1.0


def test_folder_bytes_counts_files(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.bin").write_bytes(b"1" * 100)
    (tmp_path / "y.bin").write_bytes(b"1" * 50)
    assert folder_bytes(tmp_path) == 150
    assert folder_bytes(tmp_path / "gibt-es-nicht") == 0


def test_tick_reports_growth_since_start(tmp_path):
    (tmp_path / "old.bin").write_bytes(b"1" * 5000)  # vorhandene Dateien zählen nicht
    seen = []
    watcher = SizeWatcher([tmp_path], 1000, lambda done, total: seen.append((done, total)), base=50, span=45,
                          interval=60)
    with watcher:
        assert watcher.tick() == 50
        (tmp_path / "new.bin").write_bytes(b"1" * 1000)
        later = watcher.tick()
    assert 50 < later < 95
    assert seen[-1] == (later, 100)


def test_report_errors_do_not_break_the_watcher(tmp_path):
    def broken(*_):
        raise RuntimeError("x")

    with SizeWatcher([tmp_path], 1000, broken, base=0, span=100, interval=60) as watcher:
        first = watcher.tick()  # der Melder wirft, der Wächter rechnet trotzdem weiter
        (tmp_path / "new.bin").write_bytes(b"x" * 500)
        second = watcher.tick()
    assert first == 0 and 0 < second <= 100
