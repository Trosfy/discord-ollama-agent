"""Task Planner agent plugin definition."""
from .agent import TaskPlannerAgent


PLUGIN = {
    "type": "agent",
    "name": "task_planner",
    "class": TaskPlannerAgent,
    "description": "Decomposes complex coding tasks into structured implementation steps",
    "category": "code",
    "tools": ["brain_search"],
    "config": {
        "temperature": 0.3,
        "max_tokens": 4096,
        "model_role": "code",
    },
}
