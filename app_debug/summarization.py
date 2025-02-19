import logging
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = PromptTemplate(
    input_variables=["chunk_text"],
    template="""
You are an expert at summarizing text. Summarize the following chunk:

{chunk_text}

Return a concise summary highlighting only essential details.
"""
)

def create_summarization_chain(openai_api_key: str):
    """Builds a chain that summarizes a single text chunk using composition."""
    llm = ChatOpenAI(
        model_name="gpt-3.5-turbo",  # or "gpt-4" if preferred
        temperature=0.0,
        openai_api_key=openai_api_key
    )
    # Compose the chain by piping the prompt to the LLM
    return SUMMARY_PROMPT | llm

async def hierarchical_summarize(
    text_list,
    summarization_chain,
    max_batch_chars: int = 3000,
    pass_limit: int = 5
) -> str:
    """
    Summarize a list of text chunks in multiple passes if necessary.
    """
    current_list = text_list
    pass_count = 0

    while len(current_list) > 1 and pass_count < pass_limit:
        pass_count += 1
        logger.debug(f"[hierarchical_summarize] Pass #{pass_count}, input items: {len(current_list)}")

        batch_summaries = []
        buffer = []
        buffer_size = 0

        for chunk in current_list:
            chunk_len = len(chunk)
            if buffer and (buffer_size + chunk_len > max_batch_chars):
                buffer_text = "\n\n".join(buffer)
                result_message = await summarization_chain.ainvoke({"chunk_text": buffer_text})
                batch_summaries.append(result_message.content.strip())
                buffer = [chunk]
                buffer_size = chunk_len
            else:
                buffer.append(chunk)
                buffer_size += chunk_len

        # leftover buffer
        if buffer:
            buffer_text = "\n\n".join(buffer)
            result_message = await summarization_chain.ainvoke({"chunk_text": buffer_text})
            batch_summaries.append(result_message.content.strip())

        logger.debug(f"[hierarchical_summarize] Pass #{pass_count} => partial summaries: {len(batch_summaries)}")
        current_list = batch_summaries

    if len(current_list) == 1:
        return current_list[0]
    else:
        # pass limit reached but still multiple partial summaries => just join them
        return "\n\n".join(current_list)
