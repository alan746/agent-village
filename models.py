import os
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek

MAX_TOKENS = 16_000
OPENROUTER_URL = "https://openrouter.ai/api/v1"
MODEL_IDS = {
    "claude": "claude-sonnet-5-5",
    "chatgpt": "gpt-6-luna",
    "deepseek": "deepseek-flash",
    "gemini": "google/gemini-3.8-flash",
}

class ChatOpenRouter(ChatOpenAI):
    def _create_chat_result(self, response, generation_info=None):
        result = super()._create_chat_result(response, generation_info)
        data = response if isinstance(response, dict) else response.model_dump()
        choices = data.get("choices") or []
        details = choices[0].get("message", {}).get("reasoning_details") if choices else None
        if details:
            result.generations[0].message.additional_kwargs["reasoning_details"] = details
        return result

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        messages = self._convert_input(input_).to_messages()
        if len(messages) == len(payload.get("messages", [])):
            for message, entry in zip(messages, payload["messages"]):
                details = message.additional_kwargs.get("reasoning_details") if message.type == "ai" else None
                if details:
                    entry["reasoning_details"] = details
        return payload

def make_models() -> dict:
    return {
        "claude": ChatAnthropic(
            model=MODEL_IDS["claude"],
            max_tokens=MAX_TOKENS,
            effort="medium",
            betas=["thinking-binding-controls-2026-08-01"],
            thinking={"type": "adaptive", "block_binding": {"prefix_mismatch_behavior": "drop_block"}},
            model_kwargs={"cache_control": {"type": "ephemeral"}},
        ),
        "chatgpt": ChatOpenAI(
            model=MODEL_IDS["chatgpt"],
            max_tokens=MAX_TOKENS,
            reasoning={"effort": "low"},
        ),
        "deepseek": ChatDeepSeek(
            model=MODEL_IDS["deepseek"],
            max_tokens=MAX_TOKENS,
            extra_body={"thinking": {"type": "disabled"}},
        ),
        "gemini": ChatOpenRouter(
            model=MODEL_IDS["gemini"],
            base_url=OPENROUTER_URL,
            api_key=os.environ["OPENROUTER_API_KEY"],
            max_tokens=MAX_TOKENS,
        ),
    }
