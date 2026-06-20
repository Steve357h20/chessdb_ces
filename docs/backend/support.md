# 辅助基础设施（Support）

> 数据迁移、种子数据、导入脚本、测试套件、工具函数等支撑性模块。

## 目录

```
backend/
├── migrations/                  # Alembic 数据库迁移
│   ├── env.py
│   ├── alembic.ini
│   └── versions/                # 迁移文件
├── tests/                       # 测试套件
│   ├── conftest.py              # pytest fixtures
│   ├── test_auth.py
│   ├── test_games.py
│   ├── test_e2e_fixes.py        # 答辩后优化 E2E 测试
│   └── test_practice.py
├── scripts/                     # 运维/管理脚本
│   ├── backup_db.sh
│   └── migrate.sh
├── data/                        # 数据文件
│   ├── sample_games.pgn
│   ├── sample_games_2.pgn
│   └── openings.json            # 开局库种子
├── init_db.py                   # 初始化 + 种子
├── import_openings.py           # 开局导入
├── import_pgn.py                # PGN 导入
├── config.py                    # 配置
├── run.py                       # 入口
└── requirements.txt
```

## 1. 初始化与种子

文件：[`backend/init_db.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/init_db.py)

```python
def init_database(app):
    """初始化数据库 + 灌入种子"""
    with app.app_context():
        # 1. 创建表
        db.create_all()

        # 2. 灌入种子
        seed_admin(app)
        seed_puzzles()
        seed_openings()

def seed_admin(app):
    """创建默认管理员"""
    with app.app_context():
        if not User.query.filter_by(is_admin=True).first():
            admin = User(
                username='admin',
                email='admin@chessdb.local',
                is_admin=True,
                is_active=True,
            )
            admin.set_password('chessdb123')
            db.session.add(admin)
            db.session.commit()

def seed_puzzles():
    """灌入 10 道预设残局题"""
    from app.services.puzzle_library import PRESET_PUZZLES
    with app.app_context():
        for p in PRESET_PUZZLES:
            if not Puzzle.query.filter_by(puzzle_number=p['puzzle_number']).first():
                db.session.add(Puzzle(is_preset=True, created_by=None, **p))
        db.session.commit()

def seed_openings():
    """灌入开局库"""
    import json
    with open('data/openings.json') as f:
        openings = json.load(f)
    with app.app_context():
        for op in openings:
            if not Opening.query.filter_by(eco_code=op['eco_code']).first():
                db.session.add(Opening(**op))
        db.session.commit()
```

**默认管理员**：
- 用户名：`admin`
- 密码：`chessdb123`（生产环境请修改）

**预设残局**：10 道，puzzle_number 1-10。

**开局库**：约 500 条 ECO 主流开局。

## 2. PGN 导入脚本

文件：[`backend/import_pgn.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/import_pgn.py)

```python
def import_pgn_file(file_path: str, batch_size: int = 100):
    """从 PGN 文件导入"""
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    parser = PGNParser()
    games, errors = parser.parse_multiple(text)

    imported = 0
    for i, game in enumerate(games, 1):
        # 创建/获取棋手
        white = _get_or_create_player(game['white_player'])
        black = _get_or_create_player(game['black_player'])

        # 创建棋谱
        g = Game(
            white_player_id=white.id,
            black_player_id=black.id,
            pgn_content=game['pgn_content'],
            result=game['result'],
            eco_code=game['eco_code'],
            ...
        )
        db.session.add(g)

        if i % batch_size == 0:
            db.session.commit()
            print(f'已导入 {i} 局...')
            db.session = db.session()  # 防止 session 累积

    db.session.commit()
    print(f'导入完成: {imported} 局, 错误 {len(errors)} 条')
```

**使用**：

```bash
# 单文件
python import_pgn.py sample_games.pgn

# 全目录
python import_pgn.py data/*.pgn
```

## 3. 开局导入

文件：[`backend/import_openings.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/import_openings.py)

从 `data/openings.json` 导入：

```json
{
  "eco_code": "B90",
  "name": "Sicilian, Najdorf",
  "variation": "Main Line",
  "moves": ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"],
  "popularity": 95,
  "description": "最流行的西西里变例之一"
}
```

**数据源**：从 Wikipedia / ChessBase 整理的 ECO 主流开局。

## 4. 数据库迁移

### 4.1 初始化

```bash
cd backend
flask db init
```

会创建 `migrations/` 目录。

### 4.2 生成迁移

```bash
flask db migrate -m "add analysis_tasks table"
```

会自动比对模型生成差异文件。

### 4.3 应用迁移

```bash
flask db upgrade
```

### 4.4 回滚

```bash
flask db downgrade -1  # 退回一个版本
flask db downgrade base  # 全部回滚
```

### 4.5 迁移文件结构

```
migrations/versions/
├── 20240101_1200-abc123_add_users_table.py
├── 20240105_1430-def456_add_analysis_tasks.py
└── ...
```

每个迁移文件包含 `upgrade()` 和 `downgrade()`：

```python
def upgrade():
    op.create_table('analysis_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('game_id', sa.Integer, sa.ForeignKey('games.id')),
        ...
    )

def downgrade():
    op.drop_table('analysis_tasks')
```

## 5. 测试套件

文件：[`backend/tests/`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/tests/)

### 5.1 框架

- **pytest** - 测试框架
- **pytest-flask** - Flask 集成
- **coverage** - 覆盖率

### 5.2 运行

```bash
cd backend
pytest                       # 全部
pytest tests/test_auth.py    # 单文件
pytest -k "login"            # 按名匹配
pytest --cov=app             # 覆盖率
```

### 5.3 E2E 测试（答辩后新增）

文件：[`test_e2e_fixes.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/tests/test_e2e_fixes.py)

