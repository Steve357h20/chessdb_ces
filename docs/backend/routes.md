# 路由层（Routes）

> 8 个 Flask Blueprint，对应 8 个业务域。统一以 `/api/<domain>` 前缀挂载。
>
> 完整 API 参考：[docs/API.md](../API.md)

## 总览

| Blueprint | 前缀 | 文件 | 端点数 | 主要职责 |
|-----------|------|------|--------|----------|
| `auth_bp` | `/api/auth` | [auth.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/auth.py) | 5 | 注册、登录、用户资料 |
| `games_bp` | `/api/games` | [games.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/games.py) | 9 | 棋谱 CRUD、上传、导出 |
| `players_bp` | `/api/players` | [players.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/players.py) | 7 | 棋手档案、统计 |
| `openings_bp` | `/api/openings` | [openings.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/openings.py) | 6 | 开局库、识别、相似 |
| `analysis_bp` | `/api/analysis` | [analysis.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/analysis.py) | 6 | 同步/异步分析、任务 |
| `practice_bp` | `/api/practice` | [practice.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/practice.py) | 15 | 残局、对弈、复盘 |
| `collections_bp` | `/api/collections` | [collections.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/collections.py) | 5 | 收藏 |
| `browsing_bp` | `/api/browsing` | [browsing.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/browsing.py) | 4 | 浏览历史 |
| `tournaments_bp` | `/api/tournaments` | [tournaments.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/tournaments.py) | 6 | 赛事 |
| `modification_bp` | `/api/modification-requests` | [modification_requests.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/modification_requests.py) | 4 | 修改申请 |
| `traffic_bp` | `/api/admin` | [traffic.py](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/traffic.py) | 10 | 流量监控、审核 |

## 1. 认证 auth_bp

```python
from flask import Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    """注册"""
    data = request.get_json()
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': '用户名已存在'}), 409
    user = User(username=data['username'], email=data['email'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("100 per hour")
def login():
    """登录"""
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'error': '用户名或密码错误'}), 401
    token = create_access_token(identity=user.id)
    user.last_login_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'access_token': token, 'user': user.to_dict()}), 200

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    """当前用户"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return jsonify(user.to_dict())

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """修改密码"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json()
    if not user.check_password(data['old_password']):
        return jsonify({'error': '原密码错误'}), 422
    user.set_password(data['new_password'])
    db.session.commit()
    return jsonify({'message': '密码修改成功'}), 200
```

**权限**：
- `register` / `login` - 公开
- `me` / `profile` / `change-password` - 用户

## 2. 棋谱 games_bp

```python
games_bp = Blueprint('games', __name__, url_prefix='/api/games')

@games_bp.route('/', methods=['GET'])
@jwt_required(optional=True)
def list_games():
    """棋谱列表（分页、搜索、过滤）"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    q = request.args.get('q', '')
    eco = request.args.get('eco')

    query = Game.query
    if q:
        query = query.join(Player, Game.white_player_id == Player.id).filter(
            or_(Player.name.contains(q), Game.event.contains(q))
        )
    if eco:
        query = query.filter(Game.eco_code == eco)

    pagination = query.order_by(Game.date.desc()).paginate(page=page, per_page=per_page)
    return jsonify({
        'games': [g.to_dict() for g in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
    })

@games_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_pgn():
    """上传 PGN 文件批量导入"""
    file = request.files.get('file')
    if not file:
        return jsonify({'error': '请上传文件'}), 400

    parser = PGNParser()
    text = file.read().decode('utf-8', errors='ignore')
    games, errors = parser.parse_multiple(text)

    # 创建关联棋手
    for g in games:
        _ensure_player(g['white_player'])
        _ensure_player(g['black_player'])

    imported = len(Game.__bulk_insert([...]))
    return jsonify({'imported': imported, 'errors': errors}), 201

@games_bp.route('/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_game(id):
    """删除棋谱（提交审核或直接）"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.is_admin:
        # 管理员直接删除
        game = Game.query.get_or_404(id)
        db.session.delete(game)
        db.session.commit()
        return jsonify({'message': '删除成功'})
    else:
        # 普通用户提交申请
        req = ModificationRequest(
            user_id=user_id,
            target_type='game',
            action='delete',
            target_id=id,
            reason=request.json.get('reason', ''),
        )
        db.session.add(req)
        db.session.commit()
        return jsonify({'message': '删除申请已提交', 'request_id': req.id}), 202
```

