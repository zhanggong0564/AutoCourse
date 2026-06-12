import page_actions
import runtime_installer
from assistant import Assistant


class FakePage:
    def __init__(self):
        self.waits = []

    def wait_for_timeout(self, milliseconds):
        self.waits.append(milliseconds)


def test_find_course_waits_for_async_list_data(monkeypatch):
    target = object()
    results = iter([None, None, target])
    monkeypatch.setattr(
        page_actions,
        "find_unwatched_course",
        lambda page, config, attempted=None: next(results),
    )
    assistant = Assistant.__new__(Assistant)
    assistant.config = {}
    page = FakePage()

    result = assistant._find_course_with_wait(page, attempts=3, delay_ms=500)

    assert result is target
    assert page.waits == [500, 500]


def test_assistant_configures_shared_browser_runtime(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        runtime_installer,
        "configure_browser_path",
        lambda root: calls.append(root) or root / "runtime" / "ms-playwright",
    )

    Assistant(tmp_path, lambda message: None, lambda status: None)

    assert calls == [tmp_path]
