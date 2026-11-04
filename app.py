import json
import os
import uuid
from pathlib import Path
from typing import Any

import requests
import streamlit as st

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and earlier on Streamlit Cloud
    import tomli as tomllib


DEFAULT_BOT_ID = "7696073403866562560"
DEFAULT_API_BASE = "https://api.coze.cn"
DEFAULT_PRESET_QUESTIONS = [
    "2000元左右，给妈妈买，要续航好",
    "5000元旗舰，拍照好的有什么推荐",
    "荣耀 X70 有什么优惠折扣",
    "我的订单到哪了",
    "碎屏险怎么买？保修多久",
]


def setting(name: str, default: str = "") -> str:
    """Read from Streamlit secrets first, then environment variables."""
    try:
        value = st.secrets.get(name, None)
    except Exception:
        value = None
    if not value:
        secret_file = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
        if secret_file.exists():
            try:
                file_secrets = tomllib.loads(secret_file.read_text(encoding="utf-8"))
                value = file_secrets.get(name, None)
            except Exception:
                value = None
    return str(value or os.getenv(name, default) or "").strip()


COZE_API_TOKEN = setting("COZE_API_TOKEN")
COZE_BOT_ID = setting("COZE_BOT_ID", DEFAULT_BOT_ID)
COZE_API_BASE = setting("COZE_API_BASE", DEFAULT_API_BASE).rstrip("/")
preset_setting = setting("PRESET_QUESTIONS")
PRESET_QUESTIONS = [
    item.strip()
    for item in preset_setting.splitlines()
    if item.strip()
] or DEFAULT_PRESET_QUESTIONS


st.set_page_config(
    page_title="睿购智选 · 手机消费决策 Agent",
    page_icon="📱",
    layout="centered",
)


if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "你好，我是睿购智选。告诉我预算、用途、关注的机型，"
                "或者直接问价格、优惠和到手价。"
            ),
        }
    ]
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "user_id" not in st.session_state:
    st.session_state.user_id = f"streamlit_{uuid.uuid4().hex[:16]}"


def api_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {COZE_API_TOKEN}",
        "Content-Type": "application/json",
    }


def friendly_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return f"Coze 请求失败：HTTP {response.status_code}"

    code = payload.get("code")
    message = payload.get("msg") or payload.get("error_message") or "未知错误"
    if str(code) == "4015" or "not been published" in message:
        return (
            "智能体还没有发布到 Coze API 渠道。请到 Coze 的“发布”页面，"
            "选择“Agent As API / API 服务”并完成发布，审核通过后再试。"
        )
    if str(code) == "4101" or "permission" in message.lower():
        return (
            "当前 Coze Token 权限不足。请创建具备 chat 权限的新 PAT，"
            "并确认 Token 所属空间可以访问该智能体。"
        )
    if str(code) == "4016":
        return "上一条回复仍在处理中，请稍后重试。"
    return f"Coze 错误 {code}: {message}"


