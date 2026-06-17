import json
import logging
import threading
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models.practice import PracticeGame, Puzzle
from app.models.user import User
from app.services.ai_player import PracticeSession, PracticeError

logger = logging.getLogger(__name__)

practice_bp = Blueprint('practice', __name__)

sessions = {}


def _get_stockfish_path():
    path = current_app.config.get('STOCKFISH_PATH', 'stockfish')
    logger.info('Stockfish path from config: %s', path)
    return path


def _save_session_to_db(session_obj, user_id=None, puzzle_id=None):
    data = session_obj.to_dict()
    if not data.get('active', False) and not data.get('result'):
        return None

    pg = PracticeGame(
        user_id=user_id,
        mode=data.get('source', 'custom'),
        puzzle_id=puzzle_id,
        source_game_id=data.get('source_id'),
        start_fen=data.get('start_fen', ''),
        user_color='w' if data.get('user_color') == 'white' else 'b',
        difficulty=data.get('difficulty', 'medium'),
        moves_json=json.dumps(data.get('history', [])),
        final_fen=data.get('fen', ''),
        result=data.get('result', '*'),
        total_moves=len(data.get('history', [])),
        hints_used=data.get('hints_used', 0),
        undo_count=data.get('undo_count', 0),
    )
    db.session.add(pg)

    if puzzle_id:
        puzzle = Puzzle.query.get(puzzle_id)
        if puzzle:
            puzzle.practice_count = (puzzle.practice_count or 0) + 1
            if data.get('result') and data.get('user_color') == 'w' and data.get('result') == '1-0':
                puzzle.solve_count = (puzzle.solve_count or 0) + 1
            elif data.get('result') and data.get('user_color') == 'b' and data.get('result') == '0-1':
                puzzle.solve_count = (puzzle.solve_count or 0) + 1

    db.session.commit()
    return pg


@practice_bp.route('/puzzles', methods=['GET'])
def list_puzzles():
    """
    获取残局列表
    ---
    tags:
      - 练习管理
    parameters:
      - name: category
        in: query
        type: string
        description: 分类筛选
      - name: difficulty
        in: query
        type: string
        description: 难度筛选
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 50
    responses:
      200:
        description: 残局列表
    """
    category = request.args.get('category', '').strip()
    difficulty = request.args.get('difficulty', '').strip()
    source_game_id = request.args.get('source_game_id', type=int)
    only_mine = request.args.get('only_mine', '').lower() in ('1', 'true', 'yes')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 100)

    # 个性化逻辑：识别当前登录用户，未登录只能看预设
    from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
    current_user = None
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity is not None:
            current_user = User.query.filter_by(username=identity).first()
            if not current_user:
                try:
                    current_user = User.query.get(int(identity))
                except (TypeError, ValueError):
                    current_user = None
    except Exception:
        current_user = None

    q = Puzzle.query
    if category:
        q = q.filter_by(category=category)
    if difficulty:
        q = q.filter_by(difficulty=difficulty)
    if source_game_id:
        q = q.filter_by(source_game_id=source_game_id)

    if only_mine:
        # 明确只看"我的"个性化残局（未登录则返回空）
        if current_user:
            q = q.filter(Puzzle.created_by == current_user.id)
        else:
            return jsonify({
                'puzzles': [],
                'total': 0,
                'page': page,
                'per_page': per_page,
                'pages': 0,
                'current_user_id': None,
            })
    else:
        # 默认：系统预设 OR 当前用户自建（多用户隔离）
        if current_user:
            q = q.filter(db.or_(
                Puzzle.is_preset.is_(True),
                Puzzle.created_by == current_user.id,
            ))
        else:
            q = q.filter(Puzzle.is_preset.is_(True))

    q = q.order_by(Puzzle.is_preset.desc(), Puzzle.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'puzzles': [p.to_dict(include_source=True) for p in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
        'current_user_id': current_user.id if current_user else None,
    })


