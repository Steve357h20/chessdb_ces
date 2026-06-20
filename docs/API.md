# API 文档

> ChessDB 后端 REST API 完整参考。基准 URL：`/api`
>
> 认证：除特别说明外均需在 `Authorization: Bearer <token>` 头携带 JWT。
>
> 完整 Swagger 文档：访问 `GET /apispec_1.json` 或 `/apidocs`（Flasgger）。
>
> 权限说明：
> - 公开（不需登录）：浏览、注册、登录、查看棋手/开局/分析引擎
> - 用户（需登录）：管理个人收藏/历史/练习
> - 管理员：管理用户、审核申请、查看流量

---

## 1. 认证（/api/auth）

文件：[`backend/app/routes/auth.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/auth.py)

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/register` | 公开 | 用户注册 |
| POST | `/login` | 公开 | 用户登录，返回 JWT |
| GET | `/me` | 用户 | 获取当前用户信息 |
| PUT | `/profile` | 用户 | 更新个人资料（昵称、邮箱） |
| POST | `/change-password` | 用户 | 修改密码（需原密码） |
| POST | `/logout` | 用户 | 注销（黑名单 Token） |

**POST /api/auth/register**

```json
请求体:
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "P@ssw0rd123"
}

响应 201:
{
  "message": "注册成功",
  "user": { "id": 1, "username": "testuser", "email": "test@example.com", "is_admin": false }
}
```

**POST /api/auth/login**

```json
请求体:
{
  "username": "admin",
  "password": "chessdb123"
}

响应 200:
{
  "access_token": "eyJhbGciOi...",
  "user": { "id": 1, "username": "admin", "email": "admin@chessdb.local", "is_admin": true }
}
```

> 注：实际 `access_token` 中存放的 identity 是 `username`（不是 user_id），由 `traffic.py` 中的 `_require_admin` 同时支持两种解析。

---

## 2. 棋谱（/api/games）

文件：[`backend/app/routes/games.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/games.py)

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/` | 公开 | 棋谱列表（分页、搜索、过滤） |
| GET | `/<id>` | 公开 | 棋谱详情 |
| GET | `/filters` | 公开 | 列表筛选项（ECO/棋手/赛事/日期） |
| POST | `/` | 用户 | 创建棋谱（PGN 文本） |
| POST | `/upload` | 用户 | 上传 PGN 文件批量导入 |
| POST | `/upload-pgn` | 用户 | 文本导入（粘贴 PGN） |
| PUT | `/<id>` | 用户 | 更新棋谱（提交审核或直接） |
| DELETE | `/<id>` | 用户 | 删除棋谱（提交审核或直接） |
| GET | `/<id>/moves` | 公开 | 棋谱着法列表 |
| GET | `/<id>/pgn` | 公开 | 导出 PGN 文件 |
| GET | `/<id>/analysis` | 公开 | 获取棋谱分析结果 |
| GET | `/search/quick` | 公开 | 快速搜索（按棋手名/赛事名/ECO） |

**GET /api/games/?page=1&per_page=20&q=carlsen&eco=B90**

```json
响应 200:
{
  "games": [
    {
      "id": 1,
      "white_player": { "id": 1, "name": "Magnus Carlsen" },
      "black_player": { "id": 2, "name": "Hikaru Nakamura" },
      "result": "1-0",
      "date": "2024-01-15",
      "eco_code": "B90",
      "opening_name": "Sicilian, Najdorf",
      "total_moves": 42
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20
}
```

**POST /api/games/upload（multipart）**

```
字段: file = *.pgn
响应 201:
{
  "imported": 15,
  "skipped": 2,
  "errors": ["第 3 局 PGN 格式错误"]
}
```

---

## 3. 棋手（/api/players）

文件：[`backend/app/routes/players.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/players.py)

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/` | 公开 | 棋手列表（分页、搜索、过滤） |
| GET | `/<id>` | 公开 | 棋手详情 |
| GET | `/filters` | 公开 | 列表筛选项（国家/头衔） |
| GET | `/<id>/stats` | 公开 | 棋手对局统计 |
| GET | `/<id>/games` | 公开 | 棋手参与的对局 |

**GET /api/players/1/stats**

```json
响应 200:
{
  "total_games": 215,
  "wins_as_white": 67,
  "wins_as_black": 54,
  "draws": 60,
  "losses": 34,
  "win_rate": 0.561,
  "favorite_openings": [
    { "eco_code": "B90", "name": "Sicilian, Najdorf", "count": 28 }
  ]
}
```

---

## 4. 开局（/api/openings）

文件：[`backend/app/routes/openings.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/openings.py)

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/` | 公开 | 开局列表（分页、按 ECO 分类） |
| GET | `/<id>` | 公开 | 开局详情 |
| GET | `/<id>/games` | 公开 | 使用此开局的棋谱 |
| GET | `/tree` | 公开 | 开局树（前 6 步） |
| GET | `/rec` | 公开 | 识别开局（输入 moves 列表） |
| GET | `/similar` | 公开 | 相似开局推荐 |
| POST | `/identify` | 公开 | 按着法数组识别开局（JSON） |

**GET /api/openings/rec?moves=e4,e5,Nf3,Nc6**

```json
响应 200:
{
  "eco_code": "C42",
  "name": "Petrov's Defense",
  "popularity": 87
}
```

---

## 5. 分析（/api/analysis）

文件：[`backend/app/routes/analysis.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/analysis.py)

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/game/<game_id>/start` | 用户 | 启动棋谱异步分析（5/min） |
| GET | `/game/<game_id>/status` | 用户 | 查询该棋谱的最新任务状态 |
| GET | `/game/<game_id>` | 公开 | 获取棋谱分析结果 |
| GET | `/game/<game_id>/move/<n>` | 公开 | 单着分析（info） |
| GET | `/tasks/<task_id>` | 公开 | 按 UUID 查询任务 |
| GET | `/tasks` | 公开 | 最近 100 条任务列表 |
| DELETE | `/tasks/<task_id>` | 用户 | 取消 pending/running 的任务 |
| GET | `/engines` | 公开 | 引擎信息（路径、深度、Mock 状态） |

**POST /api/analysis/game/1/start**

```json
请求体:（可空，使用配置默认值）
{ "depth": 20, "threads": 1 }

响应 200:
{
  "message": "Analysis started",
  "task_id": "uuid-xxx",
  "game_id": 1
}
```

**GET /api/analysis/game/1/status**

```json
响应 200:
{
  "id": "uuid-xxx",
  "game_id": 1,
  "status": "running",     // pending / running / completed / failed / cancelled
  "progress": 35.5,        // 0-100
  "depth": 20,
  "threads": 1,
  "result": null,          // 完成时填充
  "error": null,
  "started_at": "...",
  "completed_at": null,
  "created_at": "..."
}
```

**GET /api/analysis/game/1**

```json
响应 200:
{
  "id": 5,
  "game_id": 1,
  "analysis_data": { "moves": [...], "key_moves": [...], "win_rate_curve": [...] },
  "key_moves": [...],
  "win_rate_curve": [...],
  "accuracy_white": 0.78,
  "accuracy_black": 0.72,
  "average_loss": 12.3,
  "engine_name": "Stockfish 17.1",
  "depth": 20,
  "created_at": "...",
  "updated_at": "..."
}
```

**GET /api/analysis/engines**

```json
响应 200:
{
  "engine": {
    "available": true,
    "is_mock": false,
    "path": "/usr/bin/stockfish",
    "version": "Stockfish 17.1 ...",
    "init_error": null
  },
  "config": { "depth": 20, "threads": 1, "hash_size": 256, "timeout": 300 }
}
```

**状态机**：`pending → running → completed | failed | cancelled`
任务存于 `analysis_tasks` 表（UUID 主键），多 worker 安全。
引擎初始化失败时自动降级 Mock 模式（`is_mock=true`），不会让服务崩溃。

---

## 6. 练习（/api/practice）

文件：[`backend/app/routes/practice.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/practice.py)

### 6.1 残局题

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/puzzles` | 公开 | 残局题列表（分页、过滤） |
| GET | `/puzzles/<id>` | 公开 | 残局详情（含最近 20 条练习记录） |
| POST | `/puzzles` | 用户 | 创建自定义残局（普通用户进入审核） |
| DELETE | `/puzzles/<id>` | 用户 | 删除我的残局（预设题禁止） |
| GET | `/search_games` | 公开 | 搜索棋谱（用于"从棋谱开始"） |

### 6.2 练习对局（session 模式，服务端内存）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/start` | 可选 | 开始练习（puzzle / from_game / custom） |
| POST | `/move` | 可选 | 提交走子（SAN）+ 立即获取 AI 应着 |
| POST | `/undo` | 可选 | 悔棋（撤回用户+AI两步） |
| POST | `/hint` | 可选 | 获取提示着法（标记使用次数） |
| POST | `/resign` | 可选 | 认输 |
| GET | `/status/<session_id>` | 可选 | 对局当前状态（fen/history/result） |

### 6.3 复盘

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/history` | 用户 | 我的练习历史（持久化记录） |
| GET | `/history/<id>` | 用户 | 练习详情 |
| POST | `/analyze/<practice_id>` | 用户 | 启动复盘分析（Stockfish） |
| GET | `/analyze/<practice_id>/status` | 用户 | 复盘分析状态 |
| GET | `/analyze/<practice_id>/result` | 用户 | 复盘分析结果 |

**POST /api/practice/start**

```json
请求体:
{
  "mode": "puzzle",          // puzzle | from_game | custom
  "user_color": "white",
  "difficulty": "medium",    // beginner/elementary/intermediate/advanced/expert
  "puzzle_id": 1,            // puzzle 模式必填
  "source_game_id": null,    // from_game 模式必填
  "from_move": 12,           // 从棋谱第 N 回合后开始
  "starting_fen": null       // custom 模式必填
}

响应 200:
{
  "session_id": "sess-xxxx",
  "mode": "puzzle",
  "difficulty": "medium",
  "user_color": "white",
  "start_fen": "8/8/...",
  "current_fen": "8/8/...",
  "active": true,
  "history": []
}
```

**POST /api/practice/move**

```json
请求体: { "session_id": "sess-xxxx", "move": "e4" }

响应 200:
{
  "user_move": { "san": "e4", "fen_after": "..." },
  "ai_move":   { "san": "c5", "fen_after": "...", "evaluation": 30 },
  "active": true,
  "result": null,
  "hints_used": 0,
  "undo_count": 0
}
```

> Session 410 表示过期/不存在（前端在 `request.js` 中标记 `_sessionExpired=true` 自动重置）。

**POST /api/practice/hint**

```json
请求体: { "session_id": "sess-xxxx" }

响应 200:
{ "hint": { "move": "Nf3", "evaluation": 28, "pv": [...] }, "hints_used": 1 }
```

**POST /api/practice/analyze/100/result**

```json
响应 200:
{
  "moves": [
    { "ply": 1, "san": "e4", "score_cp": 30, "win_rate": 0.55, "label": "neutral", "label_text": "中规中矩" },
    { "ply": 3, "san": "???", "score_cp": -350, "win_rate": 0.15, "label": "blunder", "label_text": "漏着" }
  ],
  "summary": { "accuracy_white": 0.78, "blunders": 2, "mistakes": 4, "inaccuracies": 5 }
}
```

---

## 7. 收藏（/api/collections）

文件：[`backend/app/routes/collections.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/collections.py)

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/` | 用户 | 我的收藏列表 |
| POST | `/` | 用户 | 添加收藏（重复会覆盖） |
| PUT | `/<id>` | 用户 | 更新备注 |
| DELETE | `/<id>` | 用户 | 取消收藏 |
| GET | `/check/<game_id>` | 用户 | 检查是否已收藏 |

**POST /api/collections**

```json
请求体:
{
  "game_id": 1,
  "note": "Carlsen 经典对局"
}

响应 201:
{
  "id": 1,
  "game_id": 1,
  "note": "Carlsen 经典对局",
  "created_at": "2024-01-15T10:30:00"
}
```

唯一约束 `(user_id, game_id)` 防止重复收藏。

---

## 8. 浏览历史（/api/browsing）

文件：[`backend/app/routes/browsing.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/browsing.py)

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/` | 用户 | 我的浏览历史（按时间倒序） |
| POST | `/` | 用户 | 记录浏览（重复刷新时间） |
| DELETE | `/<game_id>` | 用户 | 删除单条 |
| POST | `/clear` | 用户 | 清空全部 |

**POST /api/browsing**

```json
请求体: { "game_id": 1 }
```

唯一约束 `(user_id, game_id)`，重复浏览会刷新 `viewed_at`。

---

## 9. 赛事（/api/tournaments）

文件：[`backend/app/routes/tournaments.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/tournaments.py)

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/` | 公开 | 赛事列表 |
| GET | `/<id>` | 公开 | 赛事详情 |
| GET | `/<id>/games` | 公开 | 赛事的棋谱 |
| POST | `/` | 用户 | 创建赛事（提交审核） |
| PUT | `/<id>` | 用户 | 更新赛事 |
| DELETE | `/<id>` | 用户 | 删除赛事 |

---

## 10. 修改申请（/api/mod-requests）

文件：[`backend/app/traffic.py::submit_bp`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/traffic.py)

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/` | 用户 | 提交修改/删除/添加申请 |

> 实际端点：`POST /api/mod-requests`
> 对应前端 `submitModRequest`：`/mod-requests`

**POST /api/mod-requests**

```json
请求体:
{
  "target_type": "game",     // game | puzzle | collection | profile | player
  "action": "delete",        // create | update | delete
  "target_id": 42,
  "reason": "数据重复",
  "payload": { "key": "value" }   // create/update 时必填
}

响应 201:
{
  "message": "申请已提交，等待管理员审核",
  "request": { "id": 7, "status": "pending", "applicant_name": "user1", ... }
}
```

> 注：管理员 `target_type in ('game','collection')` + `action='delete'` 时会跳过审核直接执行。

---

## 11. 管理 API（/api/admin）

文件：[`backend/app/traffic.py::admin_api_bp`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/traffic.py)

所有端点要求 JWT + `is_admin=True`。

### 11.1 修改申请审核

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/mod-requests` | 列表（status 默认 `pending`，可传 `all`） |
| GET | `/mod-requests/<id>` | 申请详情 |
| POST | `/mod-requests/<id>/review` | 审核（`action: approve\|reject`，自动执行 payload） |

### 11.2 流量监控

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/traffic/recent` | 最近 N 条访问记录（默认 100，max 500） |
| GET | `/traffic/summary` | 总体/按路径/按用户/按小时聚合 |

### 11.3 用户管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/users` | 用户列表（含收藏/浏览/审核数/24h 调用） |
| PATCH | `/users/<id>` | 修改 `is_admin`/`email`（保护最后一个 admin） |
| POST | `/users/<id>/reset_password` | 重置密码 |
| DELETE | `/users/<id>` | 删除用户（级联清理，不可自删） |
| GET | `/stats` | 仪表板统计卡 |

### 11.4 高级可视化分析

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/analytics/heatmap` | 端点 × 小时 热力图（ECharts） |
| GET | `/analytics/user-activity` | 用户活跃度时间序列（游客/用户/管理员分桶） |
| GET | `/analytics/audit-stats` | 审核流状态分布 |
| GET | `/analytics/db-changes` | 数据库写入统计 |
| GET | `/analytics/endpoint-health` | 各端点健康度（错误率/平均耗时） |

**GET /api/admin/traffic/summary?hours=24**

```json
响应 200:
{
  "summary": {
    "total_requests": 1234, "unique_users": 12,
    "error_count": 8, "error_rate": 0.0065, "hours_window": 24
  },
  "by_path": [{ "path": "/api/games", "count": 320, "avg_ms": 18.4 }, ...],
  "by_user": [{ "username": "alice", "count": 200 }, ...],
  "by_hour": [{ "hour": "2024-01-15 10:00", "count": 80 }, ...]
}
```

---

## 12. 系统端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 系统概览 HTML（含数据库统计） |
| GET | `/api/health` | 健康检查 `{status:ok, games:N}` |
| GET | `/api/openapi.json` | 302 重定向到 `/apispec_1.json` |
| GET | `/apidocs/` | Swagger UI（Flasgger） |
| GET | `/admin/` | Flask-Admin Web 后台 |

---

## 错误码规范

| 状态码 | 含义 | 前端处理 |
|--------|------|----------|
| 200/201/202 | 成功 | 直接展示 |
| 400 | 参数错误 | `ElMessage.error` |
| 401 | 未登录 / Token 过期 | 跳转 `/login?redirect=...` |
| 403 | 无权限 | 提示 |
| 404 | 资源不存在 | 提示 |
| 409 | 资源冲突 | 提示（已审核过/邮箱已用） |
| 410 | 会话过期 | 标记 `_sessionExpired=true`，重置 UI |
| 422 | 数据验证失败 | 提示 |
| 429 | 限流 | 提示稍后再试 |
| 500 | 服务器错误 | 提示 |

请求拦截器：[`frontend/src/api/request.js`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/frontend/src/api/request.js)