端到端验证三大修复：

```python
def test_modification_request_workflow(client, app):
    """验证修改申请 → 审核 → 执行流程"""
    # 1. 普通用户登录
    user_token = login(client, 'testuser', 'password')

    # 2. 提交删除棋谱申请
    resp = client.post('/api/modification-requests', json={
        'target_type': 'game', 'action': 'delete', 'target_id': 1
    }, headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 201
    request_id = resp.json['id']

    # 3. 管理员登录
    admin_token = login(client, 'admin', 'chessdb123')

    # 4. 通过申请
    resp = client.post(f'/api/admin/requests/{request_id}/approve',
        headers={'Authorization': f'Bearer {admin_token}'})
    assert resp.status_code == 200

    # 5. 棋谱被删除
    assert Game.query.get(1) is None

def test_puzzle_creation_with_user(client, app):
    """验证用户创建残局题"""
    user_token = login(client, 'user_a', 'password')
    resp = client.post('/api/practice/puzzles', json={
        'name': 'My Puzzle', 'fen': '...', 'category': 'tactics'
    }, headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 201
    assert resp.json['puzzle_number'] >= 1001
    assert resp.json['is_preset'] == False

def test_api_traffic_logging(client, app):
    """验证流量日志"""
    client.post('/api/auth/login', json={'username': 'a', 'password': 'b'})
    logs = ApiAccessLog.query.all()
    assert len(logs) > 0
    assert logs[0].path == '/api/auth/login'
```

### 5.4 Fixtures (`conftest.py`)

```python
@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def sample_game(app):
    with app.app_context():
        white = Player(name='Carlsen', country='NO')
        black = Player(name='Nakamura', country='US')
        db.session.add_all([white, black])
        db.session.commit()
        g = Game(white_player_id=white.id, black_player_id=black.id, ...)
        db.session.add(g)
        db.session.commit()
        return g
```

## 6. 备份脚本

文件：[`backend/scripts/backup_db.sh`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/scripts/backup_db.sh)

```bash
#!/bin/bash
BACKUP_DIR="backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# SQLite
cp backend/chessdb.db $BACKUP_DIR/

# PostgreSQL
# pg_dump $DATABASE_URL > $BACKUP_DIR/db.sql

# 压缩
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

echo "备份完成: $BACKUP_DIR.tar.gz"
```

或使用 Flask CLI：

```bash
flask backup-db
```

## 7. 工具函数

文件：[`backend/app/utils/validators.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/utils/validators.py)

```python
import re
import chess

def validate_email(email: str) -> bool:
    return bool(re.match(r'^[\w.+-]+@[\w-]+\.[\w.-]+$', email))

def validate_password(password: str) -> tuple[bool, str]:
    """至少 8 位、含字母数字"""
    if len(password) < 8:
        return False, '密码至少 8 位'
    if not re.search(r'[A-Za-z]', password):
        return False, '密码必须包含字母'
    if not re.search(r'[0-9]', password):
        return False, '密码必须包含数字'
    return True, ''

def validate_fen(fen: str) -> bool:
    try:
        chess.Board(fen)
        return True
    except (chess.InvalidFenError, ValueError):
        return False

def validate_pgn(pgn: str) -> bool:
    try:
        import io
        game = chess.pgn.read_game(io.StringIO(pgn))
        return game is not None
    except Exception:
        return False

def sanitize_input(text: str) -> str:
    """XSS 防护"""
    return re.sub(r'[<>"\']', '', text or '')
```

## 8. 依赖

文件：[`backend/requirements.txt`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/requirements.txt)

```text
Flask>=3.0.0
Flask-SQLAlchemy>=3.1.0
Flask-Migrate>=4.0.0
Flask-JWT-Extended>=4.6.0
Flask-CORS>=4.0.0
Flask-Limiter>=3.5.0
Flask-Admin>=1.6.1
flasgger>=0.9.7
SQLAlchemy>=2.0.0
psycopg2-binary>=2.9.9     # PostgreSQL
python-chess>=1.10.0
chess-board>=1.1.0          # 可选，棋盘渲染
gunicorn>=21.2.0
python-dotenv>=1.0.0
APScheduler>=3.10.0         # 定时任务（备用）
requests>=2.31.0
Werkzeug>=3.0.0
```

**安装**：

```bash
pip install -r requirements.txt
```

## 9. 关键脚本对照

| 场景 | 命令 |
|------|------|
| 本地首次启动 | `flask init-db` |
| 重新灌入种子 | `flask seed-data` |
| 备份数据库 | `flask backup-db` |
| 应用迁移 | `flask db upgrade` |
| 导入 PGN | `python import_pgn.py file.pgn` |
| 导入开局 | `python import_openings.py` |
| 启动 dev | `flask run` |
| 启动 prod | `gunicorn -w 4 -b 0.0.0.0:5000 run:app` |
| 跑测试 | `pytest` |
| 跑 E2E | `pytest tests/test_e2e_fixes.py -v` |

## 10. 部署启动脚本

`start-hf.sh` 在 HF Spaces 容器启动时执行：

```bash
#!/bin/bash
# 数据库初始化
python -c "
from run import app, db
with app.app_context():
    db.create_all()
    print('数据库表创建完成')
"

# 灌种子
python -c "
from run import app, db
from init_db import seed_puzzles, seed_openings, seed_admin
with app.app_context():
    seed_admin(app)
    seed_puzzles()
    seed_openings()
"

# 启动应用
exec gunicorn -w 2 -b 0.0.0.0:${PORT:-7860} --timeout 300 --preload run:app
```

`start-render.sh` 在 Render 启动时执行类似逻辑。
