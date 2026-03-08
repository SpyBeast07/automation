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
        
        # Enhanced Prompt with diverse few-shot examples
        self.prompt = PromptTemplate.from_template("""You are a personal assistant.
You MUST use a tool if the user wants to schedule, list, or remove a task.

Available tools:
- get_current_time: Returns current time. No input needed.
- schedule_task_interval: Schedules a repeating task. Input: 'Task Name, seconds'. e.g. 'Coffee, 300'
- schedule_task_cron: Schedules a task via cron. Input: 'Name, cron'. e.g. 'Meeting, 0 14 * * 1'
- list_active_jobs: Lists all active tasks. No input needed.
- remove_scheduled_job: Removes a task. Input: 'Job ID'. e.g. 'Coffee'

Format for tool use:
ACTION: <tool_name>
INPUT: <tool_input>

### Examples of varied styles:
User: "Remind me to drink water every 10 minutes"
ACTION: schedule_task_interval
INPUT: Drink Water, 600

User: "Check the server status every hour"
ACTION: schedule_task_interval
INPUT: Server Status, 3600

User: "I want a daily alarm at 8 AM for Gym"
ACTION: schedule_task_cron
INPUT: Gym, 0 8 * * *

User: "What's currently scheduled?"
ACTION: list_active_jobs
INPUT: 

User: "Cancel the water reminder"
ACTION: remove_scheduled_job
INPUT: Drink Water

User: "Stop the job named Gym"
ACTION: remove_scheduled_job
INPUT: Gym

User: "Tell me the time"
ACTION: get_current_time
INPUT: 

If no tool fits (like a greeting), just answer normally.

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
                    
                    # Call _run directly and pass chat_id if supported
                    if tool_name in ["schedule_task_interval", "schedule_task_cron"]:
                        tool_result = await asyncio.to_thread(tool._run, tool_input, chat_id=chat_id)
                    else:
                        tool_result = await asyncio.to_thread(tool._run, tool_input)
                        
                    return tool_result
            
            return content
            
        except Exception as e:
            logger.error(f"Error in agent processing: {e}")
            return f"Agent Error: {str(e)}"
