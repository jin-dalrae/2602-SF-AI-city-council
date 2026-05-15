from .definitions import (
    BudgetAgent,
    PlanningAgent,
    PublicWorksAgent,
    SFMTAAgent,
    SFPDAgent,
)
from .reddit import RedditAgent
from .x_agent import XAgent
from .coordinator import PolicyCoordinatorAgent
from .sf_news import SFNewsAgent

ALL_AGENTS = [
    SFPDAgent,
    SFMTAAgent,
    PublicWorksAgent,
    BudgetAgent,
    PlanningAgent,
    RedditAgent,
    XAgent,
    PolicyCoordinatorAgent,
]
NEWS_AGENT = SFNewsAgent
