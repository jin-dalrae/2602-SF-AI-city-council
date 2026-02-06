import streamlit as st
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain import hub
from langchain_core.tools import tool
from youdotcom import You  # You.com SDK
from composio_langchain import ComposioToolSet, LangchainProvider
from composio import Composio
import time
import json
from collections import deque
import random

# Config
YOU_API_KEY = st.secrets["YOU_API_KEY"]  # Or input
COMPOSIO_API_KEY = st.secrets["COMPOSIO_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["COMPOSIO_API_KEY"] = COMPOSIO_API_KEY

# CL: EWC (simplified)
class EWC:
    def __init__(self, lambda_ewc=1e4):
        self.lambda_ewc = lambda_ewc
        self.fisher = None
        self.old_params = None

    def compute_fisher(self, model, buffer):  # Replay on buffer
        # Diagonal Fisher approx (from HF continual-learning)
        fisher = {}
        for name, param in model.named_parameters():
            fisher[name] = torch.zeros_like(param.data)
        return fisher  # Placeholder: avg grad^2 on buffer

    def penalty(self, model):
        if self.fisher is None: return 0
        loss = 0
        for name, param in model.named_parameters():
            loss += self.fisher[name] * (param - self.old_params[name]) ** 2
        return self.lambda_ewc * loss

# QNet for RL
class QNet(nn.Module):
    def __init__(self, state_dim=3, act_dim=20):
        super().__init__()
        self.fc = nn.Sequential(nn.Linear(state_dim, 64), nn.ReLU(), nn.Linear(64, act_dim))

    def forward(self, x): return self.fc(x)

# You.com Custom Tool for Farmers
@tool
def youdotcom_search(query: str) -> str:
    """Search real-time trends for pricing/branding."""
    with You(YOU_API_KEY) as you:
        res = you.search.unified(query=query, count=5)
        snippets = [r.snippets[0] if r.snippets else r.description for r in res.results.web if res.results.web]
        return json.dumps(snippets[:3])  # Parse for "prices rising 10%"

# Composio Tools for Traders
composio = Composio(provider=LangchainProvider())
toolset = ComposioToolSet()
trader_tools = toolset.get_tools(action="default", toolkits=["GOOGLE_SHEETS", "GMAIL"])  # Boost via Sheets update

# Agent Factories
llm = ChatOpenAI(model="gpt-4o-mini")
prompt = hub.pull("hwchase17/openai-functions-agent")

def make_farmer_agent():
    tools = [youdotcom_search]
    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False)

def make_trader_agent():
    agent = create_openai_functions_agent(llm, trader_tools, prompt)
    return AgentExecutor(agent=agent, tools=trader_tools, verbose=False)

# Market State (Shared via Sheets in prod; dict here)
class StrawberryMarket:
    def __init__(self):
        self.farmers = []  # List of dicts: {'id':, 'bank':50, 'queue':[], 'price':0.6, 'qnet':QNet(), 'ewc':EWC(), 'buffer':deque(maxlen=1000)}
        self.traders = []
        self.strawberries = []  # [{'id':, 'time_made':, 'maker':, 'brand':, 'price':}]
        self.tick = 0

    def add_farmer(self):
        agent = {'id': len(self.farmers), 'bank': 50, 'queue': [], 'price': 0.6, 'executor': make_farmer_agent(),
                 'qnet': QNet(), 'optimizer': optim.Adam(self.qnet.parameters(), lr=1e-3), 'ewc': EWC(), 'buffer': deque(maxlen=1000)}
        self.farmers.append(agent)

    def add_trader(self):
        agent = {'id': len(self.traders), 'bank': 100, 'executor': make_trader_agent(), 'qnet': QNet(), 'ewc': EWC(), 'buffer': deque()}
        self.traders.append(agent)

    def tick_step(self):
        self.tick += 1
        # Farmers act
        for f in self.farmers:
            state = np.array([f['bank']/100, len(f['queue'])/20, f['price']])
            qvals = f['qnet'](torch.tensor(state)).detach()
            act = torch.argmax(qvals).item()  # RL select
            # LLM refine: Prompt w/ state + tool
            task = f"Market state: bank={f['bank']}, queue={len(f['queue'])}. Act: {act} (0=produce,1-20=price delta). Use search for trends."
            result = f['executor'].invoke({"input": task})
            # Parse result -> produce/boost price/brand (sim: random for MVP)
            if random.random() < 0.5:  # Produce
                f['queue'].append({'time': self.tick + 10, 'brand': 'GlowBerry'})
                f['bank'] -= 0.2
            f['price'] += (act - 10) * 0.005  # Delta
            f['bank'] += random.uniform(0, 1)  # Mock sales

            # Reward & Learn
            reward = f['bank'] - 50  # Δ
            f['buffer'].append((state, act, reward))
            self.update_qnet(f)

        # Traders: Similar, buy/boost/resell @1.0, fee 0.1
        for t in self.traders:
            t['bank'] -= 0.1  # Fee
            # Act: Buy/boost/spawn via Composio (mock: Sheets 'boost' halves queue time)
            if self.strawberries and t['bank'] > 1:
                berry = self.strawberries.pop(0)
                cost = berry['price']
                if t['bank'] > cost:
                    t['bank'] -= cost
                    t['bank'] += 1.0  # Resell

        # Ripen & List
        for f in self.farmers:
            f['queue'] = [s for s in f['queue'] if (self.tick - s['time']) > 0]
            self.strawberries.extend([{'id':f'f{f["id"]}-{self.tick}', 'price':f['price'], 'maker':f['id']} for _ in range(len(f['queue']))])

        # Perish/Rebirth
        self.farmers = [f for f in self.farmers if f['bank'] > 0]
        self.traders = [t for t in self.traders if t['bank'] > 0]
        if len(self.farmers) < 5: self.add_farmer()  # Respawn

    def update_qnet(self, agent):
        if len(agent['buffer']) < 32: return
        batch = random.sample(agent['buffer'], 32)
        states, acts, rews = zip(*batch)
        states = torch.tensor(np.array(states))
        q = agent['qnet'](states)
        targets = q.clone()
        targets[range(32), acts] = torch.tensor(rews)
        loss = nn.MSELoss()(q, targets) + agent['ewc'].penalty(agent['qnet'])
        agent['optimizer'].zero_grad()
        loss.backward()
        agent['optimizer'].step()
        # Update EWC every 100 steps
        if self.tick % 100 == 0:
            agent['ewc'].fisher = agent['ewc'].compute_fisher(agent['qnet'], agent['buffer'])
            agent['ewc'].old_params = {n: p.clone() for n, p in agent['qnet'].named_parameters()}

# Streamlit UI
st.title("🍓 Strawberry Reincarnation Market – CL Agents Dominate!")
market = StrawberryMarket()
for _ in range(5): market.add_farmer(); market.add_trader()

if st.button("Run 100 Ticks"):
    profits = []
    for _ in range(100):
        market.tick_step()
        profits.append(sum(f['bank'] for f in market.farmers) + sum(t['bank'] for t in market.traders))
    st.line_chart(profits)
    st.metric("Total Berries Sold", len(market.strawberries))
    st.metric("Surviving Farmers", len(market.farmers))
    st.json({"Avg Price": np.mean([s.get('price', 0.6) for s in market.strawberries])})

# CL Demo Toggle
st.subheader("CL Proof: Toggle Off → Chaos")
# (Extend: Run no-EWC baseline)

st.code("Full code above – Add real Sheets: trader_tools.execute('sheets_update', {'boost': seller_id})")