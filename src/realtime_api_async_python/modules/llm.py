
import os
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from typing import Type, TypeVar , Any, Optional
from async_lru import alru_cache



T = TypeVar('T', bound=BaseModel)


@alru_cache(maxsize=32)
async def get_agent(response_format: Optional[Type[T]]=None, llm_model: str = "gpt-4o-2024-08-06") -> Agent[Any, T]:
    model = OpenAIModel(llm_model, api_key=os.getenv("OPENAI_API_KEY"))
    if response_format is None:
        return Agent(model)
    else:
        return Agent(model, 
                         result_type=response_format)




async def structured_output_prompt(
    prompt: str, response_format: Type[T], llm_model: str = "gpt-4o-2024-08-06"
) -> T:
    """
    Parse the response from the OpenAI API using structured output.

    Args:
        prompt (str): The prompt to send to the OpenAI API.
        response_format (BaseModel): The Pydantic model representing the expected response format.

    Returns:
        BaseModel: The parsed response from the OpenAI API.
    """
    agent:Agent[Any,T] = await get_agent(response_format, llm_model)
    completion = await agent.run(
        prompt,
    )

    return completion.data


async def chat_prompt(prompt: str, llm_model: str) -> str:
    """
    Run a chat model based on the specified model name.

    Args:
        prompt (str): The prompt to send to the OpenAI API.
        model (str): The model ID to use for the API call.

    Returns:
        str: The assistant's response.
    """
    agent:Agent[Any,str] = await get_agent(llm_model)
    completion = await agent.run(
        prompt,
    )

    return completion.data


def parse_markdown_backticks(str) -> str:
    if "```" not in str:
        return str.strip()
    # Remove opening backticks and language identifier
    str = str.split("```", 1)[-1].split("\n", 1)[-1]
    # Remove closing backticks
    str = str.rsplit("```", 1)[0]
    # Remove any leading or trailing whitespace
    return str.strip()
