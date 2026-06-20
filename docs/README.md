# ChessDB - 国际象棋数据管理与训练系统

一个基于 Flask + Vue 3 的国际象棋棋谱管理、引擎分析、AI 对弈训练和对局数据库系统。集成 Stockfish 国际象棋引擎，支持棋谱解析、对局分析、AI 训练、残局练习、流量监控和后台管理。

## 项目结构

```
ces/
├── backend/                          # 后端（Flask + SQLAlchemy）
│   ├── app/
│   │   ├── __init__.py              # 应用工厂（创建 Flask 实例、注册扩展）
│   │   ├── admin.py                 # Flask-Admin 后台管理
│   │   ├── swagger_config.py        # Swagger / Flasgger API 文档
│   │   ├── traffic.py               # API 流量监控中间件 + 管理 API
│   │   ├── models/                  # 数据模型层（11 张表）
│   │   │   ├── user.py              # users
│   │   │   ├── player.py            # players（棋手）
│   │   │   ├── game.py              # games（棋谱）
│   │   │   ├── tournament.py        # tournaments（赛事）
│   │   │   ├── analysis.py          # analyses + analysis_tasks
│   │   │   ├── opening.py           # openings（开局库）
│   │   │   ├── collection.py        # collections（收藏）
│   │   │   ├── practice.py          # puzzles + practice_games
│   │   │   ├── browsing_history.py  # browsing_history
│   │   │   └── admin_models.py      # modification_requests + api_access_logs
│   │   ├── routes/                  # 路由层（8 个 Blueprint）
│   │   │   ├── auth.py              # /api/auth
│   │   │   ├── games.py             # /api/games
│   │   │   ├── players.py           # /api/players
│   │   │   ├── openings.py          # /api/openings
│   │   │   ├── analysis.py          # /api/analysis
│   │   │   ├── practice.py          # /api/practice
│   │   │   ├── collections.py       # /api/collections
│   │   │   └── browsing.py          # /api/browsing
│   │   ├── services/                # 业务服务层
│   │   │   ├── stockfish_analyzer.py # Stockfish 引擎封装
│   │   │   ├── ai_player.py         # AI 对弈引擎
│   │   │   ├── pgn_parser.py        # PGN 解析
│   │   │   ├── opening_recognizer.py # 开局识别
│   │   │   ├── fen_utils.py         # FEN 工具
│   │   │   └── puzzle_library.py    # 预设残局库
│   │   └── utils/
│   │       └── validators.py        # 验证器
│   ├── migrations/                   # Alembic 数据库迁移
│   ├── tests/                        # 测试套件
│   ├── scripts/                      # 数据脚本
│   ├── data/                         # 数据文件
│   ├── config.py                     # 多环境配置（dev/prod/test）
│   ├── run.py                        # 应用入口 + CLI 命令
│   ├── init_db.py                    # 种子数据
│   ├── import_openings.py            # 开局导入
│   ├── import_pgn.py                 # PGN 导入
│   ├── requirements.txt
│   └── chessdb.db                    # SQLite 数据库（运行时生成）
│
├── frontend/                         # 前端（Vue 3 + Vite）
│   ├── src/
│   │   ├── api/                      # HTTP API 封装（9 个模块）
│   │   ├── components/               # 可复用组件
│   │   ├── composables/              # 组合式函数
│   │   ├── layouts/                  # 布局
│   │   ├── router/                   # Vue Router 4
│   │   ├── store/                    # Pinia stores
│   │   ├── styles/                   # 样式系统
│   │   ├── utils/                    # 工具函数
│   │   ├── views/                    # 19 个页面
│   │   ├── App.vue
│   │   └── main.js
│   ├── vercel.json                   # Vercel 部署配置
│   ├── vite.config.js                # Vite 配置（含 API 代理）
│   └── package.json
│
├── docs/                             # 项目文档（当前所在目录）
│   ├── README.md                     # 本文件
│   ├── PROJECT_ANALYSIS.md           # 项目分析总结
│   ├── OPTIMIZATION_REPORT.md        # 答辩后优化报告
│   ├── Q&A.md                        # 答辩问答
│   ├── API.md                        # 后端 API 文档
│   ├── DEPLOYMENT.md                 # 部署完整指南
│   ├── er_diagram.png                # 数据库 ER 图
│   ├── func_structure.png            # 功能结构图
│   ├── backend/                      # 后端模块文档
│   │   ├── core.md                   # 核心层
│   │   ├── models.md                 # 数据模型
│   │   ├── routes.md                 # 路由层
│   │   ├── services.md               # 业务服务
│   │   └── support.md                # 辅助基础设施
│   └── frontend/                     # 前端模块文档
│       ├── api.md                    # API 封装
│       ├── components.md             # 组件
│       ├── views.md                  # 视图
│       ├── store.md                  # 状态管理
│       └── infrastructure.md         # 基础设施
│
├── deploy.sh                         # Oracle Cloud 一键部署
├── deploy-cn.sh                      # 国内 VPS 一键部署
├── deploy-hf.sh                      # HF Spaces 一键部署
├── start.bat                         # Windows 本地启动
├── start-hf.sh                       # HF 容器启动
├── start-render.sh                   # Render 容器启动
│
├── Dockerfile                        # 多阶段构建（Render/VPS）
├── Dockerfile.hf                     # HF Spaces 专用
├── docker-compose.yml                # 容器编排
├── nginx.conf                        # Nginx 反向代理
├── render.yaml                       # Render 部署
├── fly.toml                          # Fly.io 部署
├── vercel.json                       # Vercel 部署
├── .gitattributes                    # Git LF 归一化
├── .gitignore                        # Git 排除规则
└── .vercelignore                     # Vercel 排除规则
```

