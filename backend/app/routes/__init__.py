"""Register all blueprints, error handlers, and the root index route."""
import logging
import os

from flask import jsonify, Response
from app import db

logger = logging.getLogger(__name__)


def register_index_route(app):
    @app.route('/')
    def index():
        from app.models.game import Game
        from app.models.player import Player
        from app.models.analysis import Analysis
        from app.models.opening import Opening
        from app.models.practice import PracticeGame, Puzzle
        from app.models.admin_models import ApiAccessLog, ModificationRequest
        from app.models.user import User

        stats = {
            'games': Game.query.count(),
            'players': Player.query.count(),
            'analyses': Analysis.query.count(),
            'openings': Opening.query.count(),
            'puzzles': Puzzle.query.count(),
            'practice_games': PracticeGame.query.count(),
            'api_access_logs': ApiAccessLog.query.count(),
            'users': User.query.count(),
            'pending_mod_requests': ModificationRequest.query.filter_by(status='pending').count(),
        }

        # 优先从环境变量取前端地址
        frontend_origin = (
            app.config.get('FRONTEND_ORIGIN')
            or os.environ.get('FRONTEND_ORIGIN')
            or 'http://localhost:3000'
        )
        admin_path = '/admin'

        # 返回 HTML 控制台，避免直接暴露 API JSON 给用户
        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>国际象棋数据管理平台 · 后端服务</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
      "PingFang SC", "Hiragino Sans GB", sans-serif;
    margin: 0; padding: 0;
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    min-height: 100vh; color: #fff;
  }}
  .wrap {{ max-width: 960px; margin: 0 auto; padding: 40px 24px; }}
  h1 {{ font-size: 32px; margin: 0 0 8px; }}
  .subtitle {{ opacity: 0.85; margin-bottom: 24px; }}
  .status-pill {{
    display: inline-block; padding: 4px 12px; border-radius: 999px;
    background: rgba(46, 204, 113, 0.25); color: #2ecc71; font-weight: 600;
    font-size: 12px; letter-spacing: 0.5px; margin-bottom: 32px;
  }}
  .cta {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 32px; }}
  .btn {{
    display: inline-flex; align-items: center; gap: 8px; padding: 12px 24px;
    background: #fff; color: #1e3c72; text-decoration: none; border-radius: 8px;
    font-weight: 600; transition: transform 0.2s, box-shadow 0.2s;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  }}
  .btn:hover {{ transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,0,0,0.2); }}
  .btn.alt {{
    background: rgba(255,255,255,0.1); color: #fff;
    border: 1px solid rgba(255,255,255,0.3);
  }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px; background: rgba(255,255,255,0.1); border-radius: 12px; padding: 20px;
    backdrop-filter: blur(10px);
  }}
  .stat .label {{ font-size: 12px; opacity: 0.8; }}
  .stat .value {{ font-size: 24px; font-weight: 700; margin-top: 4px; }}
  .endpoints {{
    margin-top: 32px; background: rgba(0,0,0,0.2);
    border-radius: 12px; padding: 20px;
  }}
  .endpoints h3 {{ margin-top: 0; }}
  .endpoints ul {{ columns: 2; column-gap: 24px; list-style: none; padding: 0; }}
  .endpoints li {{
    font-family: ui-monospace, "SF Mono", Consolas, monospace;
    font-size: 13px; padding: 2px 0; word-break: break-all;
  }}
  .endpoints code {{
    background: rgba(255,255,255,0.1); padding: 1px 6px; border-radius: 4px;
  }}
  .footer {{ margin-top: 32px; opacity: 0.7; font-size: 12px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>♟️ 国际象棋数据管理平台</h1>
  <div class="subtitle">后端服务已启动 · API + Management API</div>
  <span class="status-pill">● RUNNING</span>

  <div class="cta">
          <a class="btn" href="/api/health" target="_blank">健康检查</a>
          <a class="btn alt" href="/apidocs/">API 文档 (Swagger UI)</a>
          <a class="btn alt" href="/apispec_1.json" target="_blank">OpenAPI 规范 (JSON)</a>
        </div>

  <div class="grid">
    <div class="stat"><div class="label">棋谱 (games)</div><div class="value">{stats['games']}</div></div>
    <div class="stat"><div class="label">棋手 (players)</div><div class="value">{stats['players']}</div></div>
    <div class="stat"><div class="label">分析 (analyses)</div><div class="value">{stats['analyses']}</div></div>
    <div class="stat"><div class="label">开局 (openings)</div><div class="value">{stats['openings']}</div></div>
    <div class="stat"><div class="label">残局 (puzzles)</div><div class="value">{stats['puzzles']}</div></div>
    <div class="stat"><div class="label">练习 (practice_games)</div><div class="value">{stats['practice_games']}</div></div>
    <div class="stat"><div class="label">用户 (users)</div><div class="value">{stats['users']}</div></div>
    <div class="stat"><div class="label">API 调用 (logs)</div><div class="value">{stats['api_access_logs']}</div></div>
    <div class="stat"><div class="label">待审核申请</div><div class="value" style="color:#f1c40f">{stats['pending_mod_requests']}</div></div>
  </div>

  <div class="endpoints">
    <h3>主要 API 端点</h3>
    <ul>
      <li><code>POST /api/auth/register</code></li>
      <li><code>POST /api/auth/login</code></li>
      <li><code>GET  /api/games</code></li>
      <li><code>GET  /api/practice/puzzles</code></li>
      <li><code>GET  /api/collections</code></li>
      <li><code>GET  /api/browsing</code></li>
      <li><code>POST /api/mod-requests</code></li>
      <li><code>GET  /api/admin/mod-requests</code></li>
      <li><code>GET  /api/admin/traffic/summary</code></li>
      <li><code>GET  /api/admin/users</code></li>
    </ul>
  </div>

  <div class="footer">系统状态由后端服务直接管理；如需用户/审核/可视化界面，请通过 Vue 前端登录管理员账户后访问 <code>{frontend_origin}/admin/center</code>。</div>
</div>
</body>
</html>"""
        return Response(html, mimetype='text/html')

    @app.route('/api/health')
    def health():
        from app.models.game import Game
        return jsonify({'status': 'ok', 'games': Game.query.count()})

    @app.route('/api/openapi.json')
    def openapi_spec():
        """重定向到 flasgger 自动生成的 OpenAPI JSON (兼容旧路径)"""
        from flask import redirect
        return redirect('/apispec_1.json', code=302)


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'error': 'Bad request', 'detail': str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({'error': 'Unauthorized', 'detail': str(e)}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({'error': 'Forbidden', 'detail': str(e)}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Resource not found', 'detail': str(e)}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({'error': 'Method not allowed', 'detail': str(e)}), 405

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        logger.error("Internal server error: %s", e)
        return jsonify({'error': 'Internal server error'}), 500


def register_blueprints(app):
    register_index_route(app)

    from app.routes.games import games_bp
    from app.routes.players import players_bp
    from app.routes.analysis import analysis_bp
    from app.routes.openings import openings_bp
    from app.routes.auth import auth_bp
    from app.routes.collections import collections_bp
    from app.routes.practice import practice_bp
    from app.routes.browsing import browsing_bp

    app.register_blueprint(games_bp, url_prefix='/api/games')
    app.register_blueprint(players_bp, url_prefix='/api/players')
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')
    app.register_blueprint(openings_bp, url_prefix='/api/openings')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(collections_bp, url_prefix='/api/collections')
    app.register_blueprint(practice_bp, url_prefix='/api/practice')
    app.register_blueprint(browsing_bp, url_prefix='/api/browsing')
