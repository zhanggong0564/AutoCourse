from app import log_toggle_text, runtime_button_state, status_presentation


def test_runtime_state_when_missing():
    assert runtime_button_state(False, False) == (
        "disabled",
        "normal",
        "需要安装浏览器组件",
    )


def test_runtime_state_while_installing():
    assert runtime_button_state(False, True) == (
        "disabled",
        "disabled",
        "正在安装浏览器组件",
    )


def test_runtime_state_when_installed():
    assert runtime_button_state(True, False) == ("normal", "disabled", "就绪")


def test_status_presentation_for_ready_state():
    assert status_presentation("就绪") == ("success", "● 就绪")


def test_status_presentation_for_manual_action():
    assert status_presentation("等待答题") == ("danger", "● 等待答题")


def test_status_presentation_for_processing_and_failure():
    assert status_presentation("正在停止") == ("info", "● 正在停止")
    assert status_presentation("运行失败") == ("danger", "● 运行失败")


def test_log_toggle_text_matches_visibility():
    assert log_toggle_text(False) == "显示详细日志 ▼"
    assert log_toggle_text(True) == "隐藏详细日志 ▲"
