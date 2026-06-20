# ChessDB 项目分析总结

## 一、项目概述

ChessDB（国际象棋数据管理与训练系统）是一个基于前后端分离架构的综合性国际象棋应用平台，提供棋谱管理、引擎分析、AI 对弈训练、复盘分析、流量监控和后台管理。

**技术栈版本：**
- 后端：Python 3.12 + Flask 3.x + SQLAlchemy 3.x + python-chess 1.x
- 前端：Vue 3.4 + Vite 5.2 + Element Plus 2.6 + Pinia 2.1 + ECharts 5.5
- 数据库：SQLite（开发）/ PostgreSQL（生产，通过 SQLAlchemy 切换）
- 引擎：Stockfish（UCI 协议，支持自动降级为 Mock 模式）
- 部署：Docker 多阶段构建，支持 Render / Vercel / HuggingFace Spaces / VPS

## 二、功能模块分析

### 2.1 核心功能

| 功能模块 | 功能描述 | 关键技术 |
|----------|----------|----------|
| 棋谱管理 | PGN 文件上传/文本导入、棋谱列表/详情、着法解析、棋谱编辑/删除 | python-chess PGN 解析、PGNParser |
| 引擎分析 | 逐着分析、胜率曲线、关键着法标注、多 PV 变化线、同步/异步分析 | Stockfish UCI 协议、python-chess.engine |
| AI 对弈 | 五档难度 AI、残局题练习、自定义开局、悔棋/提示/认输 | Stockfish 评估 + 时间控制 |
| 复盘分析 | 练习对局复盘、玩家视角分数、妙手/好着/失误标注 | python-chess 局面重演 |
| 棋手档案 | 棋手信息、对局统计、执白/执黑胜率 | SQLAlchemy 关联查询 |
| 开局库 | ECO 分类、开局识别、开局树、相似开局 | JSON 序列化 + 前缀匹配 |
| 残局题库 | 预设 10 道残局题、自定义残局、练习统计 | FEN 持久化 + python-chess 合法性 |

### 2.2 辅助功能

| 功能模块 | 功能描述 | 关键技术 |
|----------|----------|----------|
| 用户系统 | 注册登录、JWT 24h 认证、资料管理、密码修改 | Flask-JWT-Extended |
| 收藏管理 | 收藏棋谱、备注、唯一性约束 | UniqueConstraint(user_id, game_id) |
| 浏览历史 | 自动记录、单条删除、清空 | UniqueConstraint + lazy='joined' |
| 数据分析 | ELO-步数散点图、开局胜率、分类分布 | ECharts 可视化 |
| 主题切换 | 亮色/暗色/跟随系统 | CSS Custom Properties + Pinia |
| 管理后台 | Flask-Admin Web CRUD | Flask-Admin |
| 流量监控 | API 访问日志、用户活跃度、token 追踪 | 中间件 + 异步写入 |
| 修改审核 | 用户危险操作申请、管理员审核 | ModificationRequest 表 + 审核 API |

## 三、模块架构

### 3.1 后端架构（4 层）

```
┌─────────────────────────────────────────────┐
│ 应用工厂层 (app/__init__.py)                │
│  - create_app() 创建 Flask 实例              │
│  - 注册 6 个扩展：db, migrate, jwt, cors,    │
│    limiter, admin                           │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 配置层 (config.py)                          │
│  - 4 级 base_dir 解析（解决 Windows 路径问题）│
│  - 8 个候选路径查找 Stockfish               │
│  - 多环境：development / production / testing│
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 路由层 (app/routes/)                        │
│  - 8 个 Blueprint 挂载到 /api/ 前缀          │
│  - @jwt_required 装饰器保护                 │
│  - @limiter.limit 限流                       │
│  - Swagger 注释自动生成文档                  │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 服务层 (app/services/)                      │
│  - Stockfish 引擎封装                       │
│  - AI 对弈引擎（5 档）                      │
│  - PGN 解析器                                │
│  - FEN 工具 + 开局识别                       │
│  - 残局库                                    │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 模型层 (app/models/)                        │
│  - 13 个数据表（11 业务表 + 2 扩展表）       │
│  - SQLAlchemy ORM                           │
│  - JSON 字段灵活存储                         │
│  - 关系映射与外键约束                         │
└─────────────────────────────────────────────┘
```

### 3.2 前端架构（3 层）

```
┌─────────────────────────────────────────────┐
│ 视图层 (src/views/ + src/router/)           │
│  - 19 个页面组件                            │
│  - Vue Router 4 懒加载                      │
│  - 路由守卫（认证保护/游客限制）              │
│  - 动态标题                                  │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 状态管理层 (src/store/)                     │
│  - 5 个 Pinia store：user, game, practice,   │
│    theme, ui                                │
│  - Composition API 风格                      │
│  - localStorage 持久化用户认证                │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 基础设施层 (src/api/ + src/utils/ + ...)    │
│  - 9 个 API 模块（Axios 实例）               │
│  - 统一拦截器（401 自动登出）                 │
│  - 10 个可复用组件                           │
│  - SCSS 主题系统 + chessUtils 工具           │
└─────────────────────────────────────────────┘
```

## 四、数据模型（13 张表）

