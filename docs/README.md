# ChessDB - 国际象棋数据管理与训练系统

一个基于 Flask + Vue 3 的国际象棋棋谱管理、引擎分析、AI 对弈训练和对局数据库系统。

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
- **API 文档** - Swagger/Flasgger 自动生成 API 文档

## 技术栈

### 后端
- Python 3.12
- Flask 3.x（Web 框架，应用工厂模式）
- SQLAlchemy 3.x + Flask-Migrate（ORM 与数据库迁移）
- Flask-JWT-Extended（JWT 认证，支持可选认证）
- Flask-CORS（跨域支持）
- Flask-Limiter（API 限流）
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
- SCSS（样式预处理）

### 数据库
- SQLite（开发环境，通过 SQLAlchemy 可切换至 MySQL/PostgreSQL）

## 架构设计

### 整体架构

项目采用前后端分离架构：

```
┌─────────────────┐     HTTP/REST API     ┌─────────────────┐
│   Vue 3 前端     │ ◄──────────────────► │   Flask 后端     │
│   (Vite Dev)     │    JSON 数据交互      │   (Blueprint)    │
│   Port: 3000     │                       │   Port: 5000     │
└─────────────────┘                       └────────┬────────┘
                                                   │
                                          ┌────────┴────────┐
                                          │   SQLite 数据库  │
                                          │   chessdb.db     │
                                          └─────────────────┘
```

### 后端模块划分

```
backend/
├── app/
│   ├── __init__.py          # 应用工厂 create_app()
│   ├── models/              # SQLAlchemy 数据模型（10 个模型）
│   │   ├── user.py          # 用户模型 (users)
│   │   ├── game.py          # 棋谱模型 (games)
│   │   ├── player.py        # 棋手模型 (players)
│   │   ├── analysis.py      # 分析结果模型 (analyses)
│   │   ├── opening.py       # 开局模型 (openings)
│   │   ├── practice.py      # 练习/残局模型 (practice_games, puzzles)
│   │   ├── collection.py    # 收藏模型 (collections)
│   │   ├── browsing_history.py # 浏览历史模型 (browsing_history)
│   │   └── tournament.py    # 赛事模型 (tournaments)
│   ├── routes/              # API 路由（8 个 Blueprint）
│   │   ├── auth.py          # /api/auth - 认证
│   │   ├── games.py         # /api/games - 棋谱 CRUD + 统计
│   │   ├── players.py       # /api/players - 棋手
│   │   ├── openings.py      # /api/openings - 开局
│   │   ├── analysis.py      # /api/analysis - 异步分析
│   │   ├── practice.py      # /api/practice - 练习/AI对弈
│   │   ├── collections.py   # /api/collections - 收藏
│   │   └── browsing.py      # /api/browsing - 浏览历史
│   ├── services/            # 业务逻辑层
│   │   ├── stockfish_analyzer.py  # Stockfish 引擎分析器（含 Mock 降级）
│   │   ├── ai_player.py           # AI 对弈逻辑（5 档难度 + PracticeSession）
│   │   ├── pgn_parser.py          # PGN 解析器（单局/多局）
│   │   ├── opening_recognizer.py  # 开局识别器（数据库 + 内置回退）
│   │   ├── puzzle_library.py      # 预设残局题库（10 道预设题）
│   │   └── fen_utils.py           # FEN 工具类（解析/验证/转换/走子）
│   ├── admin.py             # Flask-Admin 管理后台配置
│   ├── swagger_config.py    # Swagger 文档配置
│   └── utils/               # 工具函数
├── config.py                # 配置文件（开发/生产/测试）
├── run.py                   # 启动脚本（含 CLI 命令）
├── requirements.txt         # Python 依赖
└── .env.example             # 环境变量模板
```

### 前端模块划分