**关键设计**：
- 危险操作（删除/修改）由 `ModificationRequest` 工作流保护
- 管理员可绕过审核，普通用户需审批
- PGN 上传支持批量导入，自动去重棋手

## 3. 棋手 players_bp

```python
@players_bp.route('/<int:id>/stats', methods=['GET'])
@jwt_required()
def player_stats(id):
    """棋手对局统计"""
    player = Player.query.get_or_404(id)
    white_games = Game.query.filter_by(white_player_id=id).all()
    black_games = Game.query.filter_by(black_player_id=id).all()

    wins_white = sum(1 for g in white_games if g.result == '1-0')
    wins_black = sum(1 for g in black_games if g.result == '0-1')
    draws = sum(1 for g in white_games + black_games if g.result == '1/2-1/2')

    return jsonify({
        'total_games': len(white_games) + len(black_games),
        'wins_as_white': wins_white,
        'wins_as_black': wins_black,
        'draws': draws,
        'win_rate': (wins_white + wins_black) / max(1, len(white_games) + len(black_games)),
        'favorite_openings': _player_favorite_openings(id),
    })
```

## 4. 开局 openings_bp

```python
@openings_bp.route('/rec', methods=['GET'])
@jwt_required()
def recognize_opening():
    """识别开局（输入 moves 列表）"""
    moves = request.args.getlist('moves')  # ['e4', 'e5', 'Nf3']
    recognizer = OpeningRecognizer()
    opening = recognizer.recognize(moves)
    if not opening:
        return jsonify({'eco_code': None, 'name': 'Unknown'}), 200
    return jsonify(opening.to_dict())

@openings_bp.route('/tree', methods=['GET'])
@jwt_required()
def opening_tree():
    """开局树（前 N 步）"""
    max_depth = request.args.get('depth', 6, type=int)
    tree = OpeningRecognizer().build_tree(max_depth)
    return jsonify({'tree': tree})
```

**识别算法**：
- 加载 `openings` 表，遍历每条记录的 `moves` JSON
- 与输入 moves 列表前缀匹配
- 返回最长匹配项

## 5. 分析 analysis_bp

```python
@analysis_bp.route('/async', methods=['POST'])
@jwt_required()
@limiter.limit("10 per hour")
def async_analysis():
    """提交异步分析任务"""
    data = request.get_json()
    user_id = get_jwt_identity()

    task = AnalysisTask(
        id=str(uuid.uuid4()),
        game_id=data['game_id'],
        user_id=user_id,
        status='pending',
        depth=data.get('depth', 20),
        threads=data.get('threads', 1),
    )
    db.session.add(task)
    db.session.commit()

    # 启动后台线程
    threading.Thread(
        target=run_analysis_task,
        args=(app, task.id),
        daemon=True
    ).start()

    return jsonify({'task_id': task.id, 'status': 'pending'}), 202

@analysis_bp.route('/tasks/<task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    """查询任务状态"""
    task = AnalysisTask.query.get_or_404(task_id)
    user_id = get_jwt_identity()
    if task.user_id != user_id and not User.query.get(user_id).is_admin:
        return jsonify({'error': '无权访问'}), 403
    return jsonify(task.to_dict())
```

**后台任务实现** `run_analysis_task`：

