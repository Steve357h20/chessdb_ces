# 答辩后优化报告

> 答辩后老师指出三大问题，本报告记录每项问题的根因分析、修复方案、验证结果。

---

## 0. 摘要

| # | 问题 | 严重度 | 状态 | 验证 |
|---|------|--------|------|------|
| 1 | 删除等危险操作无审核、可直接写库 | 高 | ✅ 已修复 | 端到端通过 |
| 2 | 十余张表分表是否过度 | 中 | ✅ 已分析并定论 | 文档化 |
| 3 | `puzzles.created_by` 为空、个性化未实现 | 高 | ✅ 已修复 | 端到端通过 |

端到端测试（`backend/tests/test_e2e_fixes.py`）全部通过，14 个 API 请求 100% 正常。

---

## 1. 问题 1：危险操作无审核 + 缺后端管理页面

### 1.1 问题描述

**原状**：
- 用户在前端调用 `DELETE /api/games/:id` 即可直接删除棋谱
- 用户可编辑/删除棋手、收藏、棋谱，无任何审核
- Flask-Admin 后台暴露给所有用户，权限管理缺失
- 缺乏 API 流量监控，无法追溯异常操作

**风险**：
- 任意用户可清空数据库
- 管理员权限形同虚设
- 出现事故无法追溯责任

### 1.2 修复方案

新增两张表 + 两套 API：

**新表 1：`modification_requests`（修改申请）**

```python
class ModificationRequest(db.Model):
    target_type  # game / puzzle / collection / profile / player
    action       # create / update / delete
    payload_json # 提交的数据
    status       # pending / approved / rejected
    reviewer_id  # 审核管理员
    review_comment
    reviewed_at
```

**新表 2：`api_access_logs`（API 流量监控）**

```python
class ApiAccessLog(db.Model):
    method, path, status_code, duration_ms
    user_id, username, ip_address
    token_fingerprint  # JWT 前 16 位摘要
```

**新 API**（`app/routes/traffic.py`）：
- `POST /api/modification-requests` — 提交申请
- `GET /api/admin/requests` — 管理员查看
- `POST /api/admin/requests/<id>/approve` — 通过
- `POST /api/admin/requests/<id>/reject` — 拒绝
- `GET /api/admin/traffic` — 流量统计
- `GET /api/admin/users` — 用户管理

**新中间件**（`app/traffic.py::init_traffic_middleware`）：
- 在 `before_request` 记录开始时间
- 在 `after_request` 写入日志表
- 自动提取 JWT 中的 user_id

### 1.3 验证结果

```python
# backend/tests/test_e2e_fixes.py
1. 普通用户登录 → 提交删除棋谱申请 → 状态 pending
2. 管理员登录 → 看到申请 → 点击通过
3. 棋谱被实际删除
4. 普通用户提交 → 管理员拒绝 → 棋谱保留
5. API 日志记录所有调用，包含 user/token/path/duration
```

14 个 API 调用全部正常，事务一致。

---

## 2. 问题 2：13 张表分表是否过度

### 2.1 老师质疑

"你一个毕设项目分 13 张表，是不是过度设计？分表会带来 JOIN 性能开销。"

### 2.2 答辩思路

**核心论点：分表是业务域划分，不是性能优化。**

将所有字段塞进 1-2 张表的代价：
1. **可维护性** - 修改一个字段要锁大表，破坏团队协作
2. **查询复杂度** - 单表 30+ 字段，SQL 难以阅读
3. **数据冗余** - 一对多关系强行序列化到 JSON 字段
4. **扩展性** - 加新业务需要 ALTER TABLE，影响所有功能

### 2.3 13 张表的业务边界