def list_messages(conversation_id: str, chat_id: str) -> list[dict[str, Any]]:
    response = requests.get(
        f"{COZE_API_BASE}/v3/chat/message/list",
        headers=api_headers(),
        params={
            "conversation_id": conversation_id,
            "chat_id": chat_id,
        },
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(friendly_error(response))
    payload = response.json()
    if payload.get("code") not in (None, 0):
        raise RuntimeError(friendly_error(response))
    return payload.get("data") or []


def answer_from_messages(messages: list[dict[str, Any]]) -> str:
    answers = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        if message.get("type") != "answer":
            continue
        content = message.get("content")
        if content:
            answers.append(str(content))
    return "\n\n".join(answers).strip() or "智能体没有返回文本内容。"


def ask_coze(question: str) -> str:
    body: dict[str, Any] = {
        "bot_id": COZE_BOT_ID,
        "user_id": st.session_state.user_id,
        "stream": True,
        "auto_save_history": True,
        "additional_messages": [
            {
                "role": "user",
                "type": "question",
                "content": question,
                "content_type": "text",
            }
        ],
    }
    if st.session_state.conversation_id:
        body["conversation_id"] = st.session_state.conversation_id

    response = requests.post(
        f"{COZE_API_BASE}/v3/chat",
        headers=api_headers(),
        json=body,
        timeout=(30, 180),
        stream=True,
    )
    if not response.ok:
        raise RuntimeError(friendly_error(response))

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = response.json()
        if payload.get("code") not in (None, 0):
            raise RuntimeError(friendly_error(response))

    event_name = ""
    answers: list[str] = []
    conversation_id = st.session_state.conversation_id
    chat_id = None
    failed_message = ""

    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.strip()
        if line.startswith("event:"):
            event_name = line.partition(":")[2].strip()
            continue
        if not line.startswith("data:"):
            continue
        data_text = line.partition(":")[2].strip()
        if not data_text or data_text == "[DONE]":
            continue
        try:
            event_data = json.loads(data_text)
        except json.JSONDecodeError:
            continue

        if event_name == "conversation.chat.created":
            conversation_id = str(
                event_data.get("conversation_id") or conversation_id or ""
            )
            chat_id = str(event_data.get("id") or chat_id or "")
            st.session_state.conversation_id = conversation_id or None
        elif event_name in {"conversation.chat.failed", "error"}:
            failed_message = (
                event_data.get("last_error", {}).get("msg")
                or event_data.get("msg")
                or "Coze 对话失败"
            )
        elif event_name == "conversation.message.completed":
            if (
                event_data.get("role") == "assistant"
                and event_data.get("type") == "answer"
            ):
                content = str(event_data.get("content") or "").strip()
                if content:
                    answers.append(content)

    response.close()

    if failed_message:
        raise RuntimeError(failed_message)
    if answers:
        return "\n\n".join(answers).strip()

    # 某些旧版本流式响应未携带最终 answer，使用消息列表兜底。
    if conversation_id and chat_id:
        messages = list_messages(conversation_id, chat_id)
        return answer_from_messages(messages)
    return "智能体没有返回文本内容。"


st.title("睿购智选 · 手机消费决策 Agent")
st.caption(
    "支持手机推荐、参数对比、真实口碑、优惠查询和到手价估算。"
    "演示价格与活动按 2026-10-25 口径计算。"
)

with st.sidebar:
    st.subheader("说明")
    st.write("浏览器不会接触 Coze Token；Token 仅保存在 Streamlit 服务端。")
    if COZE_API_TOKEN:
        st.success("Coze 鉴权已配置")
    else:
        st.error("未检测到 Coze Token")
    st.write("请先确认智能体已发布到 Coze API 渠道。")
    if st.button("新对话", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "已开始新对话。请告诉我想了解哪款手机。",
            }
        ]
        st.session_state.conversation_id = None
        st.session_state.user_id = f"streamlit_{uuid.uuid4().hex[:16]}"
        st.rerun()


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


if len(st.session_state.messages) == 1:
    st.markdown("#### 你可以这样问")
    for row_index in range(0, len(PRESET_QUESTIONS), 2):
        columns = st.columns(2)
        for column_index, preset in enumerate(
            PRESET_QUESTIONS[row_index : row_index + 2]
        ):
            with columns[column_index]:
                if st.button(
                    preset,
                    key=f"preset_question_{row_index}_{column_index}",
                    use_container_width=True,
                ):
                    st.session_state.pending_question = preset
                    st.rerun()


question = st.chat_input("例如：荣耀 X70 有什么优惠折扣？")
if not question:
    question = st.session_state.pop("pending_question", None)

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    if not COZE_API_TOKEN:
        answer = (
            "未配置 COZE_API_TOKEN。请在 Streamlit Secrets 或环境变量中配置 Token。"
        )
    elif not COZE_BOT_ID:
        answer = "未配置 COZE_BOT_ID。"
    else:
        try:
            with st.chat_message("assistant"):
                with st.spinner("AI 导购正在查询商品与优惠..."):
                    answer = ask_coze(question)
                    st.markdown(answer)
        except Exception as error:
            answer = f"请求失败：{error}"
            with st.chat_message("assistant"):
                st.error(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
