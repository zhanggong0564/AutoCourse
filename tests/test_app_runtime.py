from app import (
    enable_dpi_awareness,
    log_toggle_text,
    runtime_button_state,
    scaled_size,
    status_presentation,
)


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


def test_scaled_size_scales_dimensions():
    assert scaled_size(780, 500, 1.5) == (1170, 750)


def test_scaled_size_never_shrinks_below_base():
    assert scaled_size(780, 500, 0.8) == (780, 500)


def test_scaled_size_caps_extreme_factor():
    assert scaled_size(100, 100, 10.0) == (300, 300)


def test_enable_dpi_awareness_does_not_raise():
    enable_dpi_awareness()