@practice_bp.route('/puzzles/<int:puzzle_id>', methods=['GET'])
def get_puzzle_detail(puzzle_id):
    """
    获取残局详情
    ---
    tags:
      - 练习管理
    parameters:
      - name: puzzle_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: 残局详情
      404:
        description: 残局不存在
    """
    puzzle = Puzzle.query.get(puzzle_id)
    if not puzzle:
        return jsonify({'error': 'Puzzle not found'}), 404
    data = puzzle.to_dict(include_source=True)
    practice_records = PracticeGame.query.filter_by(puzzle_id=puzzle_id).order_by(PracticeGame.created_at.desc()).limit(20).all()
    data['practice_records'] = [pg.to_dict() for pg in practice_records]
    return jsonify(data)


@practice_bp.route('/puzzles', methods=['POST'])
@jwt_required()
def create_puzzle():
    """
    创建残局
    普通用户 → 提交修改申请，管理员审核后创建
    管理员 → 直接创建
    ---
    tags:
      - 练习管理
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - fen
            - name
          properties:
            fen:
              type: string
            name:
              type: string
            category:
              type: string
            difficulty:
              type: string
            description:
              type: string
            hint:
              type: string
    responses:
      201:
        description: 创建成功
      400:
        description: 参数错误
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    fen = data.get('fen', '').strip()
    name = data.get('name', '').strip()

    if not fen:
        return jsonify({'error': 'FEN is required'}), 400
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    import chess
    try:
        chess.Board(fen)
    except ValueError as e:
        return jsonify({'error': f'Invalid FEN: {e}'}), 400

    identity = get_jwt_identity()
    # 兼容 username（旧） 与 user_id（str/int，新）
    user = None
    if identity is not None:
        user = User.query.filter_by(username=identity).first()
        if not user:
            try:
                user = User.query.get(int(identity))
            except (TypeError, ValueError):
                user = None

    if not user:
        return jsonify({'error': 'User not found'}), 401

    # 普通用户：提交修改申请
    if not user.is_admin:
        from app.models.admin_models import ModificationRequest
        import json as _json
        payload = {
            'name': name[:200],
            'fen': fen,
            'category': data.get('category', 'endgame'),
            'difficulty': data.get('difficulty', 'medium'),
            'description': (data.get('description') or '')[:2000],
            'hint': (data.get('hint') or '')[:500],
            'source_game_id': data.get('source_game_id'),
            'from_move': data.get('from_move'),
        }
        req = ModificationRequest(
            user_id=user.id,
            target_type='puzzle',
            action='create',
            target_id=None,
            payload_json=_json.dumps(payload, ensure_ascii=False),
            reason=f'创建残局: {name}',
            status='pending',
        )
        db.session.add(req)
        db.session.commit()
        return jsonify({
            'message': '已提交残局创建申请，等待管理员审核',
            'need_review': True,
        }), 202

    # 管理员：直接创建
    puzzle = Puzzle(
        name=name,
        category=data.get('category', 'endgame'),
        difficulty=data.get('difficulty', 'medium'),
        description=data.get('description', ''),
        hint=data.get('hint', ''),
        fen=fen,
        source_game_id=data.get('source_game_id'),
        from_move=data.get('from_move'),
        created_by=user.id,
        is_preset=False,
    )
    puzzle.assign_puzzle_number()
    db.session.add(puzzle)
    db.session.commit()

    return jsonify(puzzle.to_dict(include_source=True)), 201


@practice_bp.route('/puzzles/<int:puzzle_id>', methods=['DELETE'])
@jwt_required()
def delete_puzzle(puzzle_id):
    puzzle = Puzzle.query.get(puzzle_id)
    if not puzzle:
        return jsonify({'error': 'Puzzle not found'}), 404

    if puzzle.is_preset:
        return jsonify({'error': 'Cannot delete preset puzzle'}), 403

    identity = get_jwt_identity()
    user = None
    if identity is not None:
        user = User.query.filter_by(username=identity).first()
        if not user:
            try:
                user = User.query.get(int(identity))
            except (TypeError, ValueError):
                user = None
    if not user or (puzzle.created_by != user.id and not user.is_admin):
        return jsonify({'error': 'Permission denied'}), 403

    db.session.delete(puzzle)
    db.session.commit()
    return jsonify({'message': 'Puzzle deleted'})


@practice_bp.route('/search_games', methods=['GET'])
def search_games():
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 100)

    from app.models.game import Game
    from app.models.player import Player
    from sqlalchemy.orm import joinedload

    q = Game.query.options(joinedload(Game.white_player), joinedload(Game.black_player))
    if query:
        sp = db.session.query(Player.id).filter(Player.name.ilike(f'%{query}%')).subquery()
        q = q.filter(db.or_(
            Game.white_player_id.in_(sp),
            Game.black_player_id.in_(sp),
            Game.opening_name.ilike(f'%{query}%'),
        ))
    q = q.order_by(Game.created_at.desc()).limit(limit)
    games = q.all()

    results = []
    for g in games:
        results.append({
            'id': g.id,
            'white_player_name': g.white_player.name if g.white_player else '?',
            'black_player_name': g.black_player.name if g.black_player else '?',
            'white_elo': g.white_elo,
            'black_elo': g.black_elo,
            'date': g.date,
            'result': g.result,
            'eco_code': g.eco_code,
            'opening_name': g.opening_name,
            'total_moves': g.total_moves,
        })
    return jsonify({'games': results, 'total': len(results)})


@practice_bp.route('/start', methods=['POST'])
@jwt_required(optional=True)
def start_session():
    """
    开始练习对局
    ---
    tags:
      - 练习管理
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            mode:
              type: string
              enum: [custom, puzzle, from_game]
              default: custom
            user_color:
              type: string
              default: white
            difficulty:
              type: string
              default: medium
            puzzle_id:
              type: integer
            game_id:
              type: integer
            from_move:
              type: integer
            custom_fen:
              type: string
    responses:
      200:
        description: 对局会话已创建
      400:
        description: 参数错误
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    mode = data.get('mode', 'custom')
    user_color = data.get('user_color', 'white')
    difficulty = data.get('difficulty', 'medium')
    puzzle_id = data.get('puzzle_id')
    game_id = data.get('game_id')
    from_move = data.get('from_move', 0)
    custom_fen = data.get('custom_fen', '')

    stockfish_path = _get_stockfish_path()
    session_obj = PracticeSession(stockfish_path)

    db_puzzle_id = None

    try:
        if mode == 'puzzle':
            if puzzle_id:
                puzzle = Puzzle.query.get(int(puzzle_id))
                if not puzzle:
                    return jsonify({'error': f'Puzzle not found: {puzzle_id}'}), 404
                fen = puzzle.fen
                db_puzzle_id = puzzle.id
            else:
                return jsonify({'error': 'puzzle_id required for puzzle mode'}), 400
            result = session_obj.start_from_fen(fen, user_color, difficulty)
            session_obj._source = 'puzzle'
            session_obj._source_id = db_puzzle_id
        elif mode == 'from_game':
            if not game_id:
                return jsonify({'error': 'game_id required for from_game mode'}), 400
            result = session_obj.start_from_game(game_id, from_move, user_color, difficulty)
        elif mode == 'custom':
            fen = custom_fen or 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
            result = session_obj.start_from_fen(fen, user_color, difficulty)
        else:
            return jsonify({'error': f'Invalid mode: {mode}'}), 400
    except PracticeError as e:
        session_obj.close()
        return jsonify({'error': str(e)}), 400

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        'session': session_obj,
        'user_id': None,
        'puzzle_id': db_puzzle_id,
        'started_at': datetime.utcnow(),
    }

    user_id = None
    try:
        identity = get_jwt_identity()
        if identity:
            user = User.query.get(int(identity))
            if user:
                user_id = user.id
                sessions[session_id]['user_id'] = user_id
    except Exception:
        pass

    return jsonify({
        'session_id': session_id,
        'mode': mode,
        'puzzle_id': db_puzzle_id,
        'fen': result.get('fen', ''),
        'start_fen': result.get('fen', ''),
        'is_user_turn': result.get('is_user_turn', True),
        'user_color': user_color,
        'difficulty': difficulty,
    })


