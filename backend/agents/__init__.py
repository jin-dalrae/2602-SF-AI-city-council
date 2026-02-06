from .sfpd import SFPDAgent
from .sfmta import SFMTAAgent
from .public_works import PublicWorksAgent
from .budget import BudgetAgent
from .planning import PlanningAgent
from .sf_news import SFNewsAgent

ALL_AGENTS = [SFPDAgent, SFMTAAgent, PublicWorksAgent, BudgetAgent, PlanningAgent]
NEWS_AGENT = SFNewsAgent
