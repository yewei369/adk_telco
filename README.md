# adk_telco
Using Google ADK to develop multi-agent for Telco diagnostics

# to setup
cloudshell workspace ~

python3 -m venv .adk
source .adk/bin/activate

export PATH=$PATH:"/home/${USER}/.local/bin"
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=hacker2025-team-212-dev
export GOOGLE_CLOUD_LOCATION=us-central1
export MODEL=gemini-2.0-flash-001

python3 -m pip install google-adk==1.2.1
python3 -m pip install -r requirements.txt

git clone https://github.com/yewei369/adk_telco.git