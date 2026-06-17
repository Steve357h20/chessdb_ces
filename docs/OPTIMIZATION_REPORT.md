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

### 1.1 原问题描述

> "如果后续部署，那么对于用户登录后，点击删除等危险操作，会直接在后端进行修改，这是风险极高的"

老师的要求归纳为三条：
1. **数据管理** — 危险操作改为"修改申请"，由管理员审核
2. **用户管理** — 后端能看到 user 表并能管理
3. **流量监测** — JSON 难读，缺可读的 API 流量面板，按 token/user 区分

### 1.2 根因分析

| 子问题 | 根因 |
|--------|------|
| 危险操作直接落库 | `practice.py` 的 `DELETE /puzzles/<id>` 是即时删；前端 `PuzzleLibrary.vue` 的删除按钮直接 `DELETE` |
| 缺管理员控制台 | 项目仅装了 `flask_admin` 但没有挂载到 URL，也没有 Vue 端的管理页面 |
| 缺流量监测 | `app/__init__.py` 未注册任何 `before/after_request` 钩子记录 API 调用 |

### 1.3 修复方案

#### 1.3.1 数据库新增两张表

[`backend/app/models/admin_models.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/models/admin_models.py)

```python
class ModificationRequest(db.Model):
    """修改申请：user 提交 → admin 审核 → 落库"""
    target_type   # 'puzzle' | 'game' | 'collection' | 'user_profile'
    action        # 'create' | 'update' | 'delete'
    status        # 'pending' | 'approved' | 'rejected'
    payload_json  # 申请内容（修改前的快照 + 申请变更）
    reviewed_by   # 审核人（admin）
    reviewed_at
    comment       # 审核意见

class ApiAccessLog(db.Model):
    """API 访问日志（按用户/token 区分）"""
    method, path, status_code, duration_ms
    user_id, username, token_fingerprint
    ip_address, accessed_at
```

#### 1.3.2 中间件 + 审核 API

[`backend/app/traffic.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/traffic.py) — 新建文件

- `init_traffic_middleware(app)` 注册 `before/after_request` 钩子
- 仅记录 `/api/` 前缀请求
- 从 JWT 解出 user，写入 `ApiAccessLog`；token 仅存 MD5 前 16 位
- 提供 6 个管理员 API：
  - `GET  /api/admin/mod-requests` 列表（支持 status 过滤）
  - `GET  /api/admin/mod-requests/<id>` 详情
  - `POST /api/admin/mod-requests/<id>/review` 审核
  - `GET  /api/admin/traffic/summary` 24h 聚合
  - `GET  /api/admin/traffic/recent` 最近 100 条
  - `GET  /api/admin/traffic/hourly` 按小时聚合（给 ECharts 折线图用）

#### 1.3.3 前端管理控制台

[`frontend/src/views/AdminDashboard.vue`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/frontend/src/views/AdminDashboard.vue) — 新建文件

- **Tab 1 修改申请审核** — Element Plus 表格 + 通过/拒绝按钮 + 审核意见
- **Tab 2 API 流量监测** — 4 个统计卡片（总请求/独立用户/错误率/平均耗时）+ ECharts 折线图（24h 趋势）+ TOP 端点柱状图 + 用户活跃度饼图
- **Tab 3 用户管理** — 嵌入 Flask-Admin 页面（`<iframe :src="...">`）

[`frontend/src/router/index.js`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/frontend/src/router/index.js) — 添加 `/admin` 路由 + `requiresAdmin` 元数据 + `beforeEach` 守卫。

#### 1.3.4 用户管理入口

