Refactoring the provided script to make it more dynamic and extensible using OpenAI's @tool decorator involves consolidating and streamlining function registration into the agent. Here's how we can refactor the functionality:

Key Changes:
Dynamic Tool Registration: Use the @tool decorator to dynamically register all functions as tools for the agent.
Centralized Registration: Maintain a single registry (TOOL_REGISTRY) where all tools are automatically registered using the decorator.
Eliminate Manual Mapping: No need to explicitly define function_map or tools arrays manually; the system automatically discovers and registers all available tools.
Refactored Script
Import and Initialization
python
Copy code
from pydantic_ai import Agent
from openai import tool
from typing import Callable, List
import os
import logging

# Tool registry for dynamic registration
TOOL_REGISTRY: List[Callable] = []

# Initialize the agent
agent = Agent(
    model="openai:gpt-4o",
    system_prompt="You are an intelligent assistant capable of performing various tasks dynamically.",
)
Dynamic Tool Registration with Decorator
Define the Custom @register_tool Decorator
This decorator adds functions to the TOOL_REGISTRY and registers them with the agent dynamically.

python
Copy code
def register_tool(func: Callable):
    """Decorator to register a tool dynamically."""
    tool(func)  # Use OpenAI's tool decorator
    TOOL_REGISTRY.append(func)
    return func
Example: Refactoring Functions
Apply the @register_tool decorator to each function to automatically register it.

python
Copy code
from datetime import datetime
import random

@register_tool
async def get_current_time() -> dict:
    """Returns the current time."""
    return {"current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

@register_tool
async def get_random_number() -> dict:
    """Returns a random number between 1 and 100."""
    return {"random_number": random.randint(1, 100)}

@register_tool
async def reset_active_memory(force_delete: bool = False) -> dict:
    """Resets the active memory."""
    if not force_delete:
        return {
            "status": "confirmation_required",
            "message": "Are you sure you want to reset the active memory? Reply with 'force delete' to confirm.",
        }
    # Logic to reset memory
    return {"status": "success", "message": "Active memory has been reset."}

@register_tool
async def open_browser(prompt: str) -> dict:
    """Opens a browser tab with a URL based on the user's prompt."""
    # Browser logic...
    return {"status": "success", "url": "example.com"}
Repeat this process for all functions in the script, replacing @timeit_decorator with @register_tool.

Auto-Register All Tools
At runtime, dynamically register all tools from the TOOL_REGISTRY.

python
Copy code
# Register tools dynamically at runtime
for tool_func in TOOL_REGISTRY:
    agent.tool(tool_func)
Simplified Execution
Once tools are registered dynamically, you can invoke them directly from the agent, eliminating the need for a function_map.

python
Copy code
async def execute_tool(name: str, **kwargs):
    """Executes a registered tool by its name."""
    if name in {tool.__name__ for tool in TOOL_REGISTRY}:
        result = await agent.run_sync(f"Call the tool: {name}", **kwargs)
        return result.data
    else:
        return {"error": f"Tool '{name}' not found."}
Benefits of Refactoring
Dynamic Extensibility: Adding new tools only requires defining a function with the @register_tool decorator.
Reduced Boilerplate: Eliminates manual function mapping and tool list definitions.
Centralized Management: All tools are managed in a single TOOL_REGISTRY, simplifying modifications.
Improved Readability: Code is cleaner and avoids redundancy.
