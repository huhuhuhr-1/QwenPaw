import os

from openai import OpenAI

from app.utils.text import sanitize_polish_text


DEFAULT_SYSTEM_PROMPT = """你是一位专业的文字编辑，擅长将语音转写稿转换为可读文本。

处理要求：
1. 断句：在语义完整处添加标点
2. 纠错：修正语音转写的常见错误（同音字、错字）
3. 口语过滤：删除无意义的重复和语气词
4. 保留：保留核心论述和说话人的个人风格

直接输出精修后的正文，不要添加解释、格式标记或思考过程标签（如 redacted_thinking 块）。"""


class PolishService:
    def __init__(self):
        self.client: OpenAI | None = None

    def init_client(self):
        from app.config import settings
        api_key = settings.minimax_api_key or os.environ.get("MINIMAX_API_KEY", "")
        if api_key:
            self.client = OpenAI(api_key=api_key, base_url="https://api.minimax.chat/v1")

    def polish(self, text: str, custom_prompt: str | None = None) -> str:
        if not self.client:
            raise RuntimeError("MINIMAX_API_KEY not configured")

        system_prompt = custom_prompt or DEFAULT_SYSTEM_PROMPT
        clean_input = sanitize_polish_text(text)

        response = self.client.chat.completions.create(
            model="MiniMax-M2.7-highspeed",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": clean_input},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise RuntimeError("MiniMax returned empty response")

        return sanitize_polish_text(content)


polish_service = PolishService()
