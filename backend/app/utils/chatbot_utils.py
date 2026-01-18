from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)

def pre_model_hook(state):
    """ Called each time Agent is invoked before sending to LLM.
    Used to truncate conversation history if it exceeds token limit"""
    trimmed_messages = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=2000,
        start_on="human",
        end_on=("human", "tool"),
    )
    return {"llm_input_messages": trimmed_messages}
