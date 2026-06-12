import page_logic


def test_contains_any_found():
    assert page_logic.contains_any("这门课未学习", ["未学习", "去学习"]) is True


def test_contains_any_not_found():
    assert page_logic.contains_any("已完成", ["未学习", "去学习"]) is False


def test_parse_progress_finds_percent_line():
    text = "课程名称\n学习进度 30%\n讲师介绍很长很长的一段文字" + "x" * 60
    assert page_logic.parse_progress(text) == "学习进度 30%"


def test_parse_progress_ignores_long_lines():
    text = "这是一段包含百分号 50% 的描述文字" + "很长" * 30
    assert page_logic.parse_progress(text) is None


def test_parse_progress_returns_none_without_percent():
    assert page_logic.parse_progress("课程名称\n讲师介绍") is None


def test_is_completed():
    assert page_logic.is_completed("状态：已完成", ["已完成", "100%"]) is True
    assert page_logic.is_completed("状态：未学习", ["已完成", "100%"]) is False


def test_is_quiz():
    assert page_logic.is_quiz("请完成本节单选题", ["单选题", "测验"]) is True
    assert page_logic.is_quiz("正在播放视频", ["单选题", "测验"]) is False


def test_is_quiz_ignores_course_navigation_and_hidden_dialog_labels():
    page_text = "章节 测验 人工智能课程 验证码答题 确定 课程播放进度 28%"
    keywords = ["答题", "测验", "试题", "提交答案", "单选题", "多选题"]

    assert page_logic.is_quiz(page_text, keywords) is False


def test_needs_human():
    assert page_logic.needs_human("请输入验证码", ["验证码", "人脸"]) is True
    assert page_logic.needs_human("正常播放中", ["验证码", "人脸"]) is False


def test_course_candidate_priority_rejects_exam_entry():
    priority = page_logic.course_candidate_priority(
        "/考试未完成",
        course_keywords=["未完成", "学习"],
        preferred_keywords=["视频", "播放", "课件", "学习"],
        excluded_keywords=["考试", "答题", "测验", "考核"],
    )

    assert priority is None


def test_course_candidate_priority_prefers_video_entry():
    video_priority = page_logic.course_candidate_priority(
        "视频学习未完成",
        course_keywords=["未完成", "学习"],
        preferred_keywords=["视频", "播放", "课件", "学习"],
        excluded_keywords=["考试", "答题", "测验", "考核"],
    )
    generic_priority = page_logic.course_candidate_priority(
        "课程未完成",
        course_keywords=["未完成", "学习"],
        preferred_keywords=["视频", "播放", "课件", "学习"],
        excluded_keywords=["考试", "答题", "测验", "考核"],
    )

    assert video_priority == 0
    assert generic_priority == 1
