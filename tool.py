from typing import Annotated
from langchain_core.tools import tool

from store import Store

def make_tools(actor: str, store: Store, input_tokens_limit: int, output_tokens_limit: int):
    @tool
    def post_chat(content: Annotated[str, "The content we want to send to the chat"]):
        """Post new messages into chat"""
        store.post_chat(actor, content)
    @tool
    def check_balance() -> str:
        """Return remaining output tokens and remaining input tokens"""
        balance = store.check_balance(input_tokens_limit, output_tokens_limit)
        return f"remaining output tokens are {balance["remaining_output_tokens"]}, remaining input tokens are {balance["remaining_input_tokens"]}"
    return [post_chat, check_balance]    
