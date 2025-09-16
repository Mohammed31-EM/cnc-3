# main_app/services/deepseek.py
from django.conf import settings
from openai import OpenAI

_client = None

def get_client():
    global _client
    if _client is None:
        if not settings.DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")
        _client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
    return _client

def chat(messages, model=None, **kwargs) -> str:
    model = model or settings.DEEPSEEK_MODEL
    resp = get_client().chat.completions.create(
        model=model,
        messages=messages,
        stream=False,
        **kwargs,
    )
    return resp.choices[0].message.content