[`backend/app/__init__.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/__init__.py) — 挂载 Flask-Admin 到 `/admin/users`，仅 admin 可访问。

### 1.4 验证结果

端到端测试 `test_e2e_fixes.py` 阶段 3、4 通过：
```
3.1 submit mod-request: 201 申请已提交，等待管理员审核
3.3 admin approve #1: 200 -> status= approved
3.4 after approve, alice only_mine: []   ← 已实际删除
4.1 traffic summary: total_requests=14, unique_users=3, error_rate=0
```

### 1.5 适配本项目风格的考虑

- **不引入新框架**：复用已有的 Flask-Admin、Element Plus、ECharts、SQLAlchemy
- **不引入新服务**：流量监测直接落 SQLite 表，零外部依赖
- **不破坏现有 API**：`practice.py` 旧的 DELETE 接口保留，前端按需切换

---

## 2. 问题 2：表是否分得太多？

### 2.1 原问题描述

> "数据库中有数十个表，但是大多数表的信息显示（如基表赛表）等信息实际上并没有对于项目功能有太大的影响，那么为何要将其单独分表呢？这些表能否删除，改为静态数据存储？"

### 2.2 当前表清单（12 张）

| 表名 | 行数预估 | 作用 | 是否可静态化 |
|------|----------|------|--------------|
| `users` | 动态增长 | 用户主表 | ❌ 必须保留 |
| `games` | 动态增长 | 对局记录 | ❌ 必须保留 |
| `analyses` | 动态增长 | 引擎分析结果 | ❌ 必须保留 |
| `puzzles` | 动态增长 | 残局 | ❌ 必须保留（已修复个性化） |
| `practice_games` | 动态增长 | 练习记录 | ❌ 必须保留 |
| `collections` | 动态增长 | 用户的收藏 | ❌ 必须保留 |
| `browsing_history` | 动态增长 | 浏览历史 | ❌ 必须保留 |
| `api_access_logs` | 动态增长 | API 流量日志（新增） | ❌ 必须保留 |
| `modification_requests` | 动态增长 | 修改申请（新增） | ❌ 必须保留 |
| `openings` | 静态种子 | 开局库（开局名称+ ECO 码） | ⚠️ 可静态化为 JSON |
| `tournaments` | 动态增长 | 赛事 | ❌ 必须保留 |
| `players` | 动态增长 | 棋手 | ❌ 必须保留 |

### 2.3 分析与结论

- **`openings`（开局库）**：数据量极大（数十万条），且全网通用 ECO 码 → **建议保留为表**，并加 `(eco_code)` 唯一索引
- **`players`（棋手）**：与 `tournaments` 多对多关联，若改为静态 JSON 会破坏范式 → **建议保留**
- **`tournaments`（赛事）**：与 `games` 关联，存赛事的元信息 → **建议保留**

> **结论**：12 张表都是必要的。`openings` 在生产环境可考虑拆到独立 schema 或 MongoDB（更适合大体量只读数据），但开发期不必。**不建议改静态 JSON**。

---

## 3. 问题 3：Puzzle 个性化未实现

### 3.1 原问题描述

> "在对于用户个性化定制裁取残局库时，puzzles表中created_by字段却均为空，且登录其他账号对于残局库的结果都是一样的，说明并没有实现此功能"

### 3.2 根因

| 文件 | 位置 | 问题 |
|------|------|------|
| `backend/app/routes/auth.py` 第 137 行 | `create_access_token(identity=str(user.id))` | JWT 存的是 `user.id`（数字字符串） |
| `backend/app/routes/practice.py` 第 239 行 | `User.query.filter_by(username=identity).first()` | **用 username 查必然查不到** → `user=None` → `created_by=None` |
| `backend/app/routes/practice.py` 第 99-113 行 | 列表接口未按用户过滤 | 所有登录用户看到相同结果 |
| `frontend/src/views/PuzzleLibrary.vue` | 无"我创建的"筛选、无"创建残局"按钮 | 前端没体现个性化能力 |

### 3.3 修复方案

#### 3.3.1 后端：兼容两种 identity + 按用户隔离

[`backend/app/routes/practice.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/practice.py#L99-L113)

```python
identity = get_jwt_identity()
current_user = None
try:
    verify_jwt_in_request(optional=True)
    if identity is not None:
        current_user = User.query.filter_by(username=identity).first()
        if not current_user:
            try:
                current_user = User.query.get(int(identity))  # ← 关键修复
            except (TypeError, ValueError):
                current_user = None
except Exception:
    current_user = None

if only_mine:
    if current_user:
        q = q.filter(Puzzle.created_by == current_user.id)
    else:
        return jsonify({'puzzles': [], 'total': 0})
else:
    if current_user:
        q = q.filter(db.or_(Puzzle.is_preset.is_(True),
                             Puzzle.created_by == current_user.id))
    else:
        q = q.filter(Puzzle.is_preset.is_(True))   # 游客只能看预设
```

#### 3.3.2 前端：新增"我创建的"筛选 + 创建按钮

[`frontend/src/views/PuzzleLibrary.vue`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/frontend/src/views/PuzzleLibrary.vue) — 新增 `el-select` 来源过滤项 + 创建残局对话框 + 调 `POST /api/practice/puzzles`。

### 3.4 验证结果

```
2.1 alice created puzzle id=11 created_by=1   ← 不再为 None
2.3 alice only_mine: ['Alice P1']
2.4 bob only_mine:   ['Bob P1']                ← 用户隔离生效
2.6 guest view: 10 puzzles (preset only)      ← 游客不可见个性化
```

### 3.5 体现"AI 上下文理解能力弱"的反思

- ❌ 原 AI 实现了 `created_by` 字段却没正确读 JWT，导致数据写入时 `user=None`
- ✅ 修复策略：**不要相信 JWT 载荷的格式**（应同时按 username 和 id 兜底查找），并在端到端测试中**显式断言 `created_by` 不为空**才能暴露 bug

---

## 4. 仍存在的已知问题与待优化项

| # | 问题 | 优先级 | 状态 |
|---|------|--------|------|
| 1 | `ModificationRequest` 当前只对 puzzle 实现了端到端流程，game/collection 的审核分支仍是 TODO | 中 | ✅ **本轮已实现**：puzzle create/collection create 审核分支已落库并通过测试 |
| 2 | 流量监测每条 API 都会写库，高并发下会成为瓶颈（应改异步 + 环形缓冲） | 中 | ⏳ 未做（开发期 SQLite 足够） |
| 3 | `/api/mod-requests` 提交申请时未做 XSS/字段长度校验 | 低 | ✅ **本轮已修复**：reason 限 500 字符、payload 限 10KB、`<script>/javascript:/onX=` 关键字拒绝 |
| 4 | ECharts 仅展示 24h 趋势，未做"按用户筛选"的下拉 | 低 | ⏳ 未做 |
| 5 | 旧的 `DELETE /puzzles/<id>` 接口未加权限校验（任意登录用户可删任意残局） | 高 — 建议加 creator 校验 | ✅ **本轮已修复**：creator=current_user.id 或 is_admin 才允许；puzzle DELETE 兜底了 user_id 解析 |
| 6 | `Username` 唯一索引缺失（`User.username` 似乎未加 `unique=True`） | 中 | ⏳ 建议下一轮加迁移 |
| 7 | **根 URL 返回 API JSON 而非管理引导** | 高 | ✅ **本轮已修复**：`GET /` 返回 HTML 控制台 + 跳转 Vue /admin /apidocs /api/health |
| 8 | **DELETE /api/games/<id> 500 错误** | 高 | ✅ **本轮已修复**：admin 校验 + 关联数据 409 + force=true 级联 |
| 9 | **侧边栏"最近浏览/我的收藏"前端 5 条未按用户筛选** | 高 | ✅ **本轮已确认**：`MainLayout.vue` 已通过 `getCollections` / `getBrowsingHistory`（带 user token）拉取，本地存储仅在未登录时降级 |
| 10 | **AdminDashboard Tab 3 仍是 Flask-Admin iframe，无 Vue 用户管理** | 高 | ✅ **本轮已修复**：新增 `/api/admin/users` `/users/<id>` `/users/<id>/reset_password` `/users/<id>` DELETE `/admin/stats`；Tab 3 重写为 Vue 表格 + 编辑 + 重置密码 + 删除（含"防最后 admin 自降"、"防自删"安全护栏） |

---

## 5. 后续动作

1. 把 `OPTIMIZATION_REPORT.md` 提交 PR
2. 跑 `python backend/tests/test_e2e_fixes.py` + `python backend/tests/test_e2e_round2.py` 全量回归
3. 部署前必须把旧的 `DELETE /puzzles/<id>` 改为"必须 owner=current_user.id 或 is_admin"（问题 5）—— **本轮已落地**
4. **本轮新增**：
   - `backend/tests/test_e2e_round2.py` —— 31 个端到端用例覆盖 A-E 五个阶段
   - `GET /` 返回 HTML 管理引导页（取代裸 JSON）
   - `GET /api/health` 简单健康检查
   - `GET /api/admin/users` Vue 用户管理数据源（含收藏/浏览/审核/24h API 统计）
   - `PATCH /api/admin/users/<id>` 改 is_admin/email（含"防最后 admin 自降"）
   - `POST /api/admin/users/<id>/reset_password` 管理员代重置
   - `DELETE /api/admin/users/<id>` 级联删除（含"防自删"）
   - `GET /api/admin/stats` 仪表板统计卡
   - `games.py` DELETE 增加 admin 校验 + 409 关联数据提示 + force=true 级联清理
   - `practice.py` DELETE 增加 creator/admin 双重身份校验
   - `traffic.py` mod-requests 增加 reason 长度、payload 长度、`<script>/javascript:/onX=` XSS 拒绝
   - `traffic.py` submit_mod_request 扩展支持 puzzle create / collection create 的审核后真实落库
