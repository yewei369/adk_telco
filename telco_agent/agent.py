import os
import logging
import json
from datetime import datetime, timedelta
import os.path
import pickle

# ADK imports
from google.adk import Agent
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.tool import Tool
from google.adk.tools import google_search
from google.adk.tools import exit_loop # For LoopAgent termination
from google.adk.hand_off import EndSession # For explicit handoff from policy agent

# Google Cloud client library imports
from google.cloud import bigquery
from google.cloud import storage
from google.cloud import aiplatform
from googleapiclient.discovery import build # For Google Search, Calendar, Meet APIs
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Load environment variables (for local development)
from dotenv import load_dotenv
load_dotenv()

## initial setup
cloud_logging_client = google.cloud.logging.Client()
cloud_logging_client.setup_logging()
load_dotenv()
model_name = os.getenv("MODEL")
print(model_name)

# --- Global/Shared Configuration ---
# Use environment variables, or default to your project values
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "hacker2025-team-212-dev")
CLOUD_REGION = os.environ.get("CLOUD_REGION", "europe-west1") # Consistent region
LOG_DATASET = os.environ.get("LOG_DATASET", "cx_logs")
LOG_TABLE = os.environ.get("LOG_TABLE", "conversation_events")
LOG_BUCKET = os.environ.get("LOG_BUCKET", "northern_lights_bucket")

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Tools ---

def append_to_state(
    tool_context: ToolContext, field: str, response: str
    ) -> dict[str, str]:
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

# Shared tool for logging


# --- Agents ---
# Central Log Agent (J)
log_agent = Agent(
    name="log_agent",
    description="Logs all conversational and diagnostic data for analytics and knowledge base.",
    tools=[
        BigQueryLoggerTool(PROJECT_ID, LOG_DATASET, LOG_TABLE),
        CloudStorageLoggerTool(LOG_BUCKET)
    ],
    instruction="Logs incoming data to BigQuery and Cloud Storage for historical tracking.",
    can_initiate_conversation=False
)

# Status Agent (New Agent)
status_agent = Agent(
    name="status_agent",
    description="Summarizes the current session status and resolution state.",
    tools=[BigQueryQueryTool(PROJECT_ID, LOG_DATASET, LOG_TABLE)],
    instruction="Retrieves and provides a summary of the current session's status from the logs.",
    can_initiate_conversation=False
)

# Diagnostics Agent (C) - Integrated directly in agent.py but calls external Cloud Function
# NOTE: In agent_registry.yaml, we had it pointing to a Cloud Function.
# For a monolithic agent.py, this definition acts as a placeholder for the agent's identity
# within the ADK structure, even if the actual execution goes to a separate Cloud Function.
# The orchestrator will use the agent_registry.yaml's endpoint for actual calls.
diagnostics_agent = Agent(
    name="diagnostics_agent",
    description="Performs automated network and device diagnostics, integrates with DownDetector.se and OSS.",
    instruction="Simulates diagnostics results based on provided postcode.",
    can_initiate_conversation=False
)

# Troubleshooting RAG Agent (D)
troubleshooting_rag_agent = Agent(
    name="troubleshooting_rag_agent",
    description="Searches knowledge base and external sources for troubleshooting steps and provides fixes.",
    tools=[google_search, VertexAISearchTool()],
    instruction="""
        Based on diagnostic results and customer issue, search the product troubleshooting data repository
        for relevant, step-by-step guides. If direct fixes aren't found, use Google Search for public manuals.
        Always aim to provide actionable troubleshooting steps or escalate if no solution is found.
        """,
    can_initiate_conversation=False
)

# Booking Agent (H)
booking_agent = Agent(
    name="booking_agent",
    description="Schedules technician visits or initiates firmware updates, integrating with Google Calendar and Meet.",
    tools=[GoogleCalendarTool()], # GoogleCalendarTool already encompasses Meet functionality
    instruction="""
        Automatically schedules technician visits using Google Calendar.
        Can create Google Meet links for virtual technician calls if requested.
        Confirm date, time, issue, device, customer name, and city.
        """,
    can_initiate_conversation=False
)

# Policy Agent (F) - Reroute Agent
policy_agent = Agent(
    name="policy_agent",
    description="Determines escalation or retry conditions and orchestrates handoffs to live agents.",
    tools=[TeamsHandoffTool(), exit_loop], # exit_loop is a built-in ADK tool for workflow agents
    instruction="""
        Evaluates diagnostic results and troubleshooting status.
        If an outage is confirmed or automated troubleshooting fails, gracefully hand over to a human agent in Microsoft Teams.
        Otherwise, suggest further automated steps or booking a technician visit.
        """,
    can_initiate_conversation=False
)

# --- Root Agent for MVP Testing (mimicking lab's entry point) ---
# This agent will act as the direct entry point when running 'adk run .' or 'adk web'
# It demonstrates how the overall system could begin and delegate.
root_agent = Agent(
    name="comcast_ai_assistant",
    model=model_name,
    description="The main AI assistant for diagnosing and resolving internet issues.",
    instruction="""
        Hi! I'm here to help diagnose and resolve your internet issues.
        I can check for outages, help you troubleshoot, and even schedule a technician if needed.
        Please tell me about your internet problem, including your postcode, issue type (e.g., 'slow internet', 'no connection'),
        and device type (e.g., 'router', 'laptop').
        """,
    generate_content_config=types.GenerateContentConfig(
        temperature=0,
    ),
    tools=[append_to_state],
    can_initiate_conversation=True, # This agent starts the conversation
    sub_agents=[
        # List your specialized agents here so comcast_ai_assistant can delegate
        '''diagnostics_agent,
        troubleshooting_rag_agent,
        booking_agent,
        policy_agent,
        log_agent,
        status_agent'''
    ]
)