```
frontend/
├── src/
│   ├── api/                 # API 封装层（9 个模块）
│   │   ├── request.js       # Axios 实例与拦截器（统一认证/错误处理）
│   │   ├── auth.js          # 认证 API（5 个接口）
│   │   ├── games.js         # 棋谱 API（9 个接口）
│   │   ├── players.js       # 棋手 API（5 个接口）
│   │   ├── openings.js      # 开局 API（4 个接口）
│   │   ├── analysis.js      # 分析 API（8 个接口）
│   │   ├── practice.js      # 练习 API（17 个接口）
│   │   ├── collections.js   # 收藏 API（5 个接口）
│   │   └── browsing.js      # 浏览历史 API（4 个接口）
│   ├── components/          # 可复用组件
│   │   ├── ChessBoard.vue   # 国际象棋棋盘（SVG 渲染）
│   │   ├── PracticeBoard.vue # 练习棋盘（含 AI 交互）
│   │   ├── GameController.vue # 游戏控制器（分数显示/自动播放）
│   │   ├── MoveList.vue     # 着法列表
│   │   ├── MoveEvaluation.vue # 着法评价面板
│   │   ├── WinRateChart.vue # 胜率走势图（ECharts）
│   │   ├── OpeningInfo.vue  # 开局信息展示
│   │   ├── AnalysisOverlay.vue # 分析叠加层
│   │   ├── HelpTooltip.vue  # 帮助提示
│   │   └── ThemeSwitch.vue  # 主题切换
│   ├── composables/         # 组合式函数
│   │   └── useAnalysisOverlay.js # 分析叠加层逻辑
│   ├── views/               # 页面视图（19 个页面）
│   │   ├── Home.vue         # 首页
│   │   ├── GameList.vue     # 棋谱库
│   │   ├── GameDetail.vue   # 对局详情/打谱
│   │   ├── PlayerList.vue   # 棋手列表
│   │   ├── PlayerDetail.vue # 棋手详情
│   │   ├── OpeningLibrary.vue # 开局库
│   │   ├── Practice.vue     # AI 对弈
│   │   ├── PracticeReview.vue # 练习复盘
│   │   ├── PracticeHistory.vue # 练习历史
│   │   ├── PuzzleLibrary.vue # 残局题库
│   │   ├── Stats.vue        # 数据分析
│   │   ├── Upload.vue       # 上传棋谱
│   │   ├── AnalysisQueue.vue # 分析队列
│   │   ├── Favorites.vue    # 我的收藏
│   │   ├── BrowsingHistory.vue # 浏览历史
│   │   ├── Profile.vue      # 个人设置
│   │   ├── Login.vue        # 登录/注册
│   │   ├── Help.vue         # 帮助中心
│   │   └── ComponentTest.vue # 组件测试
│   ├── store/               # Pinia 状态管理（5 个 Store）
│   │   ├── userStore.js     # 用户状态（登录/注册/认证检查）
│   │   ├── gameStore.js     # 棋谱状态（回放/分析/着法导航）
│   │   ├── practiceStore.js # 练习状态（会话/走棋/悔棋/提示）
│   │   ├── themeStore.js    # 主题状态（light/dark/auto）
│   │   └── uiStore.js       # UI 状态（侧边栏/通知）
│   ├── router/              # Vue Router 路由（含守卫）
│   ├── styles/              # SCSS 样式
│   └── utils/               # 工具函数
├── vite.config.js           # Vite 配置（API 代理/构建优化/按需导入）
└── package.json             # Node 依赖
```

### 前后端通信机制

1. **API 代理**：前端 Vite 开发服务器配置 `/api` 代理到后端 `http://localhost:5000`
2. **JWT 认证**：登录后获取 Token，存储在 localStorage，通过 Axios 拦截器自动注入 `Authorization: Bearer <token>` 请求头
3. **Token 过期处理**：401 响应自动清除 Token 并跳转登录页（含 redirect 参数）
4. **会话管理**：AI 对弈使用内存会话（session_id），410 状态码表示会话过期
5. **异步分析**：分析任务通过后台线程执行，前端轮询状态接口获取进度
6. **错误处理**：Axios 拦截器统一处理 400/401/403/404/410/422/429/500 错误
7. **限流保护**：429 响应提示"请求过于频繁，请稍后再试"

### 核心业务流程

**棋谱分析流程：**
```
用户选择棋谱 → POST /analysis/game/:id/start → 后台线程启动分析
     ↓                                              ↓
前端轮询 /analysis/game/:id/status     StockfishAnalyzer.analyze_game()
     ↓                                              ↓
status=completed → 获取分析结果          逐着分析 → 存入 analyses 表
```

**AI 对弈流程：**
```
用户选择模式 → POST /practice/start → 创建内存会话
     ↓                                    ↓
用户走棋 → POST /practice/move   PracticeSession.user_move()
     ↓                                    ↓
AI 自动应答 ← 返回 AI 着法      AIPlayer.get_move() → Stockfish
     ↓
游戏结束 → 保存到 practice_games 表 → 清除内存会话
```

**复盘分析流程：**
```
用户点击复盘 → POST /practice/analyze/:id → 后台线程启动
     ↓                                           ↓
前端轮询状态                    StockfishAnalyzer 逐着分析
     ↓                                           ↓
获取结果 → 渲染胜率图/着法评价    分析结果存入 analysis_json
```

## 安装部署

### 前置要求
- Python 3.10+
- Node.js 18+
- Stockfish 引擎（可选，无引擎时自动降级为 Mock 模式）

### 后端安装

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置数据库连接和密钥

# 初始化数据库
flask init-db
# 或使用种子数据
flask seed-data

# 创建管理员
flask create-admin

# 启动开发服务器
python run.py
```

### 前端安装
```bash
cd frontend
npm install

# 启动开发服务器
npm run dev

