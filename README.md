---
title: 睿购智选 Agent
emoji: "📱"
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.40.0
app_file: app.py
pinned: false
---

# 睿购智选：Coze + Streamlit 免登录前端

Streamlit 作为服务端代理，用户的浏览器只访问 Streamlit，不直接访问 Coze，也不需要登录 Coze。

## 前置条件

1. Coze Agent 已发布到 **Agent As API** 渠道，发布状态必须显示成功。
2. 创建新的 PAT，至少具备 `chat` 权限。
3. 不要再使用已经在聊天或公开网页中暴露过的 Token。

## 本地运行

```powershell
cd C:\Users\lin\Documents\Codex\2026-10-29\c\streamlit_coze
python -m pip install -r requirements.txt
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
```

编辑 `.streamlit\secrets.toml`，填写真实 Token，然后运行：

```powershell
streamlit run app.py
```

浏览器打开终端给出的 `http://localhost:8501`。

首次启动如果出现 Welcome to Streamlit 和 Email 提示，直接留空按回车即可。项目已配置关闭使用统计提示。

首页会显示 5 个预设问题。点击按钮会自动发送。可在 `.streamlit/secrets.toml` 中通过 `PRESET_QUESTIONS` 自定义，每行一个问题。

修改 Token 后必须完整停止并重启 Streamlit。只点击页面上的 Rerun 可能仍在使用旧 Token。应用会优先读取脚本同目录下的 `.streamlit/secrets.toml`，不依赖终端当前目录。

也可以使用环境变量：

```powershell
$env:COZE_API_TOKEN = "pat_新的真实Token"
$env:COZE_BOT_ID = "7696073403866562560"
streamlit run app.py
```

## 部署到 Streamlit Community Cloud

1. 将整个 `streamlit_coze` 目录上传到 GitHub 私有仓库。
2. 在 Streamlit Community Cloud 创建应用，入口选择 `app.py`。
3. 在应用设置的 Secrets 中填写：

```toml
COZE_API_TOKEN = "pat_新的真实Token"
COZE_BOT_ID = "7696073403866562560"
COZE_API_BASE = "https://api.coze.cn"
```

4. 部署完成后，用户打开 Streamlit 提供的公开 URL 即可使用，无需登录 Coze。

不要把 `.streamlit/secrets.toml` 上传到 GitHub。

项目兼容 Python 3.9 及以上。Streamlit Cloud 如果使用 Python 3.10 或更早版本，会自动安装 `tomli`。

## 不经过 GitHub 的容器部署

项目包含 `Dockerfile`，可部署到能上传源码或 Docker 镜像的平台。平台环境变量填写：

```text
COZE_API_TOKEN=pat_新的真实Token
COZE_BOT_ID=7696073403866562560
COZE_API_BASE=https://api.coze.cn
```

容器监听端口为 `8501`。Docker 镜像不会包含 `.streamlit/secrets.toml`。

## 不登录 GitHub 的长期部署：Hugging Face Spaces

1. 登录 Hugging Face，进入 Spaces，选择 `Create new Space`。
2. SDK 选择 `Streamlit`。
3. 上传 `app.py`、`requirements.txt`、`README.md` 和 `.streamlit/config.toml`。
4. 不要上传 `.streamlit/secrets.toml`。
5. 在 Space 的 `Settings → Variables and secrets` 中新建 Secret：

```text
Name: COZE_API_TOKEN
Value: pat_你的真实Token
```

6. 可选地添加普通变量：

```text
COZE_BOT_ID = 7696073403866562560
COZE_API_BASE = https://api.coze.cn
```

7. Space 启动后，将 Space 页面链接分享给其他人。

公开 Space 默认可以通过网页访问，不需要 GitHub。

## 当前接口

- 发起并接收流式对话：`POST https://api.coze.cn/v3/chat`
- 读取消息兼容接口：`GET https://api.coze.cn/v3/chat/message/list`

应用会保存本次 Streamlit 会话中的 `conversation_id`，支持多轮对话。

## 常见错误

### 4015

```text
The bot has not been published to the channel Agent As API
```

处理：在 Coze 发布页勾选 `Agent As API`，填写版本号并发布，等待审核成功。

### 4101

```text
Your token does not have permission
```

处理：重新创建 PAT，确认包含 `chat` 权限，并确认 Token 所属空间能够访问该 Agent。

### 4100

如果发起对话成功、只有查询对话状态时报 `authentication is invalid`，通常是 Token 缺少 `getChat` 权限。应用已改为直接读取流式回答，不再调用该轮询接口。修改代码后需要完整重启 Streamlit。

### 4016

同一会话已有进行中的对话。等待当前回复完成后再发起下一条。
