from composio import Composio
from langchain.agents import create_agent
from langchain_openai.chat_models import ChatOpenAI

# Initialize Composio
composio = Composio(api_key="ak_zMx6z54f0h6_e1BApUnw")

external_user_id = "pg-test-a885dd5a-71b2-49da-8e3d-d4ffd99bc550"

# Create a tool router session
session = composio.create(
    user_id=external_user_id,
)

# Get tools from the session (native)
tools = session.tools()

# Initialize LangChain model
model = ChatOpenAI(model="gpt-4o")

# Create agent
agent = create_agent(
    tools=tools,
    model=model,
)

# Run the agent
result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "Send an email to dalrae.jin.work@gmail.com with the subject 'Hello from Composio' and the body 'This is a test email!'",
            }
        ]
    }
)

print("✅ Email sent successfully!")
print(result)

