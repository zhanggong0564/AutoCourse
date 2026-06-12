from app import runtime_button_state


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
