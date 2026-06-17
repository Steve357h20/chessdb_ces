import os
import logging
from io import StringIO

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.orm import joinedload

from app import db, limiter
from app.models.game import Game
from app.models.player import Player
from app.models.analysis import Analysis
from app.services.pgn_parser import PGNParser, PGNParsingError
from app.services.opening_recognizer import OpeningRecognizer
from sqlalchemy import func, case, cast, Integer

logger = logging.getLogger(__name__)

games_bp = Blueprint('games', __name__)


@games_bp.route('/filters', methods=['GET'])
def get_game_filters():
    """
    获取棋谱筛选选项
    ---
    tags:
      - 棋谱管理
    responses:
      200:
        description: 返回可用的ECO代码和结果筛选选项
    """
    eco_codes = db.session.query(Game.eco_code).filter(Game.eco_code != '', Game.eco_code.isnot(None)).distinct().order_by(Game.eco_code).limit(100).all()
    results = db.session.query(Game.result).filter(Game.result != '', Game.result.isnot(None)).distinct().order_by(Game.result).all()
    return jsonify({
        'eco_codes': [e[0] for e in eco_codes if e[0]],
        'results': [r[0] for r in results if r[0]],
    })


@games_bp.route('', methods=['GET'])
def get_games():
    """
    获取棋谱列表
    ---
    tags:
      - 棋谱管理
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
        description: 页码
      - name: per_page
        in: query
        type: integer
        default: 20
        description: 每页数量
      - name: player
        in: query
        type: string
        description: 棋手姓名搜索
      - name: eco
        in: query
        type: string
        description: ECO代码筛选
      - name: result
        in: query
        type: string
        description: 对局结果筛选(1-0/0-1/1/2-1/2)
      - name: date_from
        in: query
        type: string
        description: 起始日期
      - name: date_to
        in: query
        type: string
        description: 结束日期
      - name: search
        in: query
        type: string
        description: 综合搜索
      - name: sort
        in: query
        type: string
        default: created_at
        description: 排序字段
      - name: order
        in: query
        type: string
        default: desc
        description: 排序方向(asc/desc)
    responses:
      200:
        description: 棋谱列表
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)

    query = Game.query.options(
        joinedload(Game.white_player),
        joinedload(Game.black_player),
    )

    player = request.args.get('player', '').strip()
    if player:
        wp = db.session.query(Player.id).filter(Player.name.ilike(f'%{player}%')).subquery()
        query = query.filter(db.or_(Game.white_player_id.in_(wp), Game.black_player_id.in_(wp)))

    date_from = request.args.get('date_from', '').strip()
    if date_from:
        query = query.filter(Game.date >= date_from)

    date_to = request.args.get('date_to', '').strip()
    if date_to:
        query = query.filter(Game.date <= date_to)

    eco = request.args.get('eco', '').strip()
    if eco:
        query = query.filter(Game.eco_code.ilike(f'{eco}%'))

    result_filter = request.args.get('result', '').strip()
    if result_filter:
        query = query.filter(Game.result == result_filter)

    search = request.args.get('search', '').strip()
    if search:
        sp = db.session.query(Player.id).filter(Player.name.ilike(f'%{search}%')).subquery()
        query = query.filter(db.or_(
            Game.white_player_id.in_(sp),
            Game.black_player_id.in_(sp),
            Game.opening_name.ilike(f'%{search}%'),
            Game.eco_code.ilike(f'%{search}%'),
        ))

    sort = request.args.get('sort', 'created_at').strip()
    order = request.args.get('order', 'desc').strip()

    sort_map = {
        'created_at': Game.created_at,
        'date': Game.date,
        'white_elo': Game.white_elo,
        'black_elo': Game.black_elo,
        'total_moves': Game.total_moves,
        'eco_code': Game.eco_code,
    }
    sort_col = sort_map.get(sort, Game.created_at)

    if order == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'items': [game.to_dict() for game in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
    })


@games_bp.route('/<int:game_id>', methods=['GET'])
def get_game(game_id):
    """
    获取棋谱详情
    ---
    tags:
      - 棋谱管理
    parameters:
      - name: game_id
        in: path
        type: integer
        required: true
        description: 棋谱ID
    responses:
      200:
        description: 棋谱详情
      404:
        description: 棋谱不存在
    """
    game = Game.query.options(
        joinedload(Game.white_player),
        joinedload(Game.black_player),
        joinedload(Game.tournament),
    ).get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    result = game.to_dict()
    result['pgn_content'] = game.pgn_content
    result['moves'] = game.get_moves_list()

    if game.analysis:
        result['has_analysis'] = True
        result['analysis'] = game.analysis.to_dict()
    else:
        result['has_analysis'] = False

    return jsonify(result)


@games_bp.route('/upload', methods=['POST'])
@limiter.limit("10 per minute")
def upload_games():
    """
    上传PGN文件导入棋谱
    普通用户 → 提交修改申请（target_type=game, action=create），管理员审核后入库
    管理员 → 直接入库
    ---
    tags:
      - 棋谱管理
    consumes:
      - multipart/form-data
    parameters:
      - name: files
        in: formData
        type: file
        required: true
        description: PGN文件(支持多文件)
    responses:
      200:
        description: 上传结果
      400:
        description: 未提供文件
    """
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No files selected'}), 400

    # 判断是否管理员
    from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
    from app.models.user import User as _User
    from app.models.admin_models import ModificationRequest as _MR
    import json as _json

    is_admin = False
    current_user = None
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity is not None:
            current_user = _User.query.filter_by(username=identity).first()
            if not current_user:
                try:
                    current_user = _User.query.get(int(identity))
                except (TypeError, ValueError):
                    current_user = None
            if current_user and current_user.is_admin:
                is_admin = True
    except Exception:
        pass

    # ---- 管理员：直接入库 ----
    if is_admin:
        parser = PGNParser()
        recognizer = OpeningRecognizer()
        uploaded = 0
        skipped = 0
        errors = []

        for file in files:
            if not file.filename.endswith(('.pgn', '.txt')):
                skipped += 1
                continue

            try:
                content = file.read().decode('utf-8')
            except UnicodeDecodeError:
                try:
                    file.seek(0)
                    content = file.read().decode('latin-1')
                except Exception as e:
                    errors.append({'file': file.filename, 'error': str(e)})
                    continue

            try:
                games_list = PGNParser.parse_multiple_games(content)
            except Exception as e:
                errors.append({'file': file.filename, 'error': str(e)})
                continue

            for game_data in games_list:
                try:
                    info = game_data.get('game_info', {})
                    white_name = info.get('white', 'Unknown')
                    black_name = info.get('black', 'Unknown')

                    white_player = Player.query.filter_by(name=white_name).first()
                    if not white_player:
                        white_player = Player(name=white_name)
                        db.session.add(white_player)
                        db.session.flush()

                    black_player = Player.query.filter_by(name=black_name).first()
                    if not black_player:
                        black_player = Player(name=black_name)
                        db.session.add(black_player)
                        db.session.flush()

                    pgn_str = _reconstruct_pgn(info, game_data.get('moves', []))

                    eco_code = info.get('eco', '')
                    opening_name = info.get('opening', '')

                    if not eco_code or not opening_name:
                        moves_san = []
                        for m in game_data.get('moves', []):
                            if m.get('white'):
                                moves_san.append(m['white'])
                            if m.get('black'):
                                moves_san.append(m['black'])
                        if moves_san:
                            opening_info = recognizer.identify_opening(moves_san)
                            if opening_info['eco_code']:
                                eco_code = eco_code or opening_info['eco_code']
                                opening_name = opening_name or opening_info['name']

                    game = Game(
                        white_player_id=white_player.id,
                        black_player_id=black_player.id,
                        date=info.get('date', ''),
                        result=info.get('result', '*'),
                        pgn_content=pgn_str,
                        eco_code=eco_code,
                        opening_name=opening_name,
                        total_moves=game_data.get('total_moves', 0),
                        final_fen=game_data.get('final_fen', ''),
                        white_elo=info.get('white_elo') if info.get('white_elo') else None,
                        black_elo=info.get('black_elo') if info.get('black_elo') else None,
                        termination=info.get('termination', ''),
                        time_control=info.get('timecontrol', info.get('time_control', '')),
                    )
                    game.assign_game_number()
                    db.session.add(game)
                    uploaded += 1
                except Exception as e:
                    logger.error("Error saving game from %s: %s", file.filename, e)
                    errors.append({'file': file.filename, 'error': str(e)})

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Database commit error: %s", e)
            return jsonify({'error': 'Database error'}), 500

        return jsonify({
            'uploaded': uploaded,
            'skipped': skipped,
            'errors': errors,
        })

    # ---- 普通用户/游客：提交修改申请 ----
    submitted = 0
    skipped = 0
    errors = []

    for file in files:
        if not file.filename.endswith(('.pgn', '.txt')):
            skipped += 1
            continue
        try:
            content = file.read().decode('utf-8')
        except UnicodeDecodeError:
            try:
                file.seek(0)
                content = file.read().decode('latin-1')
            except Exception as e:
                errors.append({'file': file.filename, 'error': str(e)})
                continue

        # 截断过长内容（payload 限制 10KB，PGN 可能很长，保留前 8000 字符）
        truncated = len(content) > 8000
        payload_content = content[:8000] if truncated else content

        req = _MR(
            user_id=current_user.id if current_user else None,
            target_type='game',
            action='create',
            target_id=None,
            payload_json=_json.dumps({
                'source': 'upload',
                'filename': file.filename,
                'pgn': payload_content,
                'truncated': truncated,
            }, ensure_ascii=False),
            reason=f'上传棋谱文件: {file.filename}',
            status='pending',
        )
        db.session.add(req)
        submitted += 1

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Database error'}), 500

    return jsonify({
        'submitted': submitted,
        'skipped': skipped,
        'errors': errors,
        'message': f'已提交 {submitted} 条上传申请，等待管理员审核',
        'need_review': True,
    })


@games_bp.route('/upload-pgn', methods=['POST'])
@limiter.limit("10 per minute")
def upload_pgn_text():
    """
    通过PGN文本导入棋谱
    普通用户 → 提交修改申请，管理员审核后入库
    管理员 → 直接入库
    ---
    tags:
      - 棋谱管理
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            pgn:
              type: string
              description: PGN格式文本
    responses:
      200:
        description: 导入结果
      400:
        description: PGN内容为空
    """
    data = request.get_json()
    if not data or 'pgn' not in data:
        return jsonify({'error': 'pgn field is required'}), 400

    content = data['pgn'].strip()
    if not content:
        return jsonify({'error': 'PGN content is empty'}), 400

    # 判断是否管理员
    from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
    from app.models.user import User as _User
    from app.models.admin_models import ModificationRequest as _MR
    import json as _json

    is_admin = False
    current_user = None
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity is not None:
            current_user = _User.query.filter_by(username=identity).first()
            if not current_user:
                try:
                    current_user = _User.query.get(int(identity))
                except (TypeError, ValueError):
                    current_user = None
            if current_user and current_user.is_admin:
                is_admin = True
    except Exception:
        pass

    # ---- 管理员：直接入库 ----
    if is_admin:
        parser = PGNParser()
        recognizer = OpeningRecognizer()
        imported = 0

        try:
            games_list = PGNParser.parse_multiple_games(content)
        except Exception as e:
            return jsonify({'error': f'PGN parse error: {str(e)}'}), 400

        for game_data in games_list:
            try:
                info = game_data.get('game_info', {})
                white_name = info.get('white', 'Unknown')
                black_name = info.get('black', 'Unknown')

                white_player = Player.query.filter_by(name=white_name).first()
                if not white_player:
                    white_player = Player(name=white_name)
                    db.session.add(white_player)
                    db.session.flush()

                black_player = Player.query.filter_by(name=black_name).first()
                if not black_player:
                    black_player = Player(name=black_name)
                    db.session.add(black_player)
                    db.session.flush()

                pgn_str = _reconstruct_pgn(info, game_data.get('moves', []))

                eco_code = info.get('eco', '')
                opening_name = info.get('opening', '')

                if not eco_code or not opening_name:
                    moves_san = []
                    for m in game_data.get('moves', []):
                        if m.get('white'):
                            moves_san.append(m['white'])
                        if m.get('black'):
                            moves_san.append(m['black'])
                    if moves_san:
                        opening_info = recognizer.identify_opening(moves_san)
                        if opening_info['eco_code']:
                            eco_code = eco_code or opening_info['eco_code']
                            opening_name = opening_name or opening_info['name']

                game = Game(
                    white_player_id=white_player.id,
                    black_player_id=black_player.id,
                    date=info.get('date', ''),
                    result=info.get('result', '*'),
                    pgn_content=pgn_str,
                    eco_code=eco_code,
                    opening_name=opening_name,
                    total_moves=game_data.get('total_moves', 0),
                    final_fen=game_data.get('final_fen', ''),
                    white_elo=info.get('white_elo') if info.get('white_elo') else None,
                    black_elo=info.get('black_elo') if info.get('black_elo') else None,
                    termination=info.get('termination', ''),
                    time_control=info.get('timecontrol', info.get('time_control', '')),
                )
                game.assign_game_number()
                db.session.add(game)
                imported += 1
            except Exception as e:
                logger.error("Error saving game from PGN text: %s", e)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error("Database commit error: %s", e)
            return jsonify({'error': 'Database error'}), 500

        return jsonify({'imported': imported})

    # ---- 普通用户/游客：提交修改申请 ----
    truncated = len(content) > 8000
    payload_content = content[:8000] if truncated else content

    req = _MR(
        user_id=current_user.id if current_user else None,
        target_type='game',
        action='create',
        target_id=None,
        payload_json=_json.dumps({
            'source': 'paste',
            'pgn': payload_content,
            'truncated': truncated,
        }, ensure_ascii=False),
        reason='粘贴上传棋谱',
        status='pending',
    )
    db.session.add(req)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Database error'}), 500

    return jsonify({
        'submitted': 1,
        'message': '已提交上传申请，等待管理员审核',
        'need_review': True,
    })


@games_bp.route('/<int:game_id>', methods=['PUT'])
@jwt_required()
def update_game(game_id):
    """
    更新棋谱信息
    普通用户 → 提交修改申请，管理员审核后生效
    管理员 → 直接修改
    ---
    tags:
      - 棋谱管理
    security:
      - Bearer: []
    parameters:
      - name: game_id
        in: path
        type: integer
        required: true
      - name: body
        in: body
        schema:
          type: object
          properties:
            date:
              type: string
            result:
              type: string
            eco_code:
              type: string
            opening_name:
              type: string
    responses:
      200:
        description: 更新成功
      404:
        description: 棋谱不存在
    """
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # 判断是否管理员
    from flask_jwt_extended import get_jwt_identity
    from app.models.user import User as _User
    from app.models.admin_models import ModificationRequest as _MR
    import json as _json

    identity = get_jwt_identity()
    current_user = _User.query.filter_by(username=identity).first()
    if not current_user:
        try:
            current_user = _User.query.get(int(identity))
        except (TypeError, ValueError):
            current_user = None

    if not current_user:
        return jsonify({'error': 'User not found'}), 401

    # 普通用户：提交修改申请
    if not current_user.is_admin:
        allowed_fields = ['date', 'result', 'eco_code', 'opening_name', 'tournament_id']
        payload = {k: v for k, v in data.items() if k in allowed_fields}
        if not payload:
            return jsonify({'error': 'No valid fields to update'}), 400

        req = _MR(
            user_id=current_user.id,
            target_type='game',
            action='update',
            target_id=game_id,
            payload_json=_json.dumps(payload, ensure_ascii=False),
            reason=f'修改棋谱 #{game_id}',
            status='pending',
        )
        db.session.add(req)
        db.session.commit()
        return jsonify({
            'message': '已提交修改申请，等待管理员审核',
            'need_review': True,
        }), 202

    # 管理员：直接修改
    allowed_fields = ['date', 'result', 'eco_code', 'opening_name', 'tournament_id']
    for field in allowed_fields:
        if field in data:
            setattr(game, field, data[field])

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

    return jsonify(game.to_dict())


@games_bp.route('/<int:game_id>', methods=['DELETE'])
@jwt_required()
def delete_game(game_id):
    """
    删除棋谱
    ---
    tags:
      - 棋谱管理
    security:
      - Bearer: []
    parameters:
      - name: game_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: 删除成功
      403:
        description: 无权限（非 owner / 非 admin）
      404:
        description: 棋谱不存在
      409:
        description: 存在关联数据（收藏/浏览）需要 force=true
    """
    from app.models.user import User
    from app.models.collection import Collection
    from app.models.browsing_history import BrowsingHistory
    from app.models.practice import Puzzle

    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    # 权限：当前用户必须是 admin 才允许删除（避免越权删公共棋谱）
    identity = get_jwt_identity()
    current_user = None
    if identity is not None:
        current_user = User.query.filter_by(username=identity).first()
        if not current_user:
            try:
                current_user = User.query.get(int(identity))
            except (TypeError, ValueError):
                current_user = None
    if not current_user or not current_user.is_admin:
        # 未登录或非管理员：拒绝，并提供"提交修改申请"入口
        return jsonify({
            'error': 'Forbidden: only admin can delete games; please submit a modification request',
            'need_mod_request': True,
        }), 403

    force = request.args.get('force', 'false').lower() in ('1', 'true', 'yes')

    # 关联数据统计
    n_collections = Collection.query.filter_by(game_id=game_id).count()
    n_browsing = BrowsingHistory.query.filter_by(game_id=game_id).count()
    n_puzzles = Puzzle.query.filter_by(source_game_id=game_id).count()

    if not force and (n_collections + n_browsing + n_puzzles > 0):
        return jsonify({
            'error': 'Game has related data; retry with ?force=true',
            'related': {
                'collections': n_collections,
                'browsing_history': n_browsing,
                'puzzles': n_puzzles,
            }
        }), 409

    try:
        # 级联清理
        Analysis.query.filter_by(game_id=game_id).delete()
        Collection.query.filter_by(game_id=game_id).delete()
        BrowsingHistory.query.filter_by(game_id=game_id).delete()
        # 残局仅断开引用，不删除
        if n_puzzles:
            Puzzle.query.filter_by(source_game_id=game_id).update({'source_game_id': None})
        db.session.delete(game)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("Delete game %s failed", game_id)
        return jsonify({'error': f'Delete failed: {e}'}), 500

    return jsonify({
        'message': 'Game deleted',
        'cascade': {
            'analyses': 1,
            'collections': n_collections,
            'browsing_history': n_browsing,
            'puzzles_unlinked': n_puzzles,
        }
    })


@games_bp.route('/<int:game_id>/moves', methods=['GET'])
def get_game_moves(game_id):
    """
    获取棋谱着法列表
    ---
    tags:
      - 棋谱管理
    parameters:
      - name: game_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: 着法列表
      404:
        description: 棋谱不存在
    """
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    moves = game.get_moves_list()
    return jsonify({
        'game_id': game_id,
        'total_moves': len(moves),
        'moves': moves,
    })


@games_bp.route('/<int:game_id>/analysis', methods=['GET'])
def get_game_analysis(game_id):
    """
    获取棋谱分析结果
    ---
    tags:
      - 棋谱管理
    parameters:
      - name: game_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: 分析结果
      404:
        description: 棋谱或分析不存在
    """
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    analysis = Analysis.query.filter_by(game_id=game_id).first()
    if not analysis:
        return jsonify({'error': 'No analysis found for this game'}), 404

    return jsonify(analysis.to_dict())


@games_bp.route('/<int:game_id>/analyze', methods=['POST'])
@jwt_required()
def analyze_game(game_id):
    """
    使用Stockfish分析棋谱
    ---
    tags:
      - 棋谱管理
    security:
      - Bearer: []
    parameters:
      - name: game_id
        in: path
        type: integer
        required: true
      - name: depth
        in: query
        type: integer
        default: 20
        description: 分析深度
    responses:
      200:
        description: 分析完成
      404:
        description: 棋谱不存在
    """
    game = Game.query.get(game_id)
    if not game:
        return jsonify({'error': 'Game not found'}), 404

    if not game.pgn_content:
        return jsonify({'error': 'Game has no PGN content'}), 400

    existing = Analysis.query.filter_by(game_id=game_id).first()
    if existing:
        return jsonify({
            'message': 'Analysis already exists',
            'analysis_id': existing.id,
            'cached': True,
        })

    from app.services.stockfish_analyzer import StockfishAnalyzer

    stockfish_path = current_app.config.get('STOCKFISH_PATH', 'stockfish')
    depth = request.args.get('depth', current_app.config.get('ANALYSIS_DEPTH', 20), type=int)
    depth = min(depth, 20)
    threads = current_app.config.get('ANALYSIS_THREADS', 1)
    hash_size = current_app.config.get('ANALYSIS_HASH', 256)

    analyzer = StockfishAnalyzer(
        stockfish_path=stockfish_path,
        depth=depth,
        threads=threads,
        hash_size=hash_size,
    )

    try:
        result = analyzer.analyze_game(game_id=game_id, pgn_moves=game.pgn_content)
    except Exception as e:
        logger.error("Analysis failed for game %d: %s", game_id, e)
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500
    finally:
        analyzer.close()

    analysis = Analysis.query.filter_by(game_id=game_id).first()
    if not analysis:
        analysis = Analysis(game_id=game_id)
        db.session.add(analysis)

    analysis.set_analysis_data(result)
    analysis.opening_eco = game.eco_code

    key_moves = []
    win_rate_curve = []
    for move_data in result.get('moves', []):
        if move_data.get('evaluation') in ('!!', '??', '!?', '?!'):
            key_moves.append({
                'move_number': move_data['move_number'],
                'san': move_data['san'],
                'evaluation': move_data['evaluation'],
                'score_diff': move_data.get('score_diff', 0),
            })
        win_rate_curve.append({
            'move_number': move_data['move_number'],
            'white_win_rate': move_data.get('white_win_rate', 50.0),
        })

    analysis.set_key_moves(key_moves)
    analysis.set_win_rate_curve(win_rate_curve)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

    return jsonify({
        'message': 'Analysis complete',
        'analysis_id': analysis.id,
        'total_moves_analyzed': result.get('total_moves', 0),
        'key_moves_count': len(key_moves),
    })


def _reconstruct_pgn(info, moves):
    lines = []
    tag_map = {
        'event': 'Event', 'site': 'Site', 'date': 'Date',
        'round': 'Round', 'white': 'White', 'black': 'Black',
        'result': 'Result', 'eco': 'ECO', 'opening': 'Opening',
        'white_elo': 'WhiteElo', 'black_elo': 'BlackElo',
        'termination': 'Termination', 'timecontrol': 'TimeControl',
    }
    for key, tag_name in tag_map.items():
        val = info.get(key, '?')
        lines.append(f'[{tag_name} "{val}"]')

    lines.append('')

    move_strs = []
    for m in moves:
        mn = m.get('move_number', 0)
        w = m.get('white', '')
        b = m.get('black', '')
        if w:
            move_strs.append(f'{mn}. {w}')
        if b:
            move_strs.append(b)

    lines.append(' '.join(move_strs) + ' ' + info.get('result', '*'))
    return '\n'.join(lines)


@games_bp.route('/stats/elo-vs-moves', methods=['GET'])
def elo_vs_moves_stats():
    base_filter = [
        Game.white_elo.isnot(None),
        Game.black_elo.isnot(None),
        Game.total_moves > 0,
        Game.result.in_(['1-0', '0-1', '1/2-1/2']),
    ]

    avg_elo_expr = func.round((Game.white_elo + Game.black_elo) / 2.0 / 10) * 10

    query = db.session.query(
        avg_elo_expr.label('avg_elo_bucket'),
        func.avg(Game.total_moves).label('avg_moves'),
        func.count(Game.id).label('game_count'),
    ).filter(*base_filter).group_by(
        avg_elo_expr,
    ).order_by(
        avg_elo_expr,
    )

    rows = query.all()

    buckets = []
    for r in rows:
        if r.avg_elo_bucket is None:
            continue
        buckets.append({
            'avg_elo': int(r.avg_elo_bucket),
            'avg_moves': round(r.avg_moves, 1) if r.avg_moves else 0,
            'game_count': r.game_count,
        })

    scatter_query = db.session.query(
        ((Game.white_elo + Game.black_elo) / 2.0).label('avg_elo'),
        Game.total_moves.label('total_moves'),
        Game.result.label('result'),
        func.abs(Game.white_elo - Game.black_elo).label('elo_gap'),
    ).filter(*base_filter).order_by(
        func.random()
    ).limit(5000)

    scatter_rows = scatter_query.all()
    scatter = []
    for r in scatter_rows:
        scatter.append({
            'avg_elo': round(r.avg_elo, 0),
            'total_moves': r.total_moves,
            'result': r.result,
            'elo_gap': int(r.elo_gap) if r.elo_gap else 0,
        })

    avg_elo = (Game.white_elo + Game.black_elo) / 2.0
    elo_bucket_50 = cast(cast(avg_elo / 50, Integer) * 50, Integer)
    move_bucket_10 = cast(cast(Game.total_moves / 10, Integer) * 10, Integer)

    density_rows = db.session.query(
        elo_bucket_50.label('elo_b'),
        move_bucket_10.label('move_b'),
        func.count(Game.id).label('cnt'),
    ).filter(*base_filter).group_by(
        elo_bucket_50, move_bucket_10,
    ).order_by(
        elo_bucket_50, move_bucket_10,
    ).all()

    density_list = [[int(r.elo_b), int(r.move_b), r.cnt] for r in density_rows]

    dist_rows = db.session.query(
        elo_bucket_50.label('elo_b'),
        func.count(Game.id).label('cnt'),
        func.min(Game.total_moves).label('min_moves'),
        func.max(Game.total_moves).label('max_moves'),
        func.avg(Game.total_moves).label('mean_moves'),
        func.avg(Game.total_moves * Game.total_moves).label('mean_sq_moves'),
    ).filter(*base_filter).group_by(
        elo_bucket_50,
    ).order_by(
        elo_bucket_50,
    ).all()

    distribution = []
    for r in dist_rows:
        if r.elo_b is None or r.cnt < 2:
            continue
        mean_val = float(r.mean_moves) if r.mean_moves else 0
        mean_sq = float(r.mean_sq_moves) if r.mean_sq_moves else 0
        variance = mean_sq - mean_val * mean_val
        std_val = (variance ** 0.5) if variance > 0 else 0
        distribution.append({
            'elo_bucket': int(r.elo_b),
            'count': r.cnt,
            'min': int(r.min_moves),
            'max': int(r.max_moves),
            'mean': round(mean_val, 1),
            'std': round(std_val, 1),
        })

    total_games = sum(b['game_count'] for b in buckets)

    return jsonify({
        'buckets': buckets,
        'scatter': scatter,
        'density_grid': density_list,
        'distribution': distribution,
        'total_games': total_games,
    })


@games_bp.route('/stats/openings', methods=['GET'])
def opening_stats():
    base_filter = [
        Game.eco_code.isnot(None),
        Game.eco_code != '',
        Game.result.in_(['1-0', '0-1', '1/2-1/2']),
    ]

    openings_query = db.session.query(
        Game.eco_code,
        func.count(Game.id).label('total'),
        func.sum(case((Game.result == '1-0', 1), else_=0)).label('white_wins'),
        func.sum(case((Game.result == '0-1', 1), else_=0)).label('black_wins'),
        func.sum(case((Game.result == '1/2-1/2', 1), else_=0)).label('draws'),
        func.avg(Game.total_moves).label('avg_moves'),
        func.avg((Game.white_elo + Game.black_elo) / 2.0).label('avg_elo'),
    ).filter(*base_filter).group_by(
        Game.eco_code,
    ).order_by(func.count(Game.id).desc()).limit(50)

    from app.models.opening import Opening
    eco_name_map = {}
    for o in Opening.query.all():
        eco_name_map[o.eco_code] = o.name

    openings = []
    for r in openings_query.all():
        total = r.total or 0
        openings.append({
            'eco_code': r.eco_code,
            'name': eco_name_map.get(r.eco_code, r.eco_code),
            'total': total,
            'white_win_rate': round((r.white_wins or 0) / total * 100, 1) if total else 0,
            'black_win_rate': round((r.black_wins or 0) / total * 100, 1) if total else 0,
            'draw_rate': round((r.draws or 0) / total * 100, 1) if total else 0,
            'avg_moves': round(r.avg_moves, 1) if r.avg_moves else 0,
            'avg_elo': round(r.avg_elo, 0) if r.avg_elo else 0,
        })

    category_names = {
        'A': '不规则开局', 'B': '半开放开局', 'C': '开放开局',
        'D': '双兵开局', 'E': '印度防御',
    }

    categories_query = db.session.query(
        func.substr(Game.eco_code, 1, 1).label('category'),
        func.count(Game.id).label('total'),
    ).filter(*base_filter).group_by(
        func.substr(Game.eco_code, 1, 1),
    ).order_by(func.substr(Game.eco_code, 1, 1))

    categories = []
    for r in categories_query.all():
        cat = r.category
        categories.append({
            'category': cat,
            'name': category_names.get(cat, cat),
            'total': r.total,
        })

    elo_bucket_expr = cast(cast((Game.white_elo + Game.black_elo) / 2.0 / 500, Integer) * 500, Integer)

    elo_openings_query = db.session.query(
        func.substr(Game.eco_code, 1, 1).label('category'),
        elo_bucket_expr.label('elo_bucket'),
        func.count(Game.id).label('total'),
    ).filter(
        *base_filter,
        Game.white_elo.isnot(None),
        Game.black_elo.isnot(None),
    ).group_by(
        func.substr(Game.eco_code, 1, 1),
        elo_bucket_expr,
    ).order_by(
        func.substr(Game.eco_code, 1, 1),
        elo_bucket_expr,
    )

    elo_openings = []
    for r in elo_openings_query.all():
        elo_openings.append({
            'category': r.category,
            'elo_bucket': int(r.elo_bucket) if r.elo_bucket is not None else 0,
            'total': r.total,
        })

    total_games = db.session.query(func.count(Game.id)).filter(*base_filter).scalar() or 0

    return jsonify({
        'openings': openings,
        'categories': categories,
        'elo_openings': elo_openings,
        'total_games': total_games,
    })
