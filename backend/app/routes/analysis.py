import logging
import uuid
import threading

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db, limiter
from app.models.analysis import Analysis, AnalysisTask
from app.models.game import Game

logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/game/<int:game_id>/start', methods=['POST'])
@jwt_required()
@limiter.limit("5 per minute")
def start_game_analysis(game_id):
    """
    启动棋谱分析任务
    ---
    tags:
      - 分析管理
    security:
      - Bearer: []
    parameters:
      - name: game_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: 分析任务已启动
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
            'game_id': game_id,
            'cached': True,
        })

    # Check for in-progress tasks
    active_task = AnalysisTask.query.filter(
        AnalysisTask.game_id == game_id,
        AnalysisTask.status.in_(['pending', 'running']),
    ).first()
    if active_task:
        return jsonify({
            'message': 'Analysis already in progress',
            'task_id': active_task.id,
            'game_id': game_id,
        })

    task_id = str(uuid.uuid4())
    task = AnalysisTask(
        id=task_id,
        game_id=game_id,
        status='pending',
        progress=0.0,
    )
    db.session.add(task)
    db.session.commit()

    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_run_analysis,
        args=(task_id, game_id, app, game.pgn_content),
        daemon=True,
    )
    thread.start()

    return jsonify({
        'message': 'Analysis started',
        'task_id': task_id,
        'game_id': game_id,
    })


@analysis_bp.route('/game/<int:game_id>/status', methods=['GET'])
@jwt_required()
def get_game_analysis_status(game_id):
    """
    获取棋谱分析状态
    ---
    tags:
      - 分析管理
    security:
      - Bearer: []
    parameters:
      - name: game_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: 分析状态
    """
    task = AnalysisTask.query.filter_by(game_id=game_id).order_by(
        AnalysisTask.created_at.desc()
    ).first()

    if task:
        return jsonify(task.to_dict())

    existing = Analysis.query.filter_by(game_id=game_id).first()
    if existing:
        return jsonify({
            'game_id': game_id,
            'status': 'completed',
            'progress': 1.0,
            'analysis_id': existing.id,
            'cached': True,
        })

    return jsonify({
        'game_id': game_id,
        'status': 'none',
        'progress': 0.0,
    })


@analysis_bp.route('/tasks/<string:task_id>', methods=['GET'])
def get_task_status(task_id):
    """
    获取分析任务状态
    ---
    tags:
      - 分析管理
    parameters:
      - name: task_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: 任务状态
      404:
        description: 任务不存在
    """
    task = AnalysisTask.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(task.to_dict())


@analysis_bp.route('/tasks', methods=['GET'])
def list_analysis_tasks():
    """
    获取所有分析任务列表
    ---
    tags:
      - 分析管理
    security:
      - Bearer: []
    responses:
      200:
        description: 分析任务列表
    """
    tasks = AnalysisTask.query.order_by(
        AnalysisTask.created_at.desc()
    ).limit(100).all()

    task_list = [t.to_dict() for t in tasks]

    return jsonify({
        'tasks': task_list,
        'total': len(task_list),
    })


@analysis_bp.route('/tasks/<string:task_id>', methods=['DELETE'])
def cancel_analysis_task(task_id):
    """
    取消分析任务
    ---
    tags:
      - 分析管理
    security:
      - Bearer: []
    parameters:
      - name: task_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: 任务已取消
      404:
        description: 任务不存在
    """
    task = AnalysisTask.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.status in ('pending', 'running'):
        task.status = 'cancelled'
        task.error = 'Cancelled by user'
        db.session.commit()
        return jsonify({'message': 'Task cancelled', 'task_id': task_id})

    return jsonify({'message': 'Task already finished', 'task_id': task_id})


@analysis_bp.route('/engines', methods=['GET'])
def get_engine_info():
    """
    获取引擎信息
    ---
    tags:
      - 分析管理
    responses:
      200:
        description: Stockfish引擎配置信息
    """
    from app.services.stockfish_analyzer import StockfishAnalyzer

    stockfish_path = current_app.config.get('STOCKFISH_PATH', 'stockfish')
    depth = current_app.config.get('ANALYSIS_DEPTH', 20)
    threads = current_app.config.get('ANALYSIS_THREADS', 1)
    hash_size = current_app.config.get('ANALYSIS_HASH', 256)

    analyzer = StockfishAnalyzer(
        stockfish_path=stockfish_path,
        depth=depth,
        threads=threads,
        hash_size=hash_size,
    )

    info = analyzer.get_engine_info()

    # Include init error details if mock mode was activated
    if analyzer._is_mock and analyzer._init_error:
        info['init_error'] = analyzer._init_error
        logger.error("Stockfish running in mock mode: path=%s, error=%s", stockfish_path, analyzer._init_error)

    analyzer.close()

    return jsonify({
        'engine': info,
        'config': {
            'depth': depth,
            'threads': threads,
            'hash_size': hash_size,
            'timeout': current_app.config.get('ANALYSIS_TIMEOUT', 300),
        },
    })


def _run_analysis(task_id, game_id, app, pgn_content):
    with app.app_context():
        task = AnalysisTask.query.get(task_id)
        if not task:
            return

        task.status = 'running'
        db.session.commit()

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

        def progress_callback(progress, move_data):
            task.progress = round(progress, 2)
            # Check cancellation
            db.session.refresh(task)
            if task.status == 'cancelled':
                raise InterruptedError('Analysis cancelled by user')
            db.session.commit()

        try:
            result = analyzer.analyze_game(
                game_id=game_id,
                pgn_moves=pgn_content,
                callback=progress_callback,
            )

            analysis = Analysis.query.filter_by(game_id=game_id).first()
            if not analysis:
                analysis = Analysis(game_id=game_id)
                db.session.add(analysis)

            analysis.set_analysis_data(result)

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

            task.status = 'completed'
            task.progress = 1.0
            task.set_result({
                'analysis_id': analysis.id,
                'total_moves': result.get('total_moves', 0),
                'key_moves_count': len(key_moves),
            })

            db.session.commit()

        except InterruptedError:
            task.status = 'cancelled'
            task.error = 'Cancelled by user'
            db.session.commit()
        except Exception as e:
            logger.error("Analysis task %s failed: %s", task_id, e)
            task.status = 'failed'
            task.error = str(e)
            db.session.commit()
        finally:
            analyzer.close()
