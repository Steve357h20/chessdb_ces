# 核心层（Core）

> 应用工厂、配置加载、扩展注册、CLI 入口、CORS、限流等核心设施。

## 1. 应用工厂 `create_app()`

文件：[`backend/app/__init__.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/__init__.py)

```python
def create_app(config_name=None):
    app = Flask(__name__)
    app.config.from_object(load_config(config_name))

    # 1. 数据库
    db.init_app(app)
    migrate.init_app(app, db)

    # 2. 认证
    jwt.init_app(app)
    jwt.token_in_blocklist_loader(load_jwt_blocklist)

    # 3. 跨域
    cors.init_app(app, resources={
        r"/api/*": {"origins": app.config['CORS_ORIGINS'].split(',')}
    })

    # 4. 限流
    limiter.init_app(app)
    limiter._storage_uri = app.config.get('RATELIMIT_STORAGE_URI', 'memory://')

    # 5. 管理后台
    admin.init_app(app)

    # 6. 注册路由
    register_blueprints(app)

    # 7. 流量中间件
    init_traffic_middleware(app)

    # 8. Swagger
    init_swagger(app)

    return app
```

**关键扩展**：

| 扩展 | 作用 | 关键配置 |
|------|------|----------|
| `db` (SQLAlchemy) | ORM | `SQLALCHEMY_DATABASE_URI`, `pool_recycle=3600` |
| `migrate` (Alembic) | 迁移 | `migrations/` |
| `jwt` (Flask-JWT-Extended) | JWT | `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRES=24h` |
| `cors` (Flask-CORS) | 跨域 | `CORS_ORIGINS` |
| `limiter` (Flask-Limiter) | 限流 | `RATELIMIT_*` |
| `admin` (Flask-Admin) | 后台 | `ADMIN_*` |
| `swagger` (Flasgger) | API 文档 | `/apispec_1.json` |

## 2. 配置层 `config.py`

文件：[`backend/config.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/config.py)

### 2.1 核心类

```python
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-dev-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'chessdb.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }

    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', './uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # Stockfish 引擎
    STOCKFISH_PATH = os.environ.get('STOCKFISH_PATH') or _resolve_stockfish_path()
    ANALYSIS_DEPTH = int(os.environ.get('ANALYSIS_DEPTH', 20))
    ANALYSIS_THREADS = int(os.environ.get('ANALYSIS_THREADS', 1))
    ANALYSIS_HASH = int(os.environ.get('ANALYSIS_HASH', 256))
    ANALYSIS_TIMEOUT = int(os.environ.get('ANALYSIS_TIMEOUT', 300))

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', Config.SQLALCHEMY_DATABASE_URI)

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
```

### 2.2 Stockfish 路径解析（4 级回退）

```python
def _resolve_stockfish_path():
    # 1. 环境变量 STOCKFISH_PATH
    if env_path := os.environ.get('STOCKFISH_PATH'):
        if os.path.isfile(env_path):
            return env_path

    # 2. STOCKFISH_BASE_DIR 拼接常见路径
    base_dir = _resolve_base_dir()
    candidates = [
        os.path.join(base_dir, 'stockfish', 'stockfish-windows-x86_64-avx2.exe'),
        os.path.join(base_dir, 'stockfish', 'stockfish.exe'),
        os.path.join(base_dir, 'Stockfish', 'stockfish-windows-x86_64-avx2.exe'),
    ]

    for c in candidates:
        if os.path.isfile(c):
            return c

    # 3. Windows 常见路径
    if sys.platform == 'win32':
        win_paths = [
            r'C:\Program Files\Stockfish\stockfish.exe',
            r'C:\Program Files (x86)\Stockfish\stockfish.exe',
            os.path.expanduser('~\\AppData\\Local\\Programs\\stockfish\\stockfish.exe'),
        ]
        for p in win_paths:
            if os.path.isfile(p):
                return p

    # 4. Linux 默认安装
    return '/usr/bin/stockfish' if sys.platform == 'linux' else None
```

### 2.3 基础目录解析（解决 Windows junction / OneDrive）

```python
def _resolve_base_dir():
    # 1. 环境变量
    if env_dir := os.environ.get('STOCKFISH_BASE_DIR'):
        return env_dir

    # 2. __file__ 绝对路径
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        pass

    # 3. 当前工作目录
    try:
        return os.path.abspath(os.getcwd())
    except OSError:
        pass

    # 4. sys.argv[0] 推导
    return os.path.dirname(os.path.abspath(sys.argv[0]))
```

## 3. 入口与 CLI