# 生产构建
npm run build
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| SECRET_KEY | dev-secret-key-change-in-production | Flask 密钥 |
| JWT_SECRET_KEY | jwt-dev-secret-key | JWT 签名密钥 |
| DATABASE_URI | sqlite:///chessdb.db | 数据库连接字符串 |
| STOCKFISH_PATH | backend/stockfish/stockfish/... | Stockfish 引擎路径 |
| ANALYSIS_DEPTH | 20 | 分析深度 |
| ANALYSIS_THREADS | 1 | 分析线程数 |
| ANALYSIS_HASH | 256 | 哈希表大小 (MB) |
| ANALYSIS_TIMEOUT | 300 | 分析超时 (秒) |
| FLASK_ENV | default | 运行环境 (development/production/testing) |
| FLASK_HOST | 0.0.0.0 | 监听地址 |
| FLASK_PORT | 5000 | 监听端口 |
| FLASK_DEBUG | true | 调试模式 |
| UPLOAD_FOLDER | ./uploads | 上传目录 |
| MAX_CONTENT_LENGTH | 16MB | 最大上传大小 |

---

## 答辩后变更记录

> 答辩后老师指出 3 个问题，已全部修复。详见 [`docs/OPTIMIZATION_REPORT.md`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/docs/OPTIMIZATION_REPORT.md) 与 [`docs/PROJECT_ANALYSIS.md`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/docs/PROJECT_ANALYSIS.md) 的"答辩后修复的验证清单"小节。

### 修复清单

| # | 问题 | 修复 | 验证 |
|---|------|------|------|
| 1 | 危险操作直接落库 | 新增 `ModificationRequest` 审核流 + 管理控制台 | 端到端测试 3.x 通过 |
| 1 | 缺后端管理页面 | 新建 [`AdminDashboard.vue`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/frontend/src/views/AdminDashboard.vue) 含 3 个 Tab（审核/流量/用户） | 前端路由守卫生效 |
| 1 | 缺 API 流量监测 | 新建 [`traffic.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/traffic.py) 中间件 + `ApiAccessLog` 表 | 4.x 测试真实记录 14 条 |
| 2 | 表分得过多 | 12 张表均为必要；`openings` 建议保留为表+索引 | 已文档化 |
| 3 | 残局 `created_by` 为空、个性化未实现 | 修复 `practice.py` 中 `User.query.get(int(identity))` 兜底 | 2.1-2.6 全 OK |

### 端到端测试

```powershell
cd backend
python tests/test_e2e_fixes.py
```

输出：
```
=== 阶段 1：用户注册 ===           OK
=== 阶段 2：个性化残局 ===         OK  (created_by=1/2, 用户隔离)
=== 阶段 3：修改申请审核 ===       OK  (申请→审核→落库)
=== 阶段 4：流量监测 ===           OK  (24h 14 次请求, 3 用户)
=== 全部测试通过！===
```

### 新增文件

- `backend/app/traffic.py` — 流量监控 + 审核 API
- `backend/app/models/admin_models.py` — `ApiAccessLog`, `ModificationRequest`
- `backend/tests/test_e2e_fixes.py` — 端到端集成测试
- `frontend/src/views/AdminDashboard.vue` — 管理控制台
- `docs/OPTIMIZATION_REPORT.md` — 优化报告

### 使用说明

1. 启动后端服务 (默认 http://localhost:5000)
2. 启动前端服务 (默认 http://localhost:3000)
3. 访问 http://localhost:3000 使用系统
4. 注册账号后可上传棋谱、提交分析任务、收藏棋谱
5. AI 对弈无需登录即可使用，但复盘分析需登录
6. 管理后台访问 http://localhost:5000/admin/
7. Swagger API 文档访问 http://localhost:5000/apidocs/

### CLI 命令

| 命令 | 说明 |
|------|------|
| `flask init-db` | 初始化数据库 |
| `flask reset-db` | 重置数据库（删除并重建） |
| `flask seed-data` | 导入种子数据 |
| `flask create-admin` | 创建管理员用户 |

## API 概览

| 模块 | 路径前缀 | 认证 | 说明 |
|------|----------|------|------|
| 认证 | `/api/auth` | 部分需要 | 注册、登录、用户信息、修改密码 |
| 棋谱 | `/api/games` | 部分需要 | CRUD、上传、分析、着法、统计 |
| 棋手 | `/api/players` | 不需要 | 列表、详情、统计、筛选 |
| 开局 | `/api/openings` | 不需要 | 开局库、识别、树 |
| 分析 | `/api/analysis` | 需要 | 异步分析任务、引擎信息 |
| 练习 | `/api/practice` | 部分需要 | AI对弈、残局题、复盘、历史 |
| 收藏 | `/api/collections` | 需要 | 收藏管理、状态检查 |
| 浏览 | `/api/browsing` | 需要 | 浏览历史、清空 |

详细 API 文档见 [API.md](./API.md)。

## 项目文档

| 文档 | 说明 |
|------|------|
| [README.md](./README.md) | 项目概述与使用指南 |
| [API.md](./API.md) | 完整 API 接口文档 |
| [PROJECT_ANALYSIS.md](./PROJECT_ANALYSIS.md) | 项目架构与实现分析 |

## 部署

### Docker 部署

```bash
docker-compose up -d
```

### 手动部署

```bash
# 后端
cd backend
gunicorn -w 4 -b 0.0.0.0:5000 run:app

# 前端
cd frontend
npm run build
# 将 dist/ 目录部署到 Nginx
```

### Nginx 配置要点

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 管理后台
    location /admin/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## License

MIT
