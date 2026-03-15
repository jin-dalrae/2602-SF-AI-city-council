"""
Persistence layer for agent findings.
Saves findings to a JSON file so they survive server restarts.
"""

import json
import os
from datetime import datetime
from pathlib import Path

STORAGE_DIR = Path(__file__).resolve().parent.parent / "data"
FINDINGS_FILE = STORAGE_DIR / "findings.json"
HISTORY_FILE = STORAGE_DIR / "findings_history.json"


def ensure_storage():
    """Create storage directory if it doesn't exist."""
    STORAGE_DIR.mkdir(exist_ok=True)


def save_findings(findings_store: dict) -> None:
    """Save current findings to disk."""
    ensure_storage()
    # Filter out internal keys (starting with _)
    to_save = {k: v for k, v in findings_store.items() if not k.startswith("_")}
    with open(FINDINGS_FILE, "w") as f:
        json.dump(to_save, f, indent=2, default=str)


def load_findings() -> dict:
    """Load findings from disk if they exist."""
    if not FINDINGS_FILE.exists():
        return {}
    try:
        with open(FINDINGS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}




def append_to_history(finding: dict) -> None:
    """Append a finding to the history file for long-term storage."""
    ensure_storage()
    history = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []
    
    # Add timestamp if not present
    finding_copy = finding.copy()
    if "saved_at" not in finding_copy:
        finding_copy["saved_at"] = datetime.now().isoformat()
    
    history.append(finding_copy)
    
    # Keep only last 5000 entries (increased from 500)
    history = history[-5000:]
    
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, default=str)


MEMORY_FILE = STORAGE_DIR / "agent_memory.json"


def save_memory(agent_name: str, summary: str, embedding: list[float]) -> None:
    """Save an agent's memory with its embedding."""
    ensure_storage()
    memories = []
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, "r") as f:
                memories = json.load(f)
        except (json.JSONDecodeError, IOError):
            memories = []

    memories.append({
        "agent": agent_name,
        "summary": summary,
        "embedding": embedding,
        "timestamp": datetime.now().isoformat()
    })
    
    # Keep last 200 memories
    memories = memories[-200:]
    with open(MEMORY_FILE, "w") as f:
        json.dump(memories, f, indent=2)


def search_memory(agent_name: str, query_embedding: list[float], limit: int = 3) -> list[str]:
    """Find similar past memories for an agent using simple cosine similarity."""
    if not MEMORY_FILE.exists() or not query_embedding:
        return []
    
    try:
        with open(MEMORY_FILE, "r") as f:
            memories = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []
    
    # Filter for this agent's memories
    agent_mems = [m for m in memories if m["agent"] == agent_name]
    if not agent_mems:
        return []
    
    import math

    def cosine_sim(v1, v2):
        if not v1 or not v2: return 0
        dot = sum(a*b for a, b in zip(v1, v2))
        mag1 = math.sqrt(sum(a*a for a in v1))
        mag2 = math.sqrt(sum(b*b for b in v2))
        if mag1 == 0 or mag2 == 0: return 0
        return dot / (mag1 * mag2)

    # Score and sort
    scored = []
    for m in agent_mems:
        score = cosine_sim(query_embedding, m["embedding"])
        scored.append((score, m["summary"]))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in scored[:limit] if s[0] > 0.7] # Only return relevant memories


def get_history(agent_name: str = None, limit: int = 50) -> list:
    """Get historical findings, optionally filtered by agent name."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []
    
    if agent_name:
        history = [h for h in history if h.get("agent_name") == agent_name]
    
    return history[-limit:]


def apply_code_update(file_path: str, method_name: str, new_code: str) -> bool:
    """
    Dynamically update an agent's source code. 
    Searches for the method and replaces its content.
    """
    if not os.path.exists(file_path):
        return False
    
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()
        
        start_line = -1
        end_line = -1
        indent = ""
        
        # Find the method start
        for i, line in enumerate(lines):
            if f"def {method_name}(" in line:
                start_line = i
                # Detect indentation of the next line (the body)
                if i + 1 < len(lines):
                    next_line = lines[i+1]
                    indent = next_line[:len(next_line) - len(next_line.lstrip())]
                break
        
        if start_line == -1:
            return False
            
        # Find the method end (next line with same or less indentation, excluding empty lines)
        method_indent = lines[start_line][:len(lines[start_line]) - len(lines[start_line].lstrip())]
        for i in range(start_line + 1, len(lines)):
            line = lines[i]
            if line.strip() == "": continue
            line_indent = line[:len(line) - len(line.lstrip())]
            if len(line_indent) <= len(method_indent):
                end_line = i
                break
        
        if end_line == -1:
            end_line = len(lines)
            
        # Format the new code with correct indentation
        formatted_code = []
        for line in new_code.strip().split("\n"):
            # Ensure the def line isn't part of new_code, or handle it
            if line.strip().startswith(f"def {method_name}"):
                formatted_code.append(line + "\n")
            else:
                formatted_code.append(indent + line.lstrip() + "\n")

        # Replace the lines
        if "def" in formatted_code[0]:
            new_lines = lines[:start_line] + formatted_code
        else:
            new_lines = lines[:start_line + 1] + formatted_code
            
        new_lines = new_lines + lines[end_line:]
        
        temp_path = f"{file_path}.tmp"
        with open(temp_path, "w") as f:
            f.writelines(new_lines)
        os.replace(temp_path, file_path)
        return True
    except Exception as e:
        print(f"Failed to apply code update: {e}")
        return False