按业务域分为 5 大类：

### 4.1 核心数据

- **users** - 用户账户（username, email, password_hash, is_admin）
- **players** - 棋手档案（name, title, country, elo_rating）
- **tournaments** - 赛事（name, start_date, end_date, location）
- **games** - 棋谱（white_player_id, black_player_id, pgn_content, result, eco_code）

### 4.2 分析数据

- **analyses** - 分析结果（game_id 唯一, analysis_data JSON, key_moves, win_rate_curve）
- **analysis_tasks** - 异步任务（UUID, game_id, status, progress, result）

### 4.3 用户行为

- **collections** - 收藏（user_id, game_id, note，唯一约束）
- **browsing_history** - 浏览历史（user_id, game_id, viewed_at，唯一约束）

### 4.4 训练数据

- **openings** - 开局库（eco_code, name, moves JSON, popularity）
- **puzzles** - 残局题（name, fen, category, difficulty, is_preset）
- **practice_games** - 练习记录（user_id, mode, puzzle_id, moves_json, result）

### 4.5 管理扩展

- **modification_requests** - 修改申请（user_id, target_type, action, status, payload_json）
- **api_access_logs** - API 访问日志（path, method, status_code, user_id, duration_ms）

## 五、关键技术亮点

### 5.1 Stockfish 路径解析（4 级回退）

`backend/config.py` 中的 `_resolve_stockfish_path()` 解决跨平台部署难题：

1. 环境变量 `STOCKFISH_PATH`（Docker / 部署）
2. `STOCKFISH_BASE_DIR` 拼接常见路径
3. Windows 常见路径（exe）
4. Linux apt 安装路径（`/usr/bin/stockfish`）

`_resolve_base_dir()` 解决 Windows junction / OneDrive 影子路径问题：

1. `STOCKFISH_BASE_DIR` 环境变量
2. `__file__` 绝对路径
3. 当前工作目录
4. `sys.argv[0]` 推导

### 5.2 异步分析任务持久化

`AnalysisTask` 数据库模型解决了 gunicorn 多 worker 下任务状态不共享的问题：

- 任务 ID 用 UUID 标识
- 状态机：pending → running → completed / failed / cancelled
- 进度和结果持久化在数据库
- 前端轮询查询状态

### 5.3 双部署架构支持

项目同时支持两种部署模式：

**模式 A：单容器（HF Spaces）**
- Nginx + Flask + Stockfish + 前端
- 端口 7860（HF 默认）
- supervisord 进程管理
- 16GB 内存跑 Stockfish 满血版

**模式 B：前后端分离（Render + Vercel）**
- 后端 Docker 容器，端口 5000
- 前端 Vercel 静态部署
- Vercel `routes` 配置反向代理 `/api/*`
- CORS 跨域配置
- Neon PostgreSQL 持久化

### 5.4 危险操作审核机制

针对"前端用户危险操作无审核"问题：

- `modification_requests` 表记录所有修改/删除/添加申请
- 普通用户提交申请 → 状态 `pending`
- 管理员审核 → 状态 `approved` / `rejected`
- 审核通过后才执行实际操作

### 5.5 流量监控

- `api_access_logs` 表记录所有 API 调用
- 中间件自动捕获 method/path/status_code/duration_ms
- JWT token 摘要（仅前 16 位，避免泄露）
- 管理后台可视化（按用户/端点/时间统计）

## 六、部署架构

| 组件 | 端口 | 镜像/工具 | 配置位置 |
|------|------|-----------|----------|
| Backend | 5000 | python:3.12-slim | Dockerfile (target=backend) |
| Frontend | 80 | nginx:alpine | Dockerfile (target=production) |
| Stockfish | - | apt (Linux) / exe (Windows) | 运行时由 config.py 解析 |
| DB | - | SQLite / PostgreSQL | config.py → DATABASE_URI |
| 进程管理 | - | supervisord（HF）/ gunicorn | start-hf.sh / start-render.sh |

## 七、配置化能力

通过环境变量实现零代码修改切换部署环境：

| 变量 | 作用 | 默认值 |
|------|------|--------|
| `FLASK_ENV` | 切换 dev/prod/test | default |
| `SECRET_KEY` | Flask session 加密 | dev-secret-key |
| `JWT_SECRET_KEY` | JWT 签名密钥 | jwt-dev-secret-key |
| `DATABASE_URL` / `DATABASE_URI` | 数据库连接 | SQLite chessdb.db |
| `STOCKFISH_PATH` | 引擎可执行文件 | 自动解析 |
| `STOCKFISH_BASE_DIR` | Stockfish 父目录 | 自动解析 |
| `ANALYSIS_DEPTH` | 分析深度 | 20 |
| `ANALYSIS_THREADS` | Stockfish 线程 | 1 |
| `ANALYSIS_HASH` | Stockfish 哈希表 MB | 256 |
| `ANALYSIS_TIMEOUT` | 分析超时秒 | 300 |
| `CORS_ORIGINS` | 跨域白名单 | * |
| `UPLOAD_FOLDER` | 上传目录 | ./uploads |
| `MAX_CONTENT_LENGTH` | 上传大小限制 | 16MB |