文件：[`backend/run.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/run.py)

```python
from app import create_app, db
from app.models import *

app = create_app(os.environ.get('FLASK_ENV', 'development'))

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Game': Game, ...}

# CLI 命令
@app.cli.command('init-db')
def init_db():
    """初始化数据库 + 种子数据"""
    from init_db import init_database
    init_database(app)

@app.cli.command('seed-data')
def seed_data():
    """重新灌入种子"""
    from init_db import seed_data
    seed_data(app)

@app.cli.command('backup-db')
def backup_db():
    """备份数据库到 backups/ 目录"""
    from app.utils import backup_database
    backup_database(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
```

**常用命令**：

```bash
flask init-db              # 初始化 + 种子
flask seed-data            # 重新灌入种子
flask backup-db            # 备份数据库
flask db migrate -m "..."  # 生成迁移
flask db upgrade           # 应用迁移
flask routes               # 列出所有路由
```

## 4. 流量中间件

文件：[`backend/app/traffic.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/traffic.py)

```python
def init_traffic_middleware(app):
    @app.before_request
    def before_request():
        g.request_start_time = time.time()

    @app.after_request
    def after_request(response):
        if request.path.startswith('/api/') and request.method in ['POST', 'PUT', 'DELETE']:
            try:
                duration = int((time.time() - g.request_start_time) * 1000)
                log = ApiAccessLog(
                    method=request.method,
                    path=request.path[:500],
                    status_code=response.status_code,
                    duration_ms=duration,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string[:500],
                )
                # 提取 JWT 用户
                try:
                    verify_jwt_in_request(optional=True)
                    user_id = get_jwt_identity()
                    if user_id:
                        user = User.query.get(user_id)
                        if user:
                            log.user_id = user_id
                            log.username = user.username
                except Exception:
                    pass
                db.session.add(log)
                db.session.commit()
            except Exception:
                db.session.rollback()
        return response
```

**记录范围**：只记录 `POST/PUT/DELETE` 的 `/api/*` 请求，避免 `GET` 写入风暴。

## 5. CORS 策略

```python
cors.init_app(app, resources={
    r"/api/*": {
        "origins": app.config['CORS_ORIGINS'].split(','),
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True,
    }
})
```

**生产推荐**：
```
CORS_ORIGINS=https://your-domain.vercel.app,https://admin.your-domain.com
```

**开发**：
```
CORS_ORIGINS=*
```

**绕过方案**：Vercel `vercel.json` 用 `routes` 反代 `/api/*` 到后端，可避免 CORS。

## 6. 限流策略

```python
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["2000 per day", "500 per hour"],
    storage_uri="memory://",
)

# 特殊限流
@auth_bp.route('/login', methods=['POST'])
@limiter.limit("100 per hour")
def login():
    ...

@analysis_bp.route('/async', methods=['POST'])
@limiter.limit("10 per hour")
def async_analysis():
    ...
```

**多 worker 注意**：`memory://` 仅对单进程生效，gunicorn 4 worker 会放大 4 倍。生产推荐 `redis://`：

```
RATELIMIT_STORAGE_URI=redis://redis:6379/0
```

## 7. JWT 策略

```python
jwt = JWTManager(app)

@jwt.token_in_blocklist_loader
def load_blocklist(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    return RevokedToken.is_revoked(jti)

@jwt.expired_token_loader
def expired_token(jwt_header, jwt_payload):
    return jsonify({'error': 'Token已过期', 'code': 'TOKEN_EXPIRED'}), 401

@jwt.unauthorized_loader
def unauthorized(callback):
    return jsonify({'error': '缺少Token', 'code': 'UNAUTHORIZED'}), 401
```

**关键点**：
- 24h 有效期（`JWT_ACCESS_TOKEN_EXPIRES`）
- 支持可选认证 `@jwt_required(optional=True)`（浏览历史/收藏时区分用户）
- Blocklist 支持（主动吊销 token）

## 8. Swagger 配置

文件：[`backend/app/swagger_config.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/swagger_config.py)

```python
swagger_config = {
    "headers": [],
    "specs": [{
        "endpoint": 'apispec_1',
        "route": '/apispec_1.json',
        "rule_filter": lambda rule: True,
        "model_filter": lambda tag: True,
    }],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
}
swagger_template = {
    "info": {
        "title": "ChessDB API",
        "version": "1.0.0",
        "description": "国际象棋数据管理与训练系统 API 文档",
    },
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
        }
    },
}
```

**访问**：`http://localhost:5000/apidocs`

## 9. 错误处理

全局错误处理（在 `create_app` 中注册）：

```python
@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error': str(e), 'code': 'BAD_REQUEST'}), 400

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': '资源不存在', 'code': 'NOT_FOUND'}), 404

@app.errorhandler(500)
def server_error(e):
    db.session.rollback()
    return jsonify({'error': '服务器内部错误', 'code': 'INTERNAL_ERROR'}), 500
```

## 10. 工具与验证器

文件：[`backend/app/utils/validators.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/utils/validators.py)

- `validate_email(email)`
- `validate_password(password)` - 至少 8 位、含字母数字
- `validate_fen(fen)` - 6 段 FEN 格式
- `validate_pgn(pgn)` - PGN 合法性
- `sanitize_input(text)` - XSS 防护
