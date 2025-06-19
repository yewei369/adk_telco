import os
import logging
import google.cloud.logging

from dotenv import load_dotenv

from google.adk import Agent
from google.adk.agents import SequentialAgent, LoopAgent, ParallelAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.langchain_tool import LangchainTool  # import
#from google.adk.tools.crewai_tool import CrewaiTool
from google.genai import types

from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
#from crewai_tools import FileWriterTool

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


    """

    # 
    if post_code == "19103": # Example postcode from documentation
        diag_result = "outage"
    else:
        diag_result = "device_issue"
    return 

# Shared tool for logging


# --- Agents ---


diagnostic_agent = Agent(
    name="diagnostic_agent",
    model=model_name,
    description="Performs automated network and device diagnostics, integrates with DownDetector.se and OSS.",
    instruction="""


    - based on provided postcode.

    """,
    generate_content_config=types.GenerateContentConfig(
        temperature=0,
    ),
    tools=[append_to_state],
    sub_agents=[],
)



# --- Root Agent for MVP
root_agent = Agent(
    name="greeter",
    model=model_name,
    description="The main AI assistant for diagnosing and resolving internet issues.",
    instruction="""
    - Let the user know you will help them diagnose and resolve their internet issues. 
    - You can check for outages, help the customer troubleshoot, and even schedule a technician if needed.
    - Ask them for the potential internet problem, including your postcode, issue type (e.g., 'slow internet', 'no connection'),
      and device type (e.g., 'router', 'laptop').
    - When they respond, analyze the responses and use the 'append_to_state' tool to store corresponding infomation in the state key 'post_code', 'issue_type', 'device_type'
    """,
    generate_content_config=types.GenerateContentConfig(
        temperature=0,
    ),
    tools=[append_to_state],
    sub_agents=[diagnostic_agent],
)

# and transfer to the 'film_concept_team' agent