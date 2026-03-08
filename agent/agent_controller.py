import logging
import re
import asyncio
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from agent.tools import (
    get_current_time,
    schedule_task_interval, 
    schedule_task_cron, 
    list_active_jobs, 
    remove_scheduled_job
)

logger = logging.getLogger(__name__)

class AgentController:
    def __init__(self, base_url: str, model: str):
        self.llm = ChatOllama(base_url=base_url, model=model, timeout=60)
        self.tools = {
            "get_current_time": get_current_time,
            "schedule_task_interval": schedule_task_interval,
            "schedule_task_cron": schedule_task_cron,
            "list_active_jobs": list_active_jobs,
            "remove_scheduled_job": remove_scheduled_job
        }
        
        # Stricter prompt to ensure tool use
        self.prompt = PromptTemplate.from_template("""You are a personal assistant.
You MUST use a tool if the user's request matches one of the tools below.

Tools available:
- get_current_time: Returns current time. No input needed.
- schedule_task_interval: Schedules a repeating task. Input: 'Task Name, seconds'. e.g. 'Coffee, 300'
- schedule_task_cron: Schedules a task via cron. Input: 'Name, cron'. e.g. 'Meeting, 0 14 * * 1'
- list_active_jobs: Lists ALL currently active tasks. No input needed. USE THIS if user asks 'what are my tasks' or 'list jobs'.
- remove_scheduled_job: Removes a task. Input: 'Job ID'. e.g. 'Coffee'

To use a tool, respond ONLY in this format:
ACTION: <tool_name>
INPUT: <tool_input>

If no tool fits, answer the question normally.

Question: {input}
Response:""")

    async def process_message(self, message: str, chat_id: int = None) -> str:
        """Processes a message and routes it to tools with user context."""
        try:
            logger.info(f"Agent processing (Chat {chat_id}): {message}")
            
            # Format and run the LLM
            formatted_prompt = self.prompt.format(input=message)
            response = await self.llm.ainvoke(formatted_prompt)
            content = response.content.strip()
            
            # Pattern matching for tool calls
            action_match = re.search(r"ACTION:\s*(\w+)", content, re.IGNORECASE)
            input_match = re.search(r"INPUT:\s*(.*)", content, re.IGNORECASE)
            
            if action_match:
                tool_name = action_match.group(1).lower().strip()
                tool_input = input_match.group(1).strip() if input_match else ""
                
                if tool_name in self.tools:
                    tool = self.tools[tool_name]
                    logger.info(f"Routing to tool {tool_name} for chat {chat_id} with input: {tool_input}")
                    # Call _run directly to ensure chat_id is passed (LangChain's run() strips unknown kwargs)
                    if tool_name in ["schedule_task_interval", "schedule_task_cron"]:
                        tool_result = await asyncio.to_thread(tool._run, tool_input, chat_id=chat_id)
                    else:
                        tool_result = await asyncio.to_thread(tool._run, tool_input)
                        
                    return tool_result
            
            return content
            
        except Exception as e:
            logger.error(f"Error in agent processing: {e}")
            return f"Agent Error: {str(e)}"