```python
def run_analysis_task(app, task_id):
    """后台线程执行分析"""
    with app.app_context():
        task = AnalysisTask.query.get(task_id)
        task.status = 'running'
        db.session.commit()

        try:
            analyzer = StockfishAnalyzer()
            game = Game.query.get(task.game_id)
            result = asyncio.run(analyzer.analyze_game(
                game.pgn_content,
                depth=task.depth,
                threads=task.threads,
            ))

            # 写 analyses 表
            analysis = Analysis(
                game_id=task.game_id,
                analysis_data=result,
                depth=task.depth,
            )
            db.session.add(analysis)

            task.status = 'completed'
            task.progress = 100
            task.result = {'analysis_id': analysis.id}
            db.session.commit()
        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
            db.session.commit()
```

## 6. 练习 practice_bp

```python
@practice_bp.route('/games', methods=['POST'])
@jwt_required()
def start_practice():
    """开始练习对局"""
    data = request.get_json()
    user_id = get_jwt_identity()

    pg = PracticeGame(
        user_id=user_id,
        mode=data['mode'],                      # ai / puzzle / game
        difficulty=data.get('difficulty'),
        puzzle_id=data.get('puzzle_id'),
        starting_fen=data.get('starting_fen'),
        user_color=data.get('user_color', 'white'),
        result='ongoing',
    )
    db.session.add(pg)
    db.session.commit()

    return jsonify(pg.to_dict()), 201

@practice_bp.route('/games/<int:id>/moves', methods=['POST'])
@jwt_required()
def make_move(id):
    """提交着法"""
    pg = PracticeGame.query.get_or_404(id)
    if pg.user_id != get_jwt_identity():
        return jsonify({'error': '无权操作'}), 403

    data = request.get_json()
    move_san = data['move']  # SAN 格式
    want_ai = data.get('ai_response', True)

    # 应用玩家着法
    board = chess.Board(pg.current_fen())
    move = board.parse_san(move_san)
    board.push(move)
    user_move = {'san': move_san, 'fen_after': board.fen()}

    # AI 回手
    ai_move = None
    if want_ai and not board.is_game_over():
        ai = AIPlayer(difficulty=pg.difficulty)
        ai_move_obj, eval_score = ai.get_move(board)
        board.push(ai_move_obj)
        ai_move = {
            'san': board.san(ai_move_obj),
            'fen_after': board.fen(),
            'evaluation': eval_score,
        }

    # 落库
    moves = pg.moves_json or []
    moves.append({'user': user_move, 'ai': ai_move})
    pg.moves_json = moves
    pg.current_fen = board.fen()
    if board.is_game_over():
        pg.result = _determine_result(board, pg.user_color)
        pg.ended_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'user_move': user_move,
        'ai_move': ai_move,
        'status': pg.result,
    })

@practice_bp.route('/games/<int:id>/review', methods=['GET'])
@jwt_required()
def review(id):
    """获取复盘分析"""
    pg = PracticeGame.query.get_or_404(id)
    if not pg.review_data:
        # 触发分析
        analyzer = StockfishAnalyzer()
        review = asyncio.run(analyzer.review_game(pg.moves_json, pg.user_color))
        pg.review_data = review
        db.session.commit()
    return jsonify(pg.review_data)
```

**复盘评价算法**（基于胜率变化）：

```python
def label_move(win_rate_delta):
    if win_rate_delta > 0.20:   return ('brilliant', '妙手')
    if win_rate_delta > 0.05:   return ('good',       '好着')
    if win_rate_delta > -0.05:  return ('neutral',    '中规中矩')
    if win_rate_delta > -0.20:  return ('inaccuracy', '失误')
    return ('blunder', '漏着')
```

## 7. 收藏 collections_bp

```python
@collections_bp.route('/', methods=['POST'])
@jwt_required()
def add_collection():
    """添加收藏（防重复）"""
    user_id = get_jwt_identity()
    data = request.get_json()

    existing = Collection.query.filter_by(
        user_id=user_id, game_id=data['game_id']
    ).first()
    if existing:
        return jsonify({'error': '已经收藏过了'}), 409

    c = Collection(
        user_id=user_id,
        game_id=data['game_id'],
        note=data.get('note', ''),
    )
    db.session.add(c)
    db.session.commit()
    return jsonify(c.to_dict()), 201
```

