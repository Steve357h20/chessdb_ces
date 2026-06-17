"""API 流量监控中间件。

对应答辩问题 1：对每个 API 请求自动记录
- method/path/status_code/duration_ms
- user_id/username（从 JWT 解出）
- token_fingerprint（仅前 16 位哈希）
- ip_address

提供 /api/admin/traffic/* 端点供管理后台查询/聚合。
"""
import hashlib
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from sqlalchemy import func

from app import db
from app.models.admin_models import ApiAccessLog, ModificationRequest
from app.models.user import User

logger = logging.getLogger(__name__)

admin_api_bp = Blueprint('admin_api', __name__, url_prefix='/api/admin')


def init_traffic_middleware(app):
    """注册请求前/后钩子，自动记录 API 访问日志。

    调用位置：app/__init__.py create_app 末尾
    """
    @app.before_request
    def _start_timer():
        g._req_start = time.time()

    @app.after_request
    def _log_request(response):
        # 仅记录 /api/ 前缀请求；跳过静态/文档/上传文件
        if not request.path.startswith('/api/'):
            return response
        if request.path.startswith('/api/admin/traffic'):
            return response  # 自递归，避免无限写日志

        duration_ms = int((time.time() - getattr(g, '_req_start', time.time())) * 1000)

        user_id = None
        username = None
        token_fp = ''
        try:
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()
            if identity is not None:
                user = User.query.filter_by(username=identity).first()
                if not user:
                    try:
                        user = User.query.get(int(identity))
                    except (TypeError, ValueError):
                        user = None
                if user:
                    user_id = user.id
                    username = user.username
        except Exception:
            pass

        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token_fp = hashlib.md5(auth[7:].encode('utf-8')).hexdigest()[:16]

        try:
            log = ApiAccessLog(
                method=request.method,
                path=request.path[:255],
                status_code=response.status_code,
                duration_ms=duration_ms,
                user_id=user_id,
                username=username,
                ip_address=request.remote_addr or '',
                token_fingerprint=token_fp,
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning('Failed to log API access: %s', e)

        return response


# ---------------- 流量查询 API（仅管理员可访问）----------------

def _require_admin():
    verify_jwt_in_request()
    identity = get_jwt_identity()
    user = None
    if identity is not None:
        user = User.query.filter_by(username=identity).first()
        if not user:
            try:
                user = User.query.get(int(identity))
            except (TypeError, ValueError):
                user = None
    if not user or not user.is_admin:
        return None, (jsonify({'error': 'Admin only'}), 403)
    return user, None


@admin_api_bp.route('/traffic/recent', methods=['GET'])
def traffic_recent():
    """最近 N 条访问记录"""
    admin, err = _require_admin()
    if err:
        return err
    limit = min(int(request.args.get('limit', 100)), 500)
    rows = ApiAccessLog.query.order_by(ApiAccessLog.id.desc()).limit(limit).all()
    return jsonify({'logs': [r.to_dict() for r in rows], 'total': len(rows)})


@admin_api_bp.route('/traffic/summary', methods=['GET'])
def traffic_summary():
    """按小时/端点的聚合统计"""
    admin, err = _require_admin()
    if err:
        return err
    hours = int(request.args.get('hours', 24))
    since = datetime.utcnow() - timedelta(hours=hours)

    # 1. 总体概览
    total = ApiAccessLog.query.filter(ApiAccessLog.accessed_at >= since).count()
    unique_users = db.session.query(func.count(func.distinct(ApiAccessLog.username))).filter(
        ApiAccessLog.accessed_at >= since,
    ).scalar() or 0
    err_count = ApiAccessLog.query.filter(
        ApiAccessLog.accessed_at >= since,
        ApiAccessLog.status_code >= 400,
    ).count()

    # 2. 按路径聚合（TOP 20）
    by_path = db.session.query(
        ApiAccessLog.path,
        func.count(ApiAccessLog.id).label('count'),
        func.avg(ApiAccessLog.duration_ms).label('avg_ms'),
    ).filter(ApiAccessLog.accessed_at >= since).group_by(
        ApiAccessLog.path,
    ).order_by(func.count(ApiAccessLog.id).desc()).limit(20).all()

    # 3. 按用户聚合（TOP 20）
    by_user = db.session.query(
        ApiAccessLog.username,
        func.count(ApiAccessLog.id).label('count'),
    ).filter(
        ApiAccessLog.accessed_at >= since,
        ApiAccessLog.username.isnot(None),
    ).group_by(
        ApiAccessLog.username,
    ).order_by(func.count(ApiAccessLog.id).desc()).limit(20).all()

    # 4. 按小时分桶（最近 24h，每小时一个点）
    by_hour_rows = db.session.query(
        func.strftime('%Y-%m-%d %H:00', ApiAccessLog.accessed_at).label('hour'),
        func.count(ApiAccessLog.id).label('count'),
    ).filter(ApiAccessLog.accessed_at >= since).group_by('hour').order_by('hour').all()

    return jsonify({
        'summary': {
            'total_requests': total,
            'unique_users': int(unique_users),
            'error_count': err_count,
            'error_rate': round(err_count / total, 4) if total else 0,
            'hours_window': hours,
        },
        'by_path': [
            {'path': r.path, 'count': r.count, 'avg_ms': round(r.avg_ms or 0, 1)}
            for r in by_path
        ],
        'by_user': [
            {'username': r.username, 'count': r.count}
            for r in by_user
        ],
        'by_hour': [
            {'hour': r.hour, 'count': r.count}
            for r in by_hour_rows
        ],
    })


# ---------------- 修改申请审核 API ----------------

@admin_api_bp.route('/mod-requests', methods=['GET'])
def list_mod_requests():
    """列出所有修改申请（管理员）"""
    admin, err = _require_admin()
    if err:
        return err
    status_filter = request.args.get('status', 'pending')
    q = ModificationRequest.query
    if status_filter != 'all':
        q = q.filter_by(status=status_filter)
    q = q.order_by(ModificationRequest.created_at.desc()).limit(200)
    return jsonify({
        'requests': [r.to_dict() for r in q.all()],
        'total': q.count(),
    })


@admin_api_bp.route('/mod-requests/<int:req_id>/review', methods=['POST'])
def review_mod_request(req_id):
    """审核修改申请

    body: { action: 'approve' | 'reject', comment: '...' }
    审核通过后系统会执行 payload 中的实际变更
    """
    admin, err = _require_admin()
    if err:
        return err
    req = ModificationRequest.query.get(req_id)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    if req.status != 'pending':
        return jsonify({'error': 'Request already reviewed'}), 409

    data = request.get_json() or {}
    action = data.get('action', '').lower()
    comment = data.get('comment', '')
    if action not in ('approve', 'reject'):
        return jsonify({'error': "action must be 'approve' or 'reject'"}), 400

    req.reviewer_id = admin.id
    req.review_comment = comment
    req.reviewed_at = datetime.utcnow()

    if action == 'approve':
        # 真正执行修改
        from app.models.game import Game
        from app.models.practice import Puzzle
        from app.models.collection import Collection
        from app.models.browsing_history import BrowsingHistory
        from app.models.analysis import Analysis
        import json as _json

        try:
            payload = _json.loads(req.payload_json or '{}')
        except Exception:
            payload = {}

        try:
            if req.target_type == 'game' and req.action == 'delete' and req.target_id:
                g_obj = Game.query.get(req.target_id)
                if g_obj:
                    # 级联清理关联数据，避免外键约束报错
                    Analysis.query.filter_by(game_id=req.target_id).delete()
                    Collection.query.filter_by(game_id=req.target_id).delete()
                    BrowsingHistory.query.filter_by(game_id=req.target_id).delete()
                    Puzzle.query.filter_by(source_game_id=req.target_id).update({'source_game_id': None})
                    db.session.delete(g_obj)
            elif req.target_type == 'game' and req.action == 'create':
                # payload: { source: 'upload'|'paste', filename?, pgn, truncated? }
                pgn_text = payload.get('pgn', '')
                if pgn_text:
                    from app.routes.games import _reconstruct_pgn
                    from app.models.player import Player
                    from app.utils.pgn_parser import PGNParser
                    from app.utils.opening_recognizer import OpeningRecognizer
                    try:
                        games_list = PGNParser.parse_multiple_games(pgn_text)
                    except Exception:
                        games_list = []
                    recognizer = OpeningRecognizer()
                    for game_data in games_list:
                        try:
                            info = game_data.get('game_info', {})
                            white_name = info.get('white', 'Unknown')
                            black_name = info.get('black', 'Unknown')
                            wp = Player.query.filter_by(name=white_name).first()
                            if not wp:
                                wp = Player(name=white_name)
                                db.session.add(wp); db.session.flush()
                            bp = Player.query.filter_by(name=black_name).first()
                            if not bp:
                                bp = Player(name=black_name)
                                db.session.add(bp); db.session.flush()
                            pgn_str = _reconstruct_pgn(info, game_data.get('moves', []))
                            eco_code = info.get('eco', '')
                            opening_name = info.get('opening', '')
                            if not eco_code or not opening_name:
                                moves_san = []
                                for m in game_data.get('moves', []):
                                    if m.get('white'): moves_san.append(m['white'])
                                    if m.get('black'): moves_san.append(m['black'])
                                if moves_san:
                                    oi = recognizer.identify_opening(moves_san)
                                    if oi.get('eco_code'):
                                        eco_code = eco_code or oi['eco_code']
                                        opening_name = opening_name or oi['name']
                            g = Game(
                                white_player_id=wp.id, black_player_id=bp.id,
                                date=info.get('date', ''), result=info.get('result', '*'),
                                pgn_content=pgn_str, eco_code=eco_code,
                                opening_name=opening_name,
                                total_moves=game_data.get('total_moves', 0),
                                final_fen=game_data.get('final_fen', ''),
                                white_elo=info.get('white_elo') or None,
                                black_elo=info.get('black_elo') or None,
                                termination=info.get('termination', ''),
                                time_control=info.get('timecontrol', info.get('time_control', '')),
                            )
                            g.assign_game_number()
                            db.session.add(g)
                        except Exception:
                            pass
            elif req.target_type == 'game' and req.action == 'update' and req.target_id:
                g_obj = Game.query.get(req.target_id)
                if g_obj:
                    allowed = ['date', 'result', 'eco_code', 'opening_name', 'tournament_id']
                    for k in allowed:
                        if k in payload:
                            setattr(g_obj, k, payload[k])
            elif req.target_type == 'puzzle' and req.action == 'delete' and req.target_id:
                p_obj = Puzzle.query.get(req.target_id)
                if p_obj:
                    db.session.delete(p_obj)
            elif req.target_type == 'puzzle' and req.action == 'create':
                # payload: { name, fen, category, difficulty, description, hint }
                p = Puzzle(
                    name=(payload.get('name') or 'Unnamed')[:200],
                    fen=payload.get('fen', ''),
                    category=payload.get('category', 'endgame'),
                    difficulty=payload.get('difficulty', 'medium'),
                    description=(payload.get('description') or '')[:2000],
                    hint=(payload.get('hint') or '')[:500],
                    is_preset=False,
                    created_by=req.user_id,
                )
                db.session.add(p)
            elif req.target_type == 'collection' and req.action == 'delete' and req.target_id:
                c_obj = Collection.query.get(req.target_id)
                if c_obj and c_obj.user_id == req.user_id:
                    db.session.delete(c_obj)
            elif req.target_type == 'collection' and req.action == 'create':
                # payload: { game_id, note? }
                gid = payload.get('game_id')
                if gid and Game.query.get(gid):
                    # 防重复
                    exists = Collection.query.filter_by(user_id=req.user_id, game_id=gid).first()
                    if not exists:
                        c = Collection(user_id=req.user_id, game_id=gid,
                                       note=(payload.get('note') or '')[:500])
                        db.session.add(c)
            req.status = 'approved'
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Apply failed: {e}'}), 500
    else:
        req.status = 'rejected'

    db.session.commit()
    return jsonify(req.to_dict())


@admin_api_bp.route('/mod-requests/<int:req_id>', methods=['GET'])
def get_mod_request(req_id):
    admin, err = _require_admin()
    if err:
        return err
    req = ModificationRequest.query.get(req_id)
    if not req:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(req.to_dict())


# ---------------- 用户管理（仅管理员） ----------------

@admin_api_bp.route('/users', methods=['GET'])
def admin_list_users():
    """用户列表（含每个用户的收藏/浏览/审核数）"""
    admin, err = _require_admin()
    if err:
        return err

    from app.models.collection import Collection
    from app.models.browsing_history import BrowsingHistory
    from sqlalchemy import func

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 200)
    q = request.args.get('q', '', type=str).strip()

    query = User.query
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(User.username.ilike(like), User.email.ilike(like)))

    pagination = query.order_by(User.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    items = []
    for u in pagination.items:
        d = u.to_dict()
        d['collections_count'] = Collection.query.filter_by(user_id=u.id).count()
        d['browsing_count'] = BrowsingHistory.query.filter_by(user_id=u.id).count()
        d['mod_requests_count'] = ModificationRequest.query.filter_by(user_id=u.id).count()
        # 24h 内该用户的 API 调用次数
        from datetime import datetime, timedelta
        since = datetime.utcnow() - timedelta(hours=24)
        d['api_calls_24h'] = ApiAccessLog.query.filter(
            ApiAccessLog.user_id == u.id,
            ApiAccessLog.accessed_at >= since,
        ).count()
        items.append(d)
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
    })


