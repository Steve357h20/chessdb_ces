# 数据模型层（Models）

> 文件位置：`backend/app/models/`，统一通过 `app/models/__init__.py` 导出。
> ORM 框架：SQLAlchemy 3.x + Flask-Migrate（Alembic）。
> 数据库：开发用 SQLite，生产可一键切换 PostgreSQL。

## 模型全景

```
┌──────────────────────────────────────────────────────────────────┐
│  核心数据                                                          │
│  ┌───────┐   ┌────────┐   ┌────────────┐   ┌──────┐              │
│  │ users │   │players │   │tournaments │   │games │              │
│  └───┬───┘   └───┬────┘   └─────┬──────┘   └──┬───┘              │
│      │           │              │              │                  │
│      │           │              │              │                  │
│  ┌───┴───────────┴──────────────┴──────────────┴─────┐            │
│  │                  user-level data                  │            │
│  └────────────────────────┬─────────────────────────┘            │
│  ┌────────────────────┐  │  ┌──────────────────────┐              │
│  │ collections        │──┼──│ browsing_history     │              │
│  └────────────────────┘  │  └──────────────────────┘              │
│                           │                                       │
│  ┌─────────────────┐  ┌───┴────────┐  ┌─────────────────┐         │
│  │ analyses        │──│ analysis_  │  │ openings        │         │
│  │ (1:1 game)      │  │ tasks (1:N)│  │ (独立预定义)     │         │
│  └─────────────────┘  └────────────┘  └─────────────────┘         │
│  ┌─────────────────┐  ┌─────────────────┐                          │
│  │ puzzles         │──│ practice_games  │                          │
│  └─────────────────┘  └─────────────────┘                          │
│                                                                     │
│  管理扩展                                                            │
│  ┌────────────────────┐  ┌──────────────────────┐                  │
│  │ modification_      │  │ api_access_logs      │                  │
│  │ requests           │  │                      │                  │
│  └────────────────────┘  └──────────────────────┘                  │
└──────────────────────────────────────────────────────────────────┘
```

## 通用约定

- 主键统一为 `id = db.Column(db.Integer, primary_key=True)`
- 时间字段：`created_at` / `updated_at`（自动维护）
- 关系命名：单数 `game` / 复数 `games`（避免命名冲突）
- 软删除：未启用，使用真删除 + 审核机制
- 索引：所有外键、状态字段、`is_preset` 等枚举字段都加索引

## 详细表结构

### 1. `users`（用户）

文件：[`backend/app/models/user.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/models/user.py)

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | Integer PK | ✓ | |
| username | String(80) | ✓ unique | 用户名 |
| email | String(120) | ✓ unique | 邮箱 |
| password_hash | String(255) | | PBKDF2 哈希 |
| nickname | String(80) | | 显示昵称 |
| is_admin | Boolean | ✓ | 管理员标识 |
| avatar_url | String(500) | | 头像 |
| last_login_at | DateTime | | 最后登录时间 |
| is_active | Boolean | ✓ | 是否启用 |
| created_at | DateTime | | |
| updated_at | DateTime | | |

**关系**：
- `games` → 棋手（反向 `backref`）
- `collections` → 收藏
- `browsing_history` → 历史
- `practice_games` → 练习
- `puzzles_created` → 残局题
- `modification_requests` → 申请
- `reviewed_requests` → 审核记录

**方法**：
- `set_password(password)` - 设置密码
- `check_password(password)` - 验证密码
- `to_dict()` - 序列化（不包含 hash）

### 2. `players`（棋手）

文件：[`backend/app/models/player.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/models/player.py)

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | Integer PK | | |
| name | String(100) | ✓ | 棋手姓名 |
| title | String(20) | | GM/IM/FM 等 |
| country | String(50) | ✓ | 国家/地区 |
| elo_rating | Integer | | 等级分 |
| birth_date | Date | | 出生日期 |
| bio | Text | | 简介 |
| avatar_url | String(500) | | 头像 |
| created_at | DateTime | | |
| updated_at | DateTime | | |

**关系**：
- `white_games` → 执白棋谱
- `black_games` → 执黑棋谱

**唯一约束**：`(name, country, birth_date)` - 避免重复

### 3. `tournaments`（赛事）

