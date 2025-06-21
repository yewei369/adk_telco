import os
import logging
import google.cloud.logging

from dotenv import load_dotenv

from google.adk import Agent
from google.adk.agents import SequentialAgent, LoopAgent, ParallelAgent
from google.adk.tools import google_search  # The Google Search tool
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.langchain_tool import LangchainTool  # import
#from google.adk.tools.crewai_tool import CrewaiTool
from google.genai import types

from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
#from crewai_tools import FileWriterTool

from .rag import query_rag_tool
from callback_logging import log_query_to_model, log_model_response

cloud_logging_client = google.cloud.logging.Client()
cloud_logging_client.setup_logging()
load_dotenv()
model_name = os.getenv("MODEL")
print(model_name)


# --- Tools ---

def append_to_state(tool_context: ToolContext, field: str, response: str) -> dict[str, str]:
    """Append new output to an existing state key.
    Args:
        field (str): a field name to append to
        response (str): a string to append to the field
    Returns:
        dict[str, str]: {"status": "success"}
    """
    existing_state = tool_context.state.get(field, [])
    tool_context.state[field] = existing_state + [response]
    logging.info(f"[Added to {field}] {response}")
    return {"status": "success"}

def fixed_diagnos(post_code: str):
    """ As per the guide, for the PoC, it returns a fixed result. You would expand this to actually query DownDetector.se or OSS.
    Args:
        post_code: given the post code by user where the internet issue takes place
    Returns:
        dict[str, str]: {"diag_result": diag_result}
    """

    if post_code == "250601": # Example postcode from documentation
        diag_result = "outage"
    else:
        diag_result = "device_issue"
    
    logging.info(f"diagnosis result: {diag_result}")
    return {"diag_result": diag_result}



# --- Agents ---

## 2: Search_agent
rag_agent = Agent(
    name="troubleshooting_rag_agent",
    model=model_name,
    description="Searches knowledge base and external sources for troubleshooting steps and provides fixes.",
    instruction="""

    INSTRUCTIONS:
    Based on diagnostic results and customer issue, always aim to provide actionable troubleshooting steps or escalate if no solution is found.

    - if {{diag_result??}} is 'device_issue', kindly ask the user for the device item name or number, and save it in the state key 'device'
    - then search in knowledge base for the troubleshooting steps related to the {{issue_type??}} and {{device??}}, using the tool 'query_rag_tool' with dialog history as 'query' to the tool. 
    - Based on the response of 'query_rag_tool', formulate an answer to the user
    - if no useful information found in knowledge base, use the tool 'google_search' to turn to public manual and information base for help
    """,
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    generate_content_config=types.GenerateContentConfig(temperature=0,),
    tools=[], #[append_to_state,query_rag_tool,google_search],
    sub_agents=[],
)

## 1: Diagnostic_agent
diagnostic_agent = Agent(
    name="diagnostic_agent",
    model=model_name,
    description="Performs automated network and device diagnostics, integrates with DownDetector.se and OSS.",
    instruction="""

    INSTRUCTIONS:
    Your goal is to detect if the issue happens in some special area that suffers from the outage based on provided {{post_code?}}.

    - use the tool 'fixed_diagnos' to determine the diagnos result, and use tool 'append_to_state' to store it in the state key 'diag_result'
    - if 'diag_result' is 'outage', then tell the customer elegantly and politely to wait until the ungoing maintenance is finished
    - if 'diag_result' is 'device_issue', tell the customer issue probably lies in the pyhisical device, and transfer to the 'troubleshooting_rag_agent'

    """,
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    generate_content_config=types.GenerateContentConfig(temperature=0,),
    tools=[append_to_state,fixed_diagnos],
    sub_agents=[rag_agent],
)



## 0: Root Agent for MVP
root_agent = Agent(
    name="greeter",
    model=model_name,
    description="The main AI assistant for diagnosing and resolving internet issues.",
    instruction="""
    INSTRUCTIONS:
    - Let the user know you will help them diagnose and resolve their internet issues. 
    - You can check for outages, help the customer troubleshoot, and even schedule a technician if needed.
    - Ask them for the potential internet problem, including your postcode, issue type (e.g., 'slow internet', 'no connection'),
      and device type (e.g., 'router', 'laptop').
    - When they respond, analyze the responses and 
        use the 'append_to_state' tool to store infomation of post code in the state key 'post_code', 
        use the 'append_to_state' tool to store infomation of the type of issue in the state key 'issue_type', 
        use the 'append_to_state' tool to store infomation of the type of device in the state key 'device_type'
    """,
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    generate_content_config=types.GenerateContentConfig(temperature=0,),
    tools=[append_to_state],
    sub_agents=[diagnostic_agent],
)