@admin_api_bp.route('/users/<int:user_id>', methods=['PATCH'])
def admin_update_user(user_id):
    """修改用户信息（is_admin / email）"""
    admin, err = _require_admin()
    if err:
        return err

    target = User.query.get(user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json() or {}
    if 'is_admin' in data:
        # 防止最后一个 admin 把自己降级
        if not data['is_admin'] and target.is_admin:
            admin_count = User.query.filter_by(is_admin=True).count()
            if admin_count <= 1:
                return jsonify({'error': 'Cannot demote the last admin'}), 400
        target.is_admin = bool(data['is_admin'])
    if 'email' in data:
        new_email = (data['email'] or '').strip()[:120]
        if '@' not in new_email:
            return jsonify({'error': 'Invalid email'}), 400
        # 唯一性
        exists = User.query.filter(User.email == new_email, User.id != target.id).first()
        if exists:
            return jsonify({'error': 'Email already in use'}), 409
        target.email = new_email

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify(target.to_dict())


@admin_api_bp.route('/users/<int:user_id>/reset_password', methods=['POST'])
def admin_reset_password(user_id):
    """重置用户密码（管理员代重置）"""
    admin, err = _require_admin()
    if err:
        return err

    target = User.query.get(user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json() or {}
    new_pwd = data.get('new_password', '')
    if not isinstance(new_pwd, str) or len(new_pwd) < 6 or len(new_pwd) > 128:
        return jsonify({'error': 'new_password length must be 6-128'}), 400
    target.set_password(new_pwd)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': 'Password reset'})


@admin_api_bp.route('/users/<int:user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    """删除用户（级联清理其收藏/浏览/审核记录）"""
    admin, err = _require_admin()
    if err:
        return err

    if user_id == admin.id:
        return jsonify({'error': 'Cannot delete yourself'}), 400

    target = User.query.get(user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    from app.models.collection import Collection
    from app.models.browsing_history import BrowsingHistory
    from app.models.practice import Puzzle

    try:
        Collection.query.filter_by(user_id=user_id).delete()
        BrowsingHistory.query.filter_by(user_id=user_id).delete()
        # 残局：保留数据但断开 created_by
        Puzzle.query.filter(Puzzle.created_by == user_id).update({'created_by': None, 'is_preset': False})
        ModificationRequest.query.filter_by(user_id=user_id).delete()
        ApiAccessLog.query.filter_by(user_id=user_id).delete()
        db.session.delete(target)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': 'User deleted', 'id': user_id})


@admin_api_bp.route('/stats', methods=['GET'])
def admin_stats():
    """仪表板顶部统计卡（用户/收藏/浏览/审核/调用）"""
    admin, err = _require_admin()
    if err:
        return err
    from app.models.collection import Collection
    from app.models.browsing_history import BrowsingHistory
    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(hours=24)
    return jsonify({
        'users': User.query.count(),
        'admin_count': User.query.filter_by(is_admin=True).count(),
        'collections': Collection.query.count(),
        'browsing': BrowsingHistory.query.count(),
        'pending_mod': ModificationRequest.query.filter_by(status='pending').count(),
        'approved_mod': ModificationRequest.query.filter_by(status='approved').count(),
        'rejected_mod': ModificationRequest.query.filter_by(status='rejected').count(),
        'api_calls_24h': ApiAccessLog.query.filter(ApiAccessLog.accessed_at >= since).count(),
        'errors_24h': ApiAccessLog.query.filter(
            ApiAccessLog.accessed_at >= since,
            ApiAccessLog.status_code >= 400,
        ).count(),
    })


# ---------------- 公开提交修改申请的端点 ----------------

submit_bp = Blueprint('mod_submit', __name__, url_prefix='/api')


@submit_bp.route('/mod-requests', methods=['POST'])
def submit_mod_request():
    """前端用户提交修改申请"""
    from flask_jwt_extended import jwt_required
    from app.models.collection import Collection
    import json as _json

    verify_jwt_in_request()
    identity = get_jwt_identity()
    user = None
    if identity is not None:
        user = User.query.filter_by(username=identity).first()
        if not user:
            try:
                user = User.query.get(int(identity))
            except (TypeError, ValueError):
                user = None
    if not user:
        return jsonify({'error': 'Login required'}), 401

    data = request.get_json() or {}
    target_type = data.get('target_type', '').strip()
    action = data.get('action', '').strip()
    target_id = data.get('target_id')
    reason = data.get('reason', '').strip()
    payload = data.get('payload', {})

    if target_type not in ('game', 'puzzle', 'collection', 'profile', 'player'):
        return jsonify({'error': 'invalid target_type'}), 400
    if action not in ('create', 'update', 'delete'):
        return jsonify({'error': 'invalid action'}), 400

    # 长度 / XSS 校验
    if len(reason) > 500:
        return jsonify({'error': 'reason too long (max 500 chars)'}), 400
    if not isinstance(payload, dict):
        return jsonify({'error': 'payload must be an object'}), 400
    payload_text = _json.dumps(payload, ensure_ascii=False)
    if len(payload_text) > 10_000:
        return jsonify({'error': 'payload too large (max 10KB)'}), 400
    # 基础 XSS 字符过滤
    import re
    for k, v in (payload.items() if isinstance(payload, dict) else []):
        if isinstance(v, str) and re.search(r'<\s*script|javascript\s*:|on\w+\s*=', v, re.IGNORECASE):
            return jsonify({'error': f'payload.{k} contains unsafe content'}), 400
    if re.search(r'<\s*script|javascript\s*:|on\w+\s*=', reason, re.IGNORECASE):
        return jsonify({'error': 'reason contains unsafe content'}), 400

    # 管理员跳过审核，直接生效
    if user.is_admin and target_type != 'puzzle':
        from app.models.game import Game
        from app.models.practice import Puzzle
        try:
            if target_type == 'game' and action == 'delete':
                g_obj = Game.query.get(target_id)
                if g_obj:
                    db.session.delete(g_obj)
                    db.session.commit()
                    return jsonify({'message': '已直接删除（管理员）'})
            elif target_type == 'collection' and action == 'delete':
                c_obj = Collection.query.get(target_id)
                if c_obj and c_obj.user_id == user.id:
                    db.session.delete(c_obj)
                    db.session.commit()
                    return jsonify({'message': '已直接删除（管理员）'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    req = ModificationRequest(
        user_id=user.id,
        target_type=target_type,
        action=action,
        target_id=target_id,
        payload_json=_json.dumps(payload, ensure_ascii=False),
        reason=reason,
        status='pending',
    )
    db.session.add(req)
    db.session.commit()
    return jsonify({'message': '申请已提交，等待管理员审核', 'request': req.to_dict()}), 201


# ---------------- 高级可视化分析端点 ----------------
# 区别于 traffic/summary（仅基础计数），下列端点返回结构化数据用于前端 ECharts 渲染


@admin_api_bp.route('/analytics/heatmap', methods=['GET'])
def analytics_heatmap():
    """端点 × 小时 二维热力图（按时间窗口聚合）

    返回:
      x_axis:  端点列表（按调用量排序取 TOP N）
      y_axis:  24 小时 (0~23)
      matrix:  [[x_idx, y_idx, count], ...]
    """
    admin, err = _require_admin()
    if err:
        return err
    hours = int(request.args.get('hours', 24))
    top = int(request.args.get('top', 30))
    since = datetime.utcnow() - timedelta(hours=hours)

    # 拉取原始记录（限定窗口，最多 5 万条以免内存爆炸）
    rows = db.session.query(
        ApiAccessLog.path, ApiAccessLog.accessed_at
    ).filter(
        ApiAccessLog.accessed_at >= since,
    ).order_by(ApiAccessLog.accessed_at.desc()).limit(50000).all()

    # 端点计数
    path_count = defaultdict(int)
    for r in rows:
        path_count[r.path] += 1
    top_paths = [p for p, _ in sorted(path_count.items(), key=lambda x: -x[1])[:top]]
    if not top_paths:
        return jsonify({'x_axis': [], 'y_axis': list(range(24)), 'matrix': []})

    path_idx = {p: i for i, p in enumerate(top_paths)}
    matrix_map = defaultdict(int)
    for r in rows:
        if r.path in path_idx:
            hh = r.accessed_at.hour
            matrix_map[(path_idx[r.path], hh)] += 1
    matrix = [[k[0], k[1], v] for k, v in matrix_map.items()]
    return jsonify({
        'x_axis': top_paths,
        'y_axis': list(range(24)),
        'matrix': matrix,
        'hours_window': hours,
    })


@admin_api_bp.route('/analytics/user-activity', methods=['GET'])
def analytics_user_activity():
    """用户活跃度时间序列（区分游客 vs 登录用户 vs 管理员）"""
    admin, err = _require_admin()
    if err:
        return err
    hours = int(request.args.get('hours', 24))
    since = datetime.utcnow() - timedelta(hours=hours)

    rows = db.session.query(
        ApiAccessLog.username, ApiAccessLog.user_id, ApiAccessLog.accessed_at
    ).filter(
        ApiAccessLog.accessed_at >= since,
    ).limit(50000).all()

    guest_h = defaultdict(int)
    user_h = defaultdict(int)
    admin_h = defaultdict(int)
    for r in rows:
        hh = r.accessed_at.strftime('%Y-%m-%d %H:00')
        if r.user_id is None:
            guest_h[hh] += 1
        elif r.username and r.username == admin.username:
            admin_h[hh] += 1
        else:
            user_h[hh] += 1

    def _to_list(d):
        return [{'hour': k, 'count': v} for k, v in sorted(d.items())]

    # 在线估算：30 分钟内不同 token 数
    since_online = datetime.utcnow() - timedelta(minutes=30)
    online_tokens = db.session.query(
        func.count(func.distinct(ApiAccessLog.token_fingerprint))
    ).filter(
        ApiAccessLog.accessed_at >= since_online,
        ApiAccessLog.token_fingerprint != '',
    ).scalar() or 0

    return jsonify({
        'series': {
            'guest': _to_list(guest_h),
            'user': _to_list(user_h),
            'admin': _to_list(admin_h),
        },
        'online_estimate': int(online_tokens),
        'hours_window': hours,
    })


@admin_api_bp.route('/analytics/audit-stats', methods=['GET'])
def analytics_audit_stats():
    """申请审核的多维分布：状态分布、类型分布、申请人分布、按日趋势"""
    admin, err = _require_admin()
    if err:
        return err

    days = int(request.args.get('days', 30))
    since = datetime.utcnow() - timedelta(days=days)

    # 拉原始记录后 Python 端分组
    rows = db.session.query(
        ModificationRequest.status,
        ModificationRequest.target_type,
        ModificationRequest.action,
        ModificationRequest.user_id,
        ModificationRequest.created_at,
    ).filter(ModificationRequest.created_at >= since).limit(50000).all()

    by_status = defaultdict(int)
    by_type_action = defaultdict(int)
    by_applicant = defaultdict(int)
    daily = defaultdict(lambda: {'pending': 0, 'approved': 0, 'rejected': 0})

    # 一次性取 username 映射
    user_ids = {r.user_id for r in rows if r.user_id is not None}
    user_map = {}
    if user_ids:
        for u in User.query.filter(User.id.in_(user_ids)).all():
            user_map[u.id] = u.username

    for r in rows:
        by_status[r.status] += 1
        by_type_action[(r.target_type, r.action)] += 1
        uname = user_map.get(r.user_id, f'#{r.user_id}')
        by_applicant[uname] += 1
        day = r.created_at.strftime('%Y-%m-%d')
        if r.status in daily[day]:
            daily[day][r.status] += 1

    by_day = [
        {'date': k, 'pending': v['pending'], 'approved': v['approved'], 'rejected': v['rejected']}
        for k, v in sorted(daily.items())
    ]
    by_status_list = [{'status': s, 'count': c} for s, c in by_status.items()]
    by_type_action_list = [
        {'target_type': t[0], 'action': t[1], 'count': c}
        for t, c in by_type_action.items()
    ]
    by_applicant_list = sorted(
        [{'username': u, 'count': c} for u, c in by_applicant.items()],
        key=lambda x: -x['count']
    )[:10]

    return jsonify({
        'by_status': by_status_list,
        'by_type_action': by_type_action_list,
        'by_applicant': by_applicant_list,
        'by_day': by_day,
        'days_window': days,
    })


@admin_api_bp.route('/analytics/db-changes', methods=['GET'])
def analytics_db_changes():
    """数据库变化速率：写操作 API 排行 + 已批准修改申请"""
    admin, err = _require_admin()
    if err:
        return err
    days = int(request.args.get('days', 14))
    since = datetime.utcnow() - timedelta(days=days)

    write_rows = db.session.query(
        ApiAccessLog.method, ApiAccessLog.path
    ).filter(
        ApiAccessLog.accessed_at >= since,
        ApiAccessLog.method.in_(['POST', 'PUT', 'DELETE', 'PATCH']),
    ).limit(50000).all()
    write_count = defaultdict(int)
    for r in write_rows:
        write_count[(r.method, r.path)] += 1
    write_apis = sorted(
        [{'method': m, 'path': p, 'count': c} for (m, p), c in write_count.items()],
        key=lambda x: -x['count']
    )[:30]

    approved_rows = db.session.query(
        ModificationRequest.target_type, ModificationRequest.action
    ).filter(
        ModificationRequest.status == 'approved',
        ModificationRequest.reviewed_at >= since,
    ).limit(20000).all()
    ap_count = defaultdict(int)
    for r in approved_rows:
        ap_count[(r.target_type, r.action)] += 1
    approved_mods = [
        {'target_type': t[0], 'action': t[1], 'count': c}
        for t, c in ap_count.items()
    ]

    decisions = db.session.query(
        ModificationRequest.status
    ).filter(
        ModificationRequest.created_at >= since,
    ).limit(20000).all()
    dec_count = defaultdict(int)
    for r in decisions:
        dec_count[r.status] += 1

    return jsonify({
        'write_apis': write_apis,
        'approved_mods': approved_mods,
        'decisions': dict(dec_count),
        'days_window': days,
    })


@admin_api_bp.route('/analytics/endpoint-health', methods=['GET'])
def analytics_endpoint_health():
    """端点健康度：每个端点的 P50/P95/99 延迟 + 错误率

    用于散点图（左下角=健康；右上=慢；左下/红色=错误率高）
    """
    admin, err = _require_admin()
    if err:
        return err
    hours = int(request.args.get('hours', 24))
    since = datetime.utcnow() - timedelta(hours=hours)

    rows = db.session.query(
        ApiAccessLog.path,
        ApiAccessLog.duration_ms,
    ).filter(
        ApiAccessLog.accessed_at >= since,
    ).limit(10000).all()

    by_path = defaultdict(list)
    for r in rows:
        by_path[r.path].append(r.duration_ms)

    health = []
    for path, durs in by_path.items():
        if not durs:
            continue
        durs_sorted = sorted(durs)
        n = len(durs_sorted)
        p50 = durs_sorted[n // 2]
        p95 = durs_sorted[min(n - 1, int(n * 0.95))]
        p99 = durs_sorted[min(n - 1, int(n * 0.99))]
        health.append({
            'path': path,
            'count': n,
            'p50_ms': p50,
            'p95_ms': p95,
            'p99_ms': p99,
        })
    health.sort(key=lambda x: -x['count'])
    return jsonify({'endpoints': health[:50], 'hours_window': hours})
