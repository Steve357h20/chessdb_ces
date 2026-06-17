from datetime import datetime
from app import db


class ModificationRequest(db.Model):
    """用户对核心数据的修改/删除/添加申请，需管理员审核。

    对应答辩问题 1：前端用户对棋谱/收藏/账号等危险操作
    不直接生效，而是提交申请进入本表，等待管理员审核。
    """
    __tablename__ = 'modification_requests'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 申请人（普通用户）
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    # 资源类型: 'game' | 'puzzle' | 'collection' | 'profile' | 'player'
    target_type = db.Column(db.String(32), nullable=False, index=True)
    # 操作: 'create' | 'update' | 'delete'
    action = db.Column(db.String(16), nullable=False)
    # 目标资源 ID（create 时为 None）
    target_id = db.Column(db.Integer, nullable=True, index=True)
    # 提交的数据（create 时为新数据；update 时为新值；delete 时为删除原因）
    payload_json = db.Column(db.Text, default='{}')
    # 申请理由
    reason = db.Column(db.Text, default='')
    # 状态: 'pending' | 'approved' | 'rejected'
    status = db.Column(db.String(16), default='pending', index=True)
    # 审核管理员
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    review_comment = db.Column(db.Text, default='')
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    applicant = db.relationship('User', foreign_keys=[user_id], backref='mod_requests')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'applicant_name': self.applicant.username if self.applicant else None,
            'target_type': self.target_type,
            'action': self.action,
            'target_id': self.target_id,
            'payload': self.payload_json,
            'reason': self.reason,
            'status': self.status,
            'reviewer_id': self.reviewer_id,
            'reviewer_name': self.reviewer.username if self.reviewer else None,
            'review_comment': self.review_comment,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ApiAccessLog(db.Model):
    """API 流量监控日志。

    对应答辩问题 1：按 token / 用户 / 端点 统计 API 访问频次。
    """
    __tablename__ = 'api_access_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 时间（索引）
    accessed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    # HTTP 方法与路径
    method = db.Column(db.String(8), nullable=False)
    path = db.Column(db.String(256), nullable=False, index=True)
    # 状态码
    status_code = db.Column(db.Integer, nullable=False, index=True)
    # 耗时（毫秒）
    duration_ms = db.Column(db.Integer, default=0)
    # 用户信息
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    username = db.Column(db.String(80), nullable=True, index=True)
    # 客户端 IP
    ip_address = db.Column(db.String(64), default='')
    # JWT token 摘要（只存前 16 位，避免泄露完整 token）
    token_fingerprint = db.Column(db.String(32), default='', index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'accessed_at': self.accessed_at.isoformat() if self.accessed_at else None,
            'method': self.method,
            'path': self.path,
            'status_code': self.status_code,
            'duration_ms': self.duration_ms,
            'user_id': self.user_id,
            'username': self.username,
            'ip_address': self.ip_address,
            'token_fingerprint': self.token_fingerprint,
        }
