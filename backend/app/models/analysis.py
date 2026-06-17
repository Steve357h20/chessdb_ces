import json
from datetime import datetime
from app import db


class Analysis(db.Model):
    __tablename__ = 'analyses'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False, unique=True, index=True)
    analysis_data = db.Column(db.Text, default='{}', comment='JSON: 完整分析数据')
    opening_eco = db.Column(db.String(10), default='')
    key_moves = db.Column(db.Text, default='[]', comment='JSON: 关键手列表')
    win_rate_curve = db.Column(db.Text, default='[]', comment='JSON: 胜率曲线数据')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_analysis_data(self):
        if self.analysis_data:
            try:
                return json.loads(self.analysis_data)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_analysis_data(self, data):
        self.analysis_data = json.dumps(data, ensure_ascii=False)

    def get_key_moves(self):
        if self.key_moves:
            try:
                return json.loads(self.key_moves)
            except json.JSONDecodeError:
                return []
        return []

    def set_key_moves(self, moves):
        self.key_moves = json.dumps(moves, ensure_ascii=False)

    def get_win_rate_curve(self):
        if self.win_rate_curve:
            try:
                return json.loads(self.win_rate_curve)
            except json.JSONDecodeError:
                return []
        return []

    def set_win_rate_curve(self, curve):
        self.win_rate_curve = json.dumps(curve, ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id,
            'game_id': self.game_id,
            'opening_eco': self.opening_eco,
            'key_moves': self.get_key_moves(),
            'win_rate_curve': self.get_win_rate_curve(),
            'analysis_data': self.get_analysis_data(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<Analysis game_id={self.game_id}>'


class AnalysisTask(db.Model):
    """Persistent analysis task state, shared across gunicorn workers."""
    __tablename__ = 'analysis_tasks'

    id = db.Column(db.String(36), primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='pending')  # pending, running, completed, failed, cancelled
    progress = db.Column(db.Float, default=0.0)
    result = db.Column(db.Text, default='')
    error = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_result(self):
        if self.result:
            try:
                return json.loads(self.result)
            except json.JSONDecodeError:
                return None
        return None

    def set_result(self, data):
        self.result = json.dumps(data, ensure_ascii=False) if data else ''

    def to_dict(self):
        return {
            'task_id': self.id,
            'game_id': self.game_id,
            'status': self.status,
            'progress': self.progress,
            'result': self.get_result(),
            'error': self.error or None,
        }

    def __repr__(self):
        return f'<AnalysisTask id={self.id} game_id={self.game_id} status={self.status}>'
