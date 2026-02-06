import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("YOU_COM_API_KEY")

if not API_KEY or API_KEY == "your_api_key_here":
    print("Error: Please set YOU_COM_API_KEY in your .env file.")
    exit(1)

API_KEY = API_KEY.strip()


url = "https://api.you.com/v1/agents/runs"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "agent": "advanced",
    "input": "Explain how quantum computers work using analogies a 5-year-old could understand.",
    "stream": True,
    "tools": [{"type": "research"}, {"type": "compute"}],
    "verbosity": "medium",
    "workflow_config": {"max_workflow_steps": 5}
}

print(f"Sending request to {url}...")
print(f"Input: {payload['input']}\n")

try:
    response = requests.post(url, headers=headers, json=payload, stream=True)
    response.raise_for_status()

    print("--- Streaming Response ---")
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("data: "):
                data_str = decoded_line[6:]
                try:
                    data = json.loads(data_str)
                    # Attempt to extract text content if present, common in many SSE APIs
                    if "event" in data:
                        event = data["event"]
                        if event == "updated":
                             # This might replace previous text or append. 
                             # Without exact specs, printing raw structure might be safer, 
                             # but let's try to be helpful. 
                             # For now, let's just print the raw event data nicely.
                             pass
                    print(json.dumps(data, indent=2))
                except json.JSONDecodeError:
                    print(decoded_line)
            else:
                print(decoded_line)
except requests.exceptions.RequestException as e:
    print(f"Error making request: {e}")