@practice_bp.route('/move', methods=['POST'])
def make_move():
    """
    练习对局走子
    ---
    tags:
      - 练习管理
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - session_id
            - move
          properties:
            session_id:
              type: string
            move:
              type: string
              description: SAN格式着法
    responses:
      200:
        description: 走子结果
      400:
        description: 非法着法
      410:
        description: 会话已过期
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    session_id = data.get('session_id')
    move_san = data.get('move')

    if not session_id or not move_san:
        return jsonify({'error': 'session_id and move required'}), 400

    entry = sessions.get(session_id)
    if not entry:
        return jsonify({'error': 'session_expired', 'detail': '对局会话已过期，请重新开始对局'}), 410

    session_obj = entry['session']
    try:
        result = session_obj.user_move(move_san)
    except PracticeError as e:
        return jsonify({'error': str(e)}), 400

    if result.get('is_game_over'):
        _save_session_to_db(session_obj, entry.get('user_id'), entry.get('puzzle_id'))
        session_obj.close()
        sessions.pop(session_id, None)

    result['fen'] = result.get('new_fen', result.get('fen', ''))
    result['is_user_turn'] = not result.get('is_game_over', False)

    return jsonify(result)


@practice_bp.route('/undo', methods=['POST'])
def undo():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400

    entry = sessions.get(session_id)
    if not entry:
        return jsonify({'error': 'session_expired', 'detail': '对局会话已过期，请重新开始对局'}), 410

    session_obj = entry['session']
    try:
        result = session_obj.undo_move()
    except PracticeError as e:
        return jsonify({'error': str(e)}), 400

    result['fen'] = result.get('new_fen', result.get('fen', ''))

    return jsonify(result)


@practice_bp.route('/hint', methods=['POST'])
def hint():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400

    entry = sessions.get(session_id)
    if not entry:
        return jsonify({'error': 'session_expired', 'detail': '对局会话已过期，请重新开始对局'}), 410

    session_obj = entry['session']
    try:
        result = session_obj.get_hint()
    except PracticeError as e:
        return jsonify({'error': str(e)}), 400

    return jsonify(result)


@practice_bp.route('/resign', methods=['POST'])
def resign():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400

    entry = sessions.get(session_id)
    if not entry:
        return jsonify({'error': 'session_expired', 'detail': '对局会话已过期，请重新开始对局'}), 410

    session_obj = entry['session']
    try:
        result = session_obj.resign()
    except PracticeError as e:
        return jsonify({'error': str(e)}), 400

    _save_session_to_db(session_obj, entry.get('user_id'), entry.get('puzzle_id'))
    session_obj.close()
    sessions.pop(session_id, None)

    return jsonify(result)


@practice_bp.route('/status/<session_id>', methods=['GET'])
def get_status(session_id):
    entry = sessions.get(session_id)
    if not entry:
        return jsonify({'error': 'session_expired', 'detail': '对局会话已过期'}), 410

    session_obj = entry['session']
    return jsonify(session_obj.get_status())


@practice_bp.route('/history', methods=['GET'])
@jwt_required(optional=True)
def get_history():
    """
    获取练习历史
    ---
    tags:
      - 练习管理
    security:
      - Bearer: []
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 20
      - name: difficulty
        in: query
        type: string
      - name: mode
        in: query
        type: string
      - name: result
        in: query
        type: string
        description: win/lose/draw
    responses:
      200:
        description: 练习历史列表
    """
    identity = get_jwt_identity()
    if identity:
        user = User.query.get(int(identity))
        if not user:
            return jsonify({'error': 'User not found'}), 404
        user_id = user.id
    else:
        user_id = None

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)

    if user_id:
        query = PracticeGame.query.filter_by(user_id=user_id)
    else:
        query = PracticeGame.query

    difficulty = request.args.get('difficulty', '').strip()
    if difficulty:
        query = query.filter(PracticeGame.difficulty == difficulty)

    mode = request.args.get('mode', '').strip()
    if mode:
        query = query.filter(PracticeGame.mode == mode)

    result = request.args.get('result', '').strip()
    if result:
        if result == 'win':
            query = query.filter(
                db.or_(
                    db.and_(PracticeGame.result == '1-0', PracticeGame.user_color == 'w'),
                    db.and_(PracticeGame.result == '0-1', PracticeGame.user_color == 'b'),
                )
            )
        elif result == 'lose':
            query = query.filter(
                db.or_(
                    db.and_(PracticeGame.result == '0-1', PracticeGame.user_color == 'w'),
                    db.and_(PracticeGame.result == '1-0', PracticeGame.user_color == 'b'),
                )
            )
        elif result == 'draw':
            query = query.filter(PracticeGame.result == '1/2-1/2')

    sort = request.args.get('sort', 'created_at').strip()
    order = request.args.get('order', 'desc').strip()

    sort_map = {
        'created_at': PracticeGame.created_at,
        'difficulty': PracticeGame.difficulty,
        'total_moves': PracticeGame.total_moves,
        'hints_used': PracticeGame.hints_used,
    }
    sort_col = sort_map.get(sort, PracticeGame.created_at)

    if order == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'history': [pg.to_dict() for pg in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
    })


@practice_bp.route('/history/<int:practice_id>', methods=['GET'])
@jwt_required(optional=True)
def get_history_detail(practice_id):
    pg = PracticeGame.query.get(practice_id)
    if not pg:
        return jsonify({'error': 'Practice game not found'}), 404

    identity = get_jwt_identity()
    if identity and pg.user_id:
        user = User.query.get(int(identity))
        if not user or pg.user_id != user.id:
            return jsonify({'error': 'Practice game not found'}), 404

    return jsonify(pg.to_dict())


_practice_analysis_tasks = {}


@practice_bp.route('/analyze/<int:practice_id>', methods=['POST'])
@jwt_required(optional=True)
def analyze_practice(practice_id):
    pg = PracticeGame.query.get(practice_id)
    if not pg:
        return jsonify({'error': 'Practice game not found'}), 404

    identity = get_jwt_identity()
    if identity and pg.user_id:
        user = User.query.get(int(identity))
        if not user or pg.user_id != user.id:
            return jsonify({'error': 'Practice game not found'}), 404

    moves = []
    if pg.moves_json:
        try:
            moves = json.loads(pg.moves_json)
        except (json.JSONDecodeError, TypeError):
            moves = []

    if not moves:
        return jsonify({'error': 'No moves to analyze'}), 400

    for tid, task in _practice_analysis_tasks.items():
        if task.get('practice_id') == practice_id and task.get('status') in ('pending', 'running'):
            return jsonify({
                'message': 'Analysis already in progress',
                'task_id': tid,
                'practice_id': practice_id,
            })

    task_id = str(uuid.uuid4())
    _practice_analysis_tasks[task_id] = {
        'task_id': task_id,
        'practice_id': practice_id,
        'status': 'pending',
        'progress': 0.0,
        'result': None,
        'error': None,
    }

    app = current_app._get_current_object()
    start_fen = pg.start_fen or 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
    thread = threading.Thread(
        target=_run_practice_analysis,
        args=(task_id, practice_id, start_fen, moves, app),
        daemon=True,
    )
    thread.start()

    return jsonify({
        'message': 'Analysis started',
        'task_id': task_id,
        'practice_id': practice_id,
    })


@practice_bp.route('/analyze/<int:practice_id>/status', methods=['GET'])
@jwt_required(optional=True)
def get_practice_analysis_status(practice_id):
    for tid, task in _practice_analysis_tasks.items():
        if task.get('practice_id') == practice_id:
            return jsonify({
                'task_id': tid,
                'practice_id': practice_id,
                'status': task.get('status', 'unknown'),
                'progress': task.get('progress', 0.0),
                'result': task.get('result'),
                'error': task.get('error'),
            })

    pg = PracticeGame.query.get(practice_id)
    if pg and pg.analysis_json:
        return jsonify({
            'practice_id': practice_id,
            'status': 'completed',
            'progress': 1.0,
            'cached': True,
        })

    return jsonify({
        'practice_id': practice_id,
        'status': 'none',
        'progress': 0.0,
    })


@practice_bp.route('/analyze/<int:practice_id>/result', methods=['GET'])
@jwt_required(optional=True)
def get_practice_analysis_result(practice_id):
    pg = PracticeGame.query.get(practice_id)
    if not pg:
        return jsonify({'error': 'Practice game not found'}), 404

    if not pg.analysis_json:
        return jsonify({'error': 'No analysis available'}), 404

    try:
        analysis = json.loads(pg.analysis_json)
    except (json.JSONDecodeError, TypeError):
        return jsonify({'error': 'Invalid analysis data'}), 500

    return jsonify({
        'practice_id': practice_id,
        'analysis': analysis,
    })


def _run_practice_analysis(task_id, practice_id, start_fen, moves, app):
    with app.app_context():
        task = _practice_analysis_tasks.get(task_id)
        if not task:
            return

        task['status'] = 'running'

        from app.services.stockfish_analyzer import StockfishAnalyzer

        stockfish_path = app.config.get('STOCKFISH_PATH', 'stockfish')
        depth = app.config.get('ANALYSIS_DEPTH', 20)
        threads = app.config.get('ANALYSIS_THREADS', 1)
        hash_size = app.config.get('ANALYSIS_HASH', 256)

        analyzer = StockfishAnalyzer(
            stockfish_path=stockfish_path,
            depth=depth,
            threads=threads,
            hash_size=hash_size,
        )

        try:
            import chess

            board = chess.Board(start_fen)
            moves_data = []
            total_plies = len(moves)

            for i, move_entry in enumerate(moves):
                san = move_entry.get('san', move_entry) if isinstance(move_entry, dict) else move_entry
                fen_before = board.fen()
                current_ply = i + 1
                move_number = (current_ply + 1) // 2
                is_white = board.turn

                try:
                    move_obj = board.parse_san(san)
                except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError):
                    logger.warning("Skipping invalid move: %s", san)
                    break

                if analyzer._is_mock:
                    analysis = analyzer._mock_analyze_position(fen_before)
                else:
                    analysis = analyzer._analyze_single_position(fen_before, move=move_obj)

                actual_eval = analyzer._evaluate_actual_move(
                    fen_before, move_obj, analysis.get("best_moves", [])
                )

                white_perspective_score = analysis.get("score", 0.0)

                move_data = {
                    "move_number": move_number,
                    "color": "w" if is_white else "b",
                    "san": san,
                    "fen": fen_before,
                    "white_win_rate": analysis.get("white_win_rate", 50.0),
                    "score": round(white_perspective_score, 2),
                    "mate_in": analysis.get("mate_in"),
                    "best_moves": analysis.get("best_moves", []),
                    "evaluation": actual_eval["evaluation"],
                    "nag": actual_eval["nag"],
                    "score_diff": actual_eval["score_diff"],
                    "delta": actual_eval["delta"],
                }

                moves_data.append(move_data)

                progress = current_ply / total_plies if total_plies > 0 else 1.0
                task['progress'] = round(progress, 2)

                board.push(move_obj)

            result = {
                "total_moves": len(moves_data),
                "moves": moves_data,
                "final_fen": board.fen(),
            }

            pg = PracticeGame.query.get(practice_id)
            if pg:
                pg.analysis_json = json.dumps(result)
                db.session.commit()

            task['status'] = 'completed'
            task['progress'] = 1.0
            task['result'] = {
                'practice_id': practice_id,
                'total_moves': len(moves_data),
            }

        except Exception as e:
            logger.error("Practice analysis task %s failed: %s", task_id, e)
            task['status'] = 'failed'
            task['error'] = str(e)
        finally:
            analyzer.close()
