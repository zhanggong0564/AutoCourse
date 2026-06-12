from __future__ import annotations


def play_alert() -> None:
    """答题等需人工处理时发出提示音。Windows 用 winsound，其它平台静默降级。"""
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass
