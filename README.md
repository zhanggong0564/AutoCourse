# 自动看课助手

带图形界面的 Windows 本机工具：打开浏览器、由你手动登录一次，之后自动查找并播放未学习的培训课程、处理挂机确认弹窗、自动翻到下一节。遇到答题会暂停并提醒，由你手动作答。

## 安装

项目默认使用已配置好的 Miniconda `base` 环境。在 Miniconda Prompt 或已初始化 Conda 的 PowerShell 中运行：

```powershell
conda activate base
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## 使用

1. 激活 Miniconda `base` 环境后运行 `python app.py`。
2. 点击“打开并开始”，首次使用时在弹出的浏览器中手动登录。
3. 保持浏览器打开，程序会自动查找并播放未完成课程。
4. 出现答题时，界面会显示红色横幅并响提示音；手动作答后程序会自动继续。
5. 点击“停止”可结束任务并关闭自动化浏览器。

## 配置

编辑 `config.json` 可调整：

- `course_keywords` / `completed_keywords`：未完成和已完成状态文案。
- `idle_popup_keywords`：挂机弹窗确认按钮文案。
- `quiz_keywords`：答题页面判定文案。
- `poll_seconds`：页面轮询间隔。
- `stuck_minutes`：进度长时间不变后刷新页面的等待分钟数。
- `debug`：设为 `true` 时记录候选元素并导出当前页面 HTML，便于校准选择器。

登录会话保存在 `.browser-profile`。请勿分享该目录；登录异常时可关闭程序、删除该目录后重新登录。

## 边界

本工具不替你答题，不绕过验证码、人脸识别或网站风控，不加速视频、不伪造学习进度，也不保存密码。请遵守平台规则并实际参与课程学习。
