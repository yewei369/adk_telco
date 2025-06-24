import os
import logging
import google.cloud.logging
import json

from dotenv import load_dotenv

from google.adk import Agent
from google.adk.agents import SequentialAgent, LoopAgent, ParallelAgent
from google.adk.tools import google_search  # The Google Search tool
#from google.adk.tools.tool import Tool
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.langchain_tool import LangchainTool  # import
#from google.adk.tools.crewai_tool import CrewaiTool
from google.genai import types

#from langchain_community.tools import WikipediaQueryRun
#from langchain_community.utilities import WikipediaAPIWrapper
#from crewai_tools import FileWriterTool
from google.cloud import storage

from .rag import query_rag_tool
from .callback_logging import log_query_to_model, log_model_response

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


def live_agent(tool_context: ToolContext, conversation_context: dict):
    '''Pass conversation context to the live agent in Teams. 
       This is a dummy function and will developed and replaced by a real Teams session
    '''

    logging.info(f"Initiating handoff to Teams with context: {json.dumps(conversation_context, indent=2)}")
    return "Handoff to a live agent in Teams initiated successfully."

def fixed_calendar(date: str, time: str, issue_type: str, customer_name: str, city: str):
    '''Given date, time, customer_name, city, book a meeting for the customer
    '''
    ## replace the following with a working Google_Calendar_Tool
    logging.info(f'The meeting has been arranged for {customer_name} regarding {issue_type} in {city} at {date} {time}')
    return {"status": "success"}

def logger_bucket(session_id: str, content: str) -> dict:
    '''Archives raw conversational transcripts or large data outputs to Cloud Storage as json files.
    Args:
        session_id: id of conversation session
        content: conversation history and context
    Returns:
        dict[str, str]: {"status": "success"}
    '''
    blob_path = f"logs/{session_id}"
    bucket = storage.Client().bucket('northern_lights_bucket')
    blob = bucket.blob(blob_path)
    try:
        blob.upload_from_string(content, content_type="application/json")
        logging.info(f"Uploaded {file_name} for session '{session_id}' to gs://{bucket.name}/{blob_path}")
        return {"status": "success", "gcs_uri": f"gs://{bucket.name}/{blob_path}"}
    except Exception as e:
        logging.error(f"Error uploading to GCS: {e}")
        return {"status": "error", "message": f"Error uploading to GCS: {e}"}

# --- Agents ---

## 5: Logging_agent
log_agent = Agent(
    name="log_agent",
    model=model_name,
    description="Logs all conversational and diagnostic data for analytics and knowledge base.",
    instruction="""
    Logs the conversation and troubleshooting process to Cloud Storage for historical tracking.
    Save the context using the tool 'logger_bucket'
    """,
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    generate_content_config=types.GenerateContentConfig(temperature=0,),
    tools=[append_to_state,logger_bucket],
    sub_agents=[],
)

## 4: Booking_agent
booking_agent = Agent(
    name="booking_agent",
    model=model_name,
    description="Schedules technician visits or initiates firmware updates, integrating with Google Calendar and Meet.",
    instruction="""
    Automatically schedules technician visits using Google Calendar.
    Use tool 'fixed_calendar' to create Google Meet links for virtual technician calls if requested.
    Confirm date, time, {{issue_type?}}, {{device?}}, {{customer_name?}}, and {{city?}}.
    """,
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    generate_content_config=types.GenerateContentConfig(temperature=0,),
    tools=[append_to_state,live_agent,fixed_calendar],
    sub_agents=[],
)


## 3: Reroute_agent
reroute_agent = Agent(
    name="reroute_agent",
    model=model_name,
    description="Determines escalation or retry conditions and orchestrates handoffs to live agents.",
    instruction="""
    INSTRUCTIONS:
    Evaluates diagnostic results and troubleshooting status.
    - if automated troubleshooting from 'rag_agent' succeeds, the diglog will end and transfer to 'log_agent'
    - if automated troubleshooting from 'rag_agent' fails, or firmware updating required, 
        * if the user responds that their issue is still not resolved then transfer to 'booking_agent'
        * or booking a technician visit is asked by the user, transfer to 'booking_agent'
        * after booking a technical visit, if the user is satisfied with the arrangement, the diglog will end and transfer to 'log_agent'    
        * if automated troubleshooting from 'rag_agent' fails, gracefully hand over to a human agent in Microsoft Teams.
        * if the user ask for the human operator please use the tool 'live_agent'
    - in case no relevant guidance or suggestion is found, instead of asking the user to turn to manufacturer for more investigation or help, transfer to 'booking_agent' or live agent
    - after interacting with live agent and confirmed if the user is satisfied, the diglog will end and transfer to 'log_agent'
    - live agent will be connected ONLY IF there is no relevant guidance or suggestion found by 'rag_agent' OR it's required by the customer

    """,
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    generate_content_config=types.GenerateContentConfig(temperature=0,),
    tools=[append_to_state,live_agent],
    sub_agents=[booking_agent,log_agent],
)


## 2: Search_agent
rag_agent = Agent(
    name="troubleshooting_rag_agent",
    model=model_name,
    description="Searches knowledge base and external sources for troubleshooting steps and provides fixes.",
    instruction="""
    INSTRUCTIONS:
    Based on diagnostic results and customer issue, always aim to provide actionable troubleshooting steps or escalate if no solution is found.

    - if {{diag_result??}} is 'device_issue', kindly ask the user for the device item name or number, and save it in the state key 'device'. DO NOT transfer to next agent if you have not got your question answered
    - then search in knowledge base for the troubleshooting steps related to the {{issue_type??}} and {{device??}}, using the tool 'query_rag_tool' with dialog history as 'query' to the tool. 
    - Based on the response of 'query_rag_tool', formulate an answer to the user
    - if no useful information found in knowledge base, turn to public manual and information base for help
    - after giving troubleshooting suggestions, transfer to the next agent 'reroute_agent'. BUT with no confirmation from the user wheather the problem gets solved or not, you should not transfer to the next agent.
    """,
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    generate_content_config=types.GenerateContentConfig(temperature=0,),
    tools=[append_to_state,query_rag_tool],
    sub_agents=[reroute_agent],
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

    - First, you should short introduce yourself, then greet the customer in similar pattern with as 'Hi, how are you?'
    - wait for the response from greeting the user , AFTER user's confirmation and smoothly switch into asking for details of the issue.
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