**唯一约束** `(user_id, game_id)` 防止重复。

## 8. 浏览历史 browsing_bp

```python
@browsing_bp.route('/', methods=['POST'])
@jwt_required()
def record():
    """记录浏览（重复浏览刷新时间）"""
    user_id = get_jwt_identity()
    data = request.get_json()

    h = BrowsingHistory.query.filter_by(
        user_id=user_id, game_id=data['game_id']
    ).first()
    if h:
        h.viewed_at = datetime.utcnow()
    else:
        h = BrowsingHistory(
            user_id=user_id,
            game_id=data['game_id'],
        )
        db.session.add(h)
    db.session.commit()
    return jsonify(h.to_dict())
```

## 9. 赛事 tournaments_bp

参见完整 API 文档。

## 10. 修改审核 modification_bp

```python
@modification_bp.route('/', methods=['POST'])
@jwt_required()
def create_request():
    """提交修改申请"""
    user_id = get_jwt_identity()
    data = request.get_json()

    req = ModificationRequest(
        user_id=user_id,
        target_type=data['target_type'],
        target_id=data['target_id'],
        action=data['action'],
        payload_json=json.dumps(data.get('payload', {})),
        reason=data.get('reason', ''),
        status='pending',
    )
    db.session.add(req)
    db.session.commit()
    return jsonify(req.to_dict()), 201
```

## 11. 管理 traffic_bp

```python
traffic_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@traffic_bp.route('/traffic', methods=['GET'])
@admin_required
def traffic_summary():
    """流量统计"""
    total = ApiAccessLog.query.count()
    error_count = ApiAccessLog.query.filter(ApiAccessLog.status_code >= 400).count()
    avg_duration = db.session.query(func.avg(ApiAccessLog.duration_ms)).scalar() or 0

    # Top endpoints
    top_paths = db.session.query(
        ApiAccessLog.path, func.count(ApiAccessLog.id)
    ).group_by(ApiAccessLog.path).order_by(func.count(ApiAccessLog.id).desc()).limit(10).all()

    return jsonify({
        'summary': {
            'total_requests': total,
            'error_rate': error_count / max(1, total),
            'avg_duration_ms': int(avg_duration),
        },
        'top_endpoints': [{'path': p, 'count': c} for p, c in top_paths],
    })

@traffic_bp.route('/requests/<int:id>/approve', methods=['POST'])
@admin_required
def approve_request(id):
    """通过申请"""
    req = ModificationRequest.query.get_or_404(id)
    if req.status != 'pending':
        return jsonify({'error': '该申请已处理'}), 409

    # 执行业务
    try:
        _execute_modification(req)
        req.status = 'approved'
        req.reviewer_id = get_jwt_identity()
        req.review_comment = request.json.get('comment', '')
        req.reviewed_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'message': '已通过', 'request': req.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
```

`admin_required` 装饰器：

```python
def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return jsonify({'error': '需要管理员权限'}), 403
        return fn(*args, **kwargs)
    return wrapper
```

## 注册入口

```python
# app/__init__.py
def register_blueprints(app):
    from app.routes.auth import auth_bp
    from app.routes.games import games_bp
    from app.routes.players import players_bp
    from app.routes.openings import openings_bp
    from app.routes.analysis import analysis_bp
    from app.routes.practice import practice_bp
    from app.routes.collections import collections_bp
    from app.routes.browsing import browsing_bp
    from app.routes.tournaments import tournaments_bp
    from app.routes.modification_requests import modification_bp
    from app.routes.traffic import traffic_bp

    for bp in [auth_bp, games_bp, players_bp, openings_bp,
               analysis_bp, practice_bp, collections_bp, browsing_bp,
               tournaments_bp, modification_bp, traffic_bp]:
        app.register_blueprint(bp)
```

## 路由清单

总计约 75 个端点。可通过 `flask routes` 命令查看完整列表。