文件：[`backend/app/models/tournament.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/models/tournament.py)

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | Integer PK | | |
| name | String(200) | ✓ | 赛事名 |
| location | String(200) | | 地点 |
| start_date | Date | | 开始日期 |
| end_date | Date | | 结束日期 |
| category | String(50) | ✓ | 类别（古典/快棋/超快棋） |
| time_control | String(50) | | 时限 |
| description | Text | | 描述 |
| created_at | DateTime | | |
| updated_at | DateTime | | |

### 4. `games`（棋谱）

文件：[`backend/app/models/game.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/models/game.py)

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | Integer PK | | |
| white_player_id | FK(players) | ✓ | 执白棋手 |
| black_player_id | FK(players) | ✓ | 执黑棋手 |
| tournament_id | FK(tournaments) | ✓ | 所属赛事（可空） |
| event | String(200) | | 事件名 |
| site | String(200) | | 地点 |
| date | Date | ✓ | 对局日期 |
| round | String(20) | | 轮次 |
| result | String(10) | ✓ | 1-0 / 0-1 / 1/2-1/2 / * |
| eco_code | String(10) | ✓ | ECO 编码 |
| opening | String(200) | | 开局名 |
| time_control | String(50) | | 时限 |
| pgn_content | Text | | PGN 完整文本 |
| moves_count | Integer | | 回合数 |
| created_at | DateTime | | |
| updated_at | DateTime | | |

**关系**：
- `white_player` / `black_player` → Player
- `tournament` → Tournament
- `analysis` → Analysis（1:1，uselist=False）
- `analysis_tasks` → AnalysisTask（1:N）
- `collections` / `browsing_history` → 用户行为

### 5. `analyses` + `analysis_tasks`（分析）

文件：[`backend/app/models/analysis.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/models/analysis.py)

**`analyses` 表**（分析结果，1:1 关联 game）：

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | Integer PK | | |
| game_id | FK(games) | ✓ unique | |
| analysis_data | JSON | | 完整分析结果 |
| key_moves | JSON | | 关键着法索引 |
| win_rate_curve | JSON | | 胜率曲线 |
| accuracy | Float | | 准确度（白方/黑方） |
| average_loss | Float | | 平均损失 |
| engine_name | String(50) | | 引擎名 |
| depth | Integer | | 分析深度 |
| created_at | DateTime | | |
| updated_at | DateTime | | |

**`analysis_tasks` 表**（异步任务，1:N 关联 game）：

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | String(36) PK | | UUID |
| game_id | FK(games) | ✓ | |
| user_id | FK(users) | ✓ | 发起用户 |
| status | String(20) | ✓ | pending/running/completed/failed/cancelled |
| progress | Integer | | 0-100 |
| depth | Integer | | 分析深度 |
| threads | Integer | | 线程数 |
| result | JSON | | 完成时填充 |
| error_message | Text | | 失败原因 |
| started_at | DateTime | | |
| completed_at | DateTime | | |
| created_at | DateTime | | |

### 6. `openings`（开局库）

文件：[`backend/app/models/opening.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/models/opening.py)

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | Integer PK | | |
| eco_code | String(10) | ✓ unique | ECO 编码（A00-E99） |
| name | String(200) | | 开局名 |
| variation | String(200) | | 变例 |
| moves | JSON | | 着法列表 |
| popularity | Integer | ✓ | 流行度 |
| description | Text | | 描述 |
| parent_id | FK(openings) | | 父开局（树结构） |
| created_at | DateTime | | |
| updated_at | DateTime | | |

**关系**：
- `parent` → 父开局
- `children` → 子开局
- `games` → 关联棋谱

### 7. `collections`（收藏）

文件：[`backend/app/models/collection.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/models/collection.py)

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | Integer PK | | |
| user_id | FK(users) | ✓ | |
| game_id | FK(games) | ✓ | |
| note | Text | | 备注 |
| created_at | DateTime | | |

**唯一约束**：`(user_id, game_id)` - 防止重复收藏
**索引**：`user_id, created_at desc` - 用户收藏按时间倒序

### 8. `browsing_history`（浏览历史）

文件：[`backend/app/models/browsing_history.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/models/browsing_history.py)

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | Integer PK | | |
| user_id | FK(users) | ✓ | |
| game_id | FK(games) | ✓ | |
| viewed_at | DateTime | ✓ | 浏览时间 |

**唯一约束**：`(user_id, game_id)` - 重复浏览刷新时间

### 9. `puzzles` + `practice_games`（练习）

