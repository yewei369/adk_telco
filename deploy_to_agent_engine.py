import os
import vertexai
from vertexai.preview.reasoning_engines import AdkApp
from vertexai import agent_engines
from dotenv import load_dotenv

from telco_agent.agent import root_agent

load_dotenv()

vertexai.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION"),
    staging_bucket="gs://" + os.getenv("GOOGLE_CLOUD_PROJECT")+"-bucket",
)

'''app = AdkApp(
    agent=root_agent,
    enable_tracing=True,
)'''

remote_app = agent_engines.create(
    display_name=os.getenv("APP_NAME", "Agent App 1"),
    agent_engine=root_agent,
    requirements=[
        'fire==0.7.0',
        "google-cloud-aiplatform[adk,agent_engines]==1.98.0",
        'cloudpickle==3.1.1', 
        'pydantic==2.11.7',
        'google-adk==1.2.1',
        'langchain==0.3.25'
    ],
    extra_packages = ["telco_agent"],
    env_vars = {
        "GOOGLE_GENAI_USE_VERTEXAI": "True",
        "MODEL": "gemini-2.0-flash-001"
    }
)