## 功能特性

### 核心功能

- **棋谱管理** - 上传 PGN 文件批量导入棋谱，自动解析棋手、开局、结果等信息，支持文本粘贴导入
- **引擎分析** - 集成 Stockfish 引擎，提供逐着评价、胜率曲线、关键着法标注、多 PV 变化线展示，支持同步/异步分析
- **AI 对弈** - 五档难度 AI 对手（入门/初级/中级/高级/专家），支持自定义开局、残局题、从棋谱开始练习，含悔棋/提示/认输
- **复盘分析** - 练习对局后一键复盘，支持玩家视角分数/胜率显示、着法评价标注（妙手/好着/失误等）、胜率走势图
- **棋手档案** - 棋手信息管理，对局统计（执白/执黑胜率），ECO 分类统计
- **开局库** - ECO 编码分类浏览，开局识别，开局树结构，相似开局推荐
- **残局题库** - 10 道预设残局练习题（王兵残局/战术/将杀），支持用户自定义残局，练习次数与解题率统计

### 辅助功能

- **用户系统** - 注册登录，JWT 认证（24h 有效期），个人资料管理，密码修改
- **收藏管理** - 收藏棋谱并添加备注，收藏状态检查，快速访问
- **浏览历史** - 自动记录浏览过的棋谱，支持单条删除和清空
- **数据分析** - ELO 与步数关系散点图、开局胜率统计、开局分类分布
- **打谱回放** - 棋谱回放，自动播放，着法跳转，速度控制
- **主题切换** - 亮色/暗色/跟随系统三种模式
- **管理后台** - Flask-Admin Web 管理界面，支持数据 CRUD 和导出
- **管理 API** - 流量监控、用户管理、修改申请审核（应对"危险操作无审核"问题）
- **API 文档** - Swagger/Flasgger 自动生成 API 文档

## 技术栈

### 后端

- Python 3.12
- Flask 3.x（Web 框架，应用工厂模式）
- SQLAlchemy 3.x + Flask-Migrate（ORM 与数据库迁移）
- Flask-JWT-Extended（JWT 认证，支持可选认证）
- Flask-CORS（跨域支持，配置化 CORS_ORIGINS）
- Flask-Limiter（API 限流，2000/天、500/小时）
- Flask-Admin（管理后台）
- Flasgger（Swagger API 文档）
- python-chess（棋谱解析、FEN 处理、规则引擎）
- Stockfish（UCI 引擎分析，支持 Mock 降级）

### 前端

- Vue 3.4（Composition API + `<script setup>`）
- Vite 5.2（构建工具，内置 API 代理）
- Element Plus 2.6（UI 组件库，按需导入）
- Pinia 2.1（状态管理）
- Vue Router 4.3（路由管理，懒加载）
- ECharts 5.5 + vue-echarts 6.6（数据可视化）
- Axios 1.6（HTTP 请求，统一拦截器）
- chess.js（前端棋规引擎）

