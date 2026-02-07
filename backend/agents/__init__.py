from .sfpd import SFPDAgent
from .sfmta import SFMTAAgent
from .public_works import PublicWorksAgent
from .budget import BudgetAgent
from .planning import PlanningAgent
from .sf_news import SFNewsAgent
from .reddit import RedditAgent
from .x_agent import XAgent
from .coordinator import PolicyCoordinatorAgent

ALL_AGENTS = [SFPDAgent, SFMTAAgent, PublicWorksAgent, BudgetAgent, PlanningAgent, RedditAgent, XAgent, PolicyCoordinatorAgent]
NEWS_AGENT = SFNewsAgent
