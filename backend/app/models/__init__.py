from app import db
from app.models.player import Player
from app.models.game import Game
from app.models.tournament import Tournament
from app.models.analysis import Analysis, AnalysisTask
from app.models.opening import Opening
from app.models.user import User
from app.models.collection import Collection
from app.models.practice import PracticeGame, Puzzle
from app.models.browsing_history import BrowsingHistory
from app.models.admin_models import ModificationRequest, ApiAccessLog

__all__ = [
    'Player', 'Game', 'Tournament',
    'Analysis', 'AnalysisTask', 'Opening', 'User', 'Collection',
    'PracticeGame', 'Puzzle', 'BrowsingHistory',
    'ModificationRequest', 'ApiAccessLog',
]
