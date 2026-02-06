import requests

url = "https://api.you.com/v1/agents/runs"

payload = {
  "agent": "advanced",
  "input": "from the data you can find in x, hackernews, geeknews, github, what kind of new technology will be developed in 2026?",
  "stream": True,
  "tools": [
    {
      "type": "research",
      "search_effort": "high",
      "report_verbosity": "high"
    }
  ],
  "verbosity": "medium",
  "workflow_config": { "max_workflow_steps": 10 }
}
headers = {
  "Authorization": "Bearer <api-key>",
  "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.json())