## 数据模型概览

11 张数据表，按业务域划分：

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `users` | 用户账户 | username, email, password_hash, is_admin |
| `players` | 棋手信息 | name, title, country, elo_rating |
| `tournaments` | 赛事 | name, start_date, end_date, location |
| `games` | 棋谱 | white_player_id, black_player_id, pgn_content, result, eco_code |
| `analyses` | 分析结果 | game_id, analysis_data(JSON), key_moves, win_rate_curve |
| `analysis_tasks` | 异步任务 | id(UUID), game_id, status, progress, result |
| `openings` | 开局库 | eco_code, name, moves(JSON), popularity |
| `collections` | 收藏 | user_id, game_id, note |
| `browsing_history` | 浏览历史 | user_id, game_id, viewed_at |
| `puzzles` | 残局题 | name, fen, category, difficulty, is_preset |
| `practice_games` | 练习记录 | user_id, mode, puzzle_id, moves_json, result |
| `modification_requests` | 修改申请 | user_id, target_type, action, status, payload_json |
| `api_access_logs` | API 访问日志 | path, method, status_code, user_id, duration_ms |

详细字段说明见 [docs/backend/models.md](backend/models.md)。

## 快速开始

### 本地开发（Windows）

```bat
# 双击或在 cmd 中执行
start.bat
```

自动启动：
- 后端：Flask dev server，端口 5000
- 前端：Vite dev server，端口 3000

### Docker 部署

```bash
# 构建并启动
docker compose up -d --build

# 初始化数据库
docker compose exec backend flask init-db
docker compose exec backend flask seed-data

# 访问
# 前端：http://localhost
# 后端：http://localhost:5000
```

### 生产部署

详见 [docs/DEPLOYMENT.md](DEPLOYMENT.md)。支持以下平台：

| 平台 | 后端 | 前端 | 数据库 | 费用 |
|------|------|------|--------|------|
| Render + Vercel | Render Docker | Vercel | Neon PostgreSQL（推荐）或 SQLite | 免费 |
| Hugging Face Spaces | 单容器（HF） | 内置 | SQLite（需 Persistent Storage 持久化） | 免费 |
| Oracle Cloud ARM | Docker Compose | Nginx | SQLite + Volume | 永久免费 |
| 雨云/腾讯云 | Docker Compose | Nginx | SQLite + Volume | ¥10-30/月 |

## 默认管理员

通过 `init_db` + 种子数据或容器启动脚本自动创建：
- 用户名：`admin`
- 密码：`chessdb123`（HF 部署）/ `admin123`（Render 部署）
- **部署后请立即修改密码**

## 文档导航

| 文档 | 内容 |
|------|------|
| [docs/PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md) | 项目整体分析、模块划分、技术亮点 |
| [docs/OPTIMIZATION_REPORT.md](OPTIMIZATION_REPORT.md) | 答辩后三大问题修复记录 |
| [docs/Q&A.md](Q&A.md) | 答辩高频问答 |
| [docs/API.md](API.md) | 后端所有 REST API |
| [docs/DEPLOYMENT.md](DEPLOYMENT.md) | 各平台部署完整步骤 |
| [docs/backend/models.md](backend/models.md) | 11 张数据表详解 |
| [docs/backend/core.md](backend/core.md) | 应用工厂、配置、扩展 |
| [docs/backend/routes.md](backend/routes.md) | 8 个 Blueprint |
| [docs/backend/services.md](backend/services.md) | 业务服务（引擎、AI、解析） |
| [docs/backend/support.md](backend/support.md) | 数据、脚本、测试、迁移 |
| [docs/frontend/api.md](frontend/api.md) | 前端 HTTP 封装 |
| [docs/frontend/components.md](frontend/components.md) | 10 个可复用组件 |
| [docs/frontend/views.md](frontend/views.md) | 19 个页面与路由 |
| [docs/frontend/store.md](frontend/store.md) | 5 个 Pinia store |
| [docs/frontend/infrastructure.md](frontend/infrastructure.md) | 样式、工具、布局、构建 |