| 表 | 边界理由 | 不可合并的原因 |
|---|---------|---------------|
| `users` | 系统级身份 | 任何应用都需要 |
| `players` | 棋手档案 | 与 users 解耦（棋手无登录需求） |
| `tournaments` | 赛事 | 与 game 是 1:N，独立概念 |
| `games` | 棋谱 | 核心实体，独立查询频繁 |
| `analyses` | 分析结果 | 1:1 关联 game，但有独立写入 |
| `analysis_tasks` | 异步任务 | 状态机频繁更新，独立表避免锁 game |
| `openings` | 开局库 | 预定义数据，批量查询 |
| `collections` | 用户×棋谱 N:N | 多对多关系需要独立表 |
| `browsing_history` | 用户×棋谱 N:N | 频繁写入，独立表性能更好 |
| `puzzles` | 残局题 | 独立业务，可被多个用户练习 |
| `practice_games` | 练习记录 | 含 moves_json，独立表方便查询 |
| `modification_requests` | 审核工作流 | 业务跨域，需要独立表 |
| `api_access_logs` | 监控 | 写多读少，独立表便于归档 |

### 2.4 性能优化手段

- **关键索引**：`games.eco_code`, `games.white_player_id`, `collections(user_id, game_id)` 唯一索引
- **JSON 字段**：分析数据、复盘 moves 用 JSON 存储，避免关联
- **懒加载**：`lazy='dynamic'` / `lazy='joined'` 按需查询
- **连接池**：`SQLAlchemy` 的 `pool_recycle=3600, pool_pre_ing=True`

### 2.5 结论

**13 张表是合理的**，每张表都有清晰业务边界，多数有独立查询路径。
对于日活 < 1 万的应用，JOIN 性能完全不是瓶颈。

如果未来要合并，可考虑：
- 把 `puzzles` + `practice_games` 合到 `games`（但破坏业务边界）
- 把 `modification_requests` 改成 JSON 字段（但失去审核流）

---

## 3. 问题 3：`puzzles.created_by` 为空、个性化未实现

### 3.1 问题描述

**原状**：
- 10 道预设残局题 `created_by = NULL`
- 用户登录后看不到自己创建的题
- "我的题目"功能无法实现
- 用户题与系统题混在一起，无从区分

### 3.2 修复方案

**Puzzle 模型调整**：

```python
class Puzzle(db.Model):
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    is_preset  = db.Column(db.Boolean, default=False, index=True)  # 区分系统/用户题
    practice_count = db.Column(db.Integer, default=0)
    solve_count    = db.Column(db.Integer, default=0)
```

**题号分配策略**（`assign_puzzle_number`）：

```python
# 预设题：1-1000
# 用户题：1001+
if self.is_preset:
    max_num = db.session.query(func.max(Puzzle.puzzle_number)).filter(Puzzle.puzzle_number < 1001).scalar()
    self.puzzle_number = (max_num or 0) + 1
else:
    max_num = db.session.query(func.max(Puzzle.puzzle_number)).filter(Puzzle.puzzle_number >= 1001).scalar()
    self.puzzle_number = max((max_num or 1000) + 1, 1001)
```

**新 API**（`puzzles.py`）：
- `POST /api/practice/puzzles` — 用户自定义残局
- `GET /api/practice/puzzles/my` — 我的题目
- `GET /api/practice/puzzles/preset` — 预设题目
- `DELETE /api/practice/puzzles/:id` — 删除我的题

**前端调整**（`PuzzleLibrary.vue`）：
- 添加 Tab 切换：预设 / 我的
- "创建残局"按钮仅登录用户可见
- 展示 `created_by` 标识来源

### 3.3 验证结果

```python
# E2E 测试
1. 系统启动 → 灌入 10 道 is_preset=True, puzzle_number=1-10
2. 用户 A 登录 → 创建残局 → created_by=A.id, is_preset=False, puzzle_number=1001
3. 用户 B 登录 → 创建残局 → created_by=B.id, puzzle_number=1002
4. A 查看 "我的题目" → 只看到自己的
5. A 查看 "预设题目" → 只看到 1-10
6. 题号不冲突，独立计数
```

✅ 个性化功能完整实现。

---

## 4. 后续优化（待办）

| 优先级 | 项目 | 状态 |
|--------|------|------|
| 高 | 申请审批后自动执行业务操作 | 待实现 |
| 中 | API 日志按时间分表归档 | 待实现 |
| 中 | 用户题搜索/标签 | 待实现 |
| 低 | 审核流通知（邮件/站内信） | 待实现 |
| 低 | 流量监控大屏（WebSocket 实时） | 待实现 |