文件：[`backend/app/models/practice.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/models/practice.py)

**`puzzles` 表**（残局题）：

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | Integer PK | | |
| puzzle_number | Integer | ✓ unique | 题号（预设 1-1000，用户 1001+） |
| name | String(200) | | 题目名 |
| description | Text | | 描述 |
| fen | String(200) | | 初始局面 FEN |
| solution | JSON | | 解法着法 |
| category | String(50) | ✓ | king_pawn/queen_pawn/tactics/mate |
| difficulty | String(20) | ✓ | easy/medium/hard/expert |
| is_preset | Boolean | ✓ | 是否预设 |
| created_by | FK(users) | ✓ | 创建者 |
| practice_count | Integer | | 练习次数 |
| solve_count | Integer | | 解出次数 |
| created_at | DateTime | | |
| updated_at | DateTime | | |

**`practice_games` 表**（练习对局）：

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | Integer PK | | |
| user_id | FK(users) | ✓ | |
| mode | String(20) | ✓ | ai / puzzle / game |
| difficulty | String(20) | | 难度 |
| puzzle_id | FK(puzzles) | | 关联残局 |
| starting_game_id | FK(games) | | 从棋谱开始 |
| starting_fen | String(200) | | 起始 FEN |
| user_color | String(10) | | 用户执子色 |
| moves_json | JSON | | 完整着法记录 |
| result | String(20) | | white_win/black_win/draw/ongoing |
| review_data | JSON | | 复盘分析 |
| started_at | DateTime | | |
| ended_at | DateTime | | |
| created_at | DateTime | | |

### 10. 管理扩展表

文件：[`backend/app/models/admin_models.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/models/admin_models.py)

**`modification_requests` 表**（修改申请）：

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | Integer PK | | |
| user_id | FK(users) | ✓ | 申请人 |
| target_type | String(50) | ✓ | game/puzzle/collection/player |
| target_id | Integer | ✓ | 目标 ID |
| action | String(20) | ✓ | create/update/delete |
| payload_json | JSON | | 提交的数据 |
| reason | Text | | 申请理由 |
| status | String(20) | ✓ | pending/approved/rejected/cancelled |
| reviewer_id | FK(users) | | 审核人 |
| review_comment | Text | | 审核意见 |
| reviewed_at | DateTime | | |
| created_at | DateTime | | |
| updated_at | DateTime | | |

**`api_access_logs` 表**（API 访问日志）：

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| id | Integer PK | | |
| method | String(10) | ✓ | HTTP 方法 |
| path | String(500) | ✓ | 路径 |
| status_code | Integer | ✓ | 状态码 |
| duration_ms | Integer | | 耗时 |
| user_id | FK(users) | | 用户（可空） |
| username | String(80) | | 用户名 |
| ip_address | String(50) | | IP |
| token_fingerprint | String(20) | | JWT 摘要 |
| user_agent | String(500) | | |
| error_message | Text | | |
| created_at | DateTime | ✓ | |

## 数据库迁移

使用 Flask-Migrate（Alembic）：

```bash
# 初始化（首次）
flask db init

# 生成迁移
flask db migrate -m "add analysis_tasks table"

# 应用迁移
flask db upgrade

# 回滚
flask db downgrade
```

迁移文件位置：`backend/migrations/versions/`

## 索引策略

| 表 | 索引 | 目的 |
|----|------|------|
| games | `eco_code`, `date`, `white_player_id`, `black_player_id`, `tournament_id` | 多维过滤 |
| analyses | `game_id` unique | 一对一 |
| analysis_tasks | `game_id`, `user_id`, `status` | 任务查询 |
| collections | `(user_id, game_id)` unique | 去重 + 倒序 |
| browsing_history | `(user_id, game_id)` unique, `viewed_at` | 倒序 |
| puzzles | `puzzle_number` unique, `is_preset`, `category`, `difficulty` | 题号分配 + 过滤 |
| practice_games | `user_id`, `mode` | 用户练习列表 |
| modification_requests | `user_id`, `status`, `target_type` | 审核查询 |
| api_access_logs | `created_at`, `user_id`, `path` | 流量统计 |

## 初始化数据

`backend/init_db.py` 负责：

1. 创建数据库表（`db.create_all()`）
2. 灌入 10 道预设残局题（puzzle_number 1-10）
3. 灌入常用开局（Eco 编码 A00-E99 主流）
4. 创建默认管理员 `admin / chessdb123`

启动脚本 `start-hf.sh` / `start-render.sh` 也会自动调用 `init_db`。
