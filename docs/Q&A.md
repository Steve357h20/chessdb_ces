# 项目技术问答（答辩准备）

> 本文档针对项目各技术要点进行深入解答，所有代码引用均标注具体文件与行号。

---

## 问题 1：JWT Token 是什么？时间限制如何实现？

### 1.1 Token 是什么？

**Token 不是请求，而是"令牌"——一种身份凭证。**

JWT（JSON Web Token）是一种开放标准（RFC 7519），用于在各方之间安全地传输信息。在本项目中，JWT Token 的作用是**代替用户名+密码，在后续每次请求中证明"我是谁"**。

**类比理解**：Token 就像酒店房卡。入住时用身份证（用户名+密码）办理登记，前台给你一张房卡（Token）。之后进入房间、使用健身房等，只需刷房卡，不需要每次都出示身份证。

**Token 的结构**（三段用 `.` 分隔的 Base64 字符串）：

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
│             头部(Header)              │                载荷(Payload)                 │        签名(Signature)       
```

- **Header**：声明算法类型（如 HS256）
- **Payload**：存放用户身份信息（如 `user_id`）
- **Signature**：用密钥对前两部分签名，防止篡改

### 1.2 Token 的生成

在用户注册和登录时，后端通过 `Flask-JWT-Extended` 库生成 Token：

**文件**: `backend/app/routes/auth.py`

```python
# 第 86 行 — 登录成功后生成 Token
access_token = create_access_token(identity=str(user.id))
```

`create_access_token` 是 Flask-JWT-Extended 提供的函数，它：
1. 将 `user.id` 编码进 Payload 的 `sub`（subject）字段
2. 设置签发时间 `iat` 和过期时间 `exp`
3. 用 `JWT_SECRET_KEY` 进行 HMAC-SHA256 签名

### 1.3 Token 的时间限制如何实现？

**不是用 `datetime` 实时获取来计时，而是在 Token 生成时就写入了过期时间戳（`exp` claim）。**

**文件**: `backend/config.py` 第 14 行：

```python
JWT_ACCESS_TOKEN_EXPIRES = 86400  # 秒数，即 24 小时
```

**工作原理**：

1. **生成时**：`create_access_token` 读取配置 `JWT_ACCESS_TOKEN_EXPIRES`，计算 `exp = 当前时间 + 86400秒`，将 `exp` 写入 Token 的 Payload
2. **验证时**：每次受保护的路由使用 `@jwt_required()` 装饰器，Flask-JWT-Extended 自动解码 Token，检查 `exp` 字段是否大于当前时间。如果过期，返回 401 错误
3. **前端处理**：收到 401 时自动跳转登录页

**文件**: `frontend/src/api/request.js` 第 62-78 行：

```javascript
case 401:
  handleTokenExpired()  // 清除本地 Token，跳转登录页
  break
```

**关键理解**：Token 的过期验证是**无状态**的——服务器不需要存储任何会话信息，只需通过密钥验证签名和 `exp` 字段即可。这也是 JWT 与传统 Session 的核心区别。

### 1.4 Token 的使用流程

```
1. 用户登录 → 后端返回 Token
2. 前端存储 Token 到 localStorage
   （文件: frontend/src/store/userStore.js 第 19-20 行）
3. 每次请求自动附加 Token 到 Header
   （文件: frontend/src/api/request.js 第 13-16 行）
4. 后端通过 @jwt_required() 验证 Token 有效性
5. Token 过期 → 401 → 前端跳转登录页
```

---

## 问题 2：ECharts 图表技术栈、特点、为何不用 Matplotlib、分析方法

### 2.1 ECharts 与 Vue-ECharts

本项目使用 **Apache ECharts 5.5** + **vue-echarts 6.6** 进行图表绘制。

- **ECharts**：百度开源的 JavaScript 可视化库，运行在浏览器端
- **vue-echarts**：ECharts 的 Vue 3 封装组件，提供响应式绑定

**文件**: `frontend/package.json` 依赖声明：
```
"echarts": "^5.5.0"
"vue-echarts": "^6.6.0"
```

### 2.2 Vue + ECharts 的特点与功能

**Vue 的特点**：
- **响应式数据绑定**：数据变化自动更新视图，无需手动操作 DOM
- **组件化开发**：将 UI 拆分为独立、可复用的组件
- **虚拟 DOM**：高效计算最小 DOM 变更，提升渲染性能
- **Composition API**：逻辑按功能组织而非按选项类型，提高代码可读性和复用性

**ECharts 的特点**：
- **丰富的图表类型**：折线图、散点图、热力图、箱线图、饼图等 30+ 种
- **交互能力强**：缩放、拖拽、Tooltip、数据筛选
- **高性能渲染**：Canvas/SVG 双引擎，支持百万级数据
- **主题定制**：支持亮色/暗色主题切换
- **数据缩放**：`dataZoom` 组件支持区域选择浏览

### 2.3 为何使用 ECharts 而非 Matplotlib？

| 对比维度 | ECharts | Matplotlib |
|----------|---------|------------|
| **运行环境** | 浏览器（前端） | Python 进程（后端） |
| **交互性** | 原生支持缩放、Tooltip、点击事件 | 静态图片，无交互 |
| **实时更新** | 数据变化自动重绘 | 需重新生成图片 |
| **网络开销** | 仅传输 JSON 数据 | 需传输图片二进制 |
| **主题适配** | 亮色/暗色实时切换 | 需预生成两套图片 |
| **适用场景** | Web 应用前端可视化 | 数据分析报告、论文图表 |

**核心原因**：本项目是 Web 应用，用户需要**交互式**图表（如点击胜率曲线跳转到对应着法、缩放查看局部数据），Matplotlib 生成的是静态图片，无法满足交互需求。且 ECharts 直接在前端渲染，无需后端生成图片再传输，性能更优。

**文件**: `frontend/src/components/WinRateChart.vue` 第 246 行的 `@click` 事件：
```javascript
function onChartClick(params) {
  if (params.componentType === 'series') {
    emit('move-select', params.dataIndex + 1)  // 点击图表跳转到对应着法
  }
}
```

### 2.4 本项目使用的分析方法

本项目**没有使用** K-Means 聚类、线性拟合等机器学习算法。使用的是**统计描述性分析方法**，核心计算在**后端 SQL 聚合查询**中完成，前端仅负责可视化呈现。

以下逐一详解每个图表的分析方法：

---

#### 2.4.1 ELO vs 平均步数 — 折线图 + 散点图

**分析方法：等宽分桶聚合（Equal-Width Binning + Group Aggregation）**

**后端**：`backend/app/routes/games.py` 第 737-754 行

```python
# 将 ELO 均分按 10 分一桶分组
avg_elo_expr = func.round((Game.white_elo + Game.black_elo) / 2.0 / 10) * 10

query = db.session.query(
    avg_elo_expr.label('avg_elo_bucket'),        # 分桶键
    func.avg(Game.total_moves).label('avg_moves'), # 桶内平均步数
    func.count(Game.id).label('game_count'),       # 桶内对局数
).group_by(avg_elo_expr)
```

**原理**：
1. 计算每局棋的 ELO 均分 = `(白方ELO + 黑方ELO) / 2`
2. 将 ELO 均分按 10 分一桶离散化（如 2400-2409 → 2400）
3. 对每个桶计算 `AVG(total_moves)` 和 `COUNT(id)`
4. 前端用折线图展示趋势，散点图展示原始分布（点大小=对局数量）

**散点图**（`Stats.vue` 第 355-410 行）：随机采样 5000 局，展示每局的 ELO 均分 vs 步数的原始分布，颜色映射 ELO 差距（`|白方ELO - 黑方ELO|`）。

---

#### 2.4.2 热力密度图 — ELO × 步数二维分布

**分析方法：二维分箱统计（2D Histogram / Binning）**

**后端**：`backend/app/routes/games.py` 第 778-791 行

```python
# ELO 按 50 分一格，步数按 10 步一格
elo_bucket_50 = cast(cast(avg_elo / 50, Integer) * 50, Integer)
move_bucket_10 = cast(cast(Game.total_moves / 10, Integer) * 10, Integer)

density_rows = db.session.query(
    elo_bucket_50.label('elo_b'),
    move_bucket_10.label('move_b'),
    func.count(Game.id).label('cnt'),
).group_by(elo_bucket_50, move_bucket_10)
```

**原理**：
1. 将二维空间（ELO × 步数）划分为网格（ELO 每 50 分一格，步数每 10 步一格）
2. 统计每个网格内的对局数量 `COUNT(id)`
3. 前端用热力图渲染：颜色深浅 = 对局密度（深蓝=多，浅绿=少）
4. 这本质上是对二维联合分布的离散估计，类似二维直方图

**前端**：`Stats.vue` 第 198-310 行 — ECharts `heatmap` 类型，`visualMap` 映射计数到颜色梯度。

---

#### 2.4.3 箱线图 — 步数分布的五数概括

**分析方法：均值 ± 标准差 + 极值范围（Mean ± Std + Min/Max）**

**后端**：`backend/app/routes/games.py` 第 794-822 行

```python
dist_rows = db.session.query(
    elo_bucket_50.label('elo_b'),
    func.count(Game.id).label('cnt'),
    func.min(Game.total_moves).label('min_moves'),     # 最小值
    func.max(Game.total_moves).label('max_moves'),     # 最大值
    func.avg(Game.total_moves).label('mean_moves'),    # 均值
    func.avg(Game.total_moves * Game.total_moves).label('mean_sq_moves'),  # 均方值
).group_by(elo_bucket_50)

# 方差 = E[X²] - (E[X])²  （利用方差的计算公式）
variance = mean_sq - mean_val * mean_val
std_val = (variance ** 0.5) if variance > 0 else 0
```

**原理**：
1. 按 ELO 每 50 分一桶分组
2. 对每桶计算：`MIN`（最小步数）、`MAX`（最大步数）、`AVG`（均值）
3. **标准差的计算**：利用公式 `Var(X) = E[X²] - (E[X])²`，只需 SQL 聚合 `AVG(X)` 和 `AVG(X²)` 即可，无需加载原始数据到 Python
4. 前端渲染为自定义箱线图：
   - 外框（绿色）：极值范围 [min, max]
   - 内框（蓝色）：均值 ± 标准差 [mean-std, mean+std]
   - 横线（蓝色粗线）：均值
   - 虚线（橙色）：各桶均值连线

**注意**：本项目使用的是"均值±标准差"而非传统箱线图的"四分位数"（Q1/Q2/Q3），因为 SQL 计算四分位数需要窗口函数，实现更复杂。均值±标准差在数据近似正态分布时等价于约 68% 的数据范围。

---

#### 2.4.4 步数分布直方图

**分析方法：一维频率分布统计（1D Histogram）**

**前端**：`Stats.vue` 第 598-640 行

```javascript
// 前端对散点数据做分桶统计
const bins = {}
const step = 10
for (const s of scatter.value) {
  const bucket = Math.floor(s.total_moves / step) * step  // 每 10 步一桶
  bins[bucket] = (bins[bucket] || 0) + 1
}
```

**原理**：
1. 将步数按 10 步一桶离散化（0-9, 10-19, 20-29, ...）
2. 统计每个桶内的对局数量
3. 用柱状图展示频率分布

**与后端分桶的区别**：直方图的分桶在前端完成（基于已加载的 scatter 数据），而热力图的分桶在后端 SQL 完成（因为需要全量数据）。

---

#### 2.4.5 开局胜率排行 — 堆叠柱状图

**分析方法：分组条件计数 + 百分比计算（Conditional Count + Percentage）**

**后端**：`backend/app/routes/games.py` 第 835-870 行

```python
openings_query = db.session.query(
    Game.eco_code,
    func.count(Game.id).label('total'),
    func.sum(case((Game.result == '1-0', 1), else_=0)).label('white_wins'),
    func.sum(case((Game.result == '0-1', 1), else_=0)).label('black_wins'),
    func.sum(case((Game.result == '1/2-1/2', 1), else_=0)).label('draws'),
).group_by(Game.eco_code).order_by(func.count(Game.id).desc()).limit(50)

# 胜率 = 该结果次数 / 总对局数 × 100
'white_win_rate': round((r.white_wins or 0) / total * 100, 1)
```

**原理**：
1. 按 `eco_code` 分组
2. 使用 SQL `CASE WHEN` 条件表达式分别计数白胜/黑胜/和棋
3. 计算百分比：`白胜率 = 白胜数 / 总数 × 100%`
4. 前端用堆叠水平柱状图展示，每段代表一种结果的比例

---

#### 2.4.6 开局分类饼图

**分析方法：分类频数统计（Category Frequency Count）**

**后端**：`backend/app/routes/games.py` 第 872-890 行

```python
# 按 ECO 首字母（A/B/C/D/E）分组统计
categories_query = db.session.query(
    func.substr(Game.eco_code, 1, 1).label('category'),
    func.count(Game.id).label('total'),
).group_by(func.substr(Game.eco_code, 1, 1))
```

**原理**：ECO 编码首字母代表开局大类（A=不规则、B=半开放、C=开放、D=双兵、E=印度防御），按首字母分组计数即可得到各类开局的使用频率。

---

#### 2.4.7 开局-ELO 关系热力图

**分析方法：二维交叉统计（Cross Tabulation / Contingency Table）**

**后端**：`backend/app/routes/games.py` 第 894-920 行

```python
# 开局分类 × ELO桶（每500分一桶）
elo_bucket_expr = cast(cast((Game.white_elo + Game.black_elo) / 2.0 / 500, Integer) * 500, Integer)

elo_openings_query = db.session.query(
    func.substr(Game.eco_code, 1, 1).label('category'),
    elo_bucket_expr.label('elo_bucket'),
    func.count(Game.id).label('total'),
).group_by(func.substr(Game.eco_code, 1, 1), elo_bucket_expr)
```

**原理**：同时按开局分类和 ELO 桶两个维度分组，统计每个交叉组合的对局数，形成列联表（Contingency Table），用热力图可视化。

---

#### 2.4.8 胜率曲线 — 移动平均平滑

**分析方法：3 点移动平均（3-Point Moving Average）**

**前端**：`frontend/src/components/WinRateChart.vue` 第 38-48 行

```javascript
for (let i = 0; i < raw.length; i++) {
  const start = Math.max(0, i - 1)
  const end = Math.min(raw.length - 1, i + 1)
  let sum = 0, count = 0
  for (let j = start; j <= end; j++) {
    if (raw[j] != null) { sum += raw[j]; count++ }
  }
  smoothed.push(Math.round(sum / count * 100) / 100)
}
```

**原理**：对原始胜率序列做 3 点窗口平滑，每个点取前后各 1 个邻居的平均值，消除单步波动噪声，使曲线更平滑。这是最简单的低通滤波器。

---

### 2.5 分析方法总结

| 图表 | 分析方法 | 数学本质 | 计算位置 |
|------|----------|----------|----------|
| ELO vs 步数折线图 | 等宽分桶聚合 | `AVG(X) GROUP BY floor(X/10)*10` | 后端 SQL |
| ELO vs 步数散点图 | 随机采样 | `SELECT ... ORDER BY RANDOM() LIMIT 5000` | 后端 SQL |
| 热力密度图 | 二维分箱统计 | `COUNT(*) GROUP BY floor(ELO/50)*50, floor(Moves/10)*10` | 后端 SQL |
| 箱线图 | 均值±标准差+极值 | `Var(X) = E[X²] - (E[X])²` | 后端 SQL |
| 步数直方图 | 一维频率分布 | `COUNT(*) GROUP BY floor(Moves/10)*10` | 前端 JS |
| 开局胜率排行 | 条件计数+百分比 | `SUM(CASE WHEN result='1-0' THEN 1 ELSE 0 END) / COUNT(*)` | 后端 SQL |
| 开局分类饼图 | 分类频数统计 | `COUNT(*) GROUP BY SUBSTR(eco_code,1,1)` | 后端 SQL |
| 开局-ELO热力图 | 二维交叉统计 | `COUNT(*) GROUP BY category, floor(ELO/500)*500` | 后端 SQL |
| 胜率曲线 | 3点移动平均 | `Y[i] = (X[i-1] + X[i] + X[i+1]) / 3` | 前端 JS |

**核心结论**：所有分析方法均为**描述性统计**（Descriptive Statistics），不涉及推断性统计或机器学习。计算主要由后端 SQL 聚合完成（`GROUP BY` + `AVG/COUNT/SUM/MIN/MAX`），前端仅做简单平滑和可视化渲染。

---

## 问题 3：Stockfish 的集成方式、底层逻辑与常用功能

### 3.1 集成方式：本地部署，非 API 调用

**Stockfish 是本地部署的可执行程序，不是通过 API 调用网页大模型。**

**文件**: `backend/config.py` 第 16 行：

```python
STOCKFISH_PATH = os.environ.get('STOCKFISH_PATH',
    os.path.join(os.path.dirname(__file__), 'stockfish', 'stockfish', 'stockfish-windows-x86-64-avx2.exe'))
```

**集成原理**：通过 `python-chess` 库的 UCI（Universal Chess Interface）协议与 Stockfish 进程通信：

**文件**: `backend/app/services/stockfish_analyzer.py` 第 24-33 行：

```python
# 启动 Stockfish 子进程，通过标准输入/输出通信
self._engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
self._engine.configure({"Threads": threads, "Hash": hash_size})
```

`popen_uci` 的底层原理：
1. 使用 Python `subprocess` 启动 Stockfish 可执行文件作为子进程
2. 通过 stdin/stdout 管道发送 UCI 命令（如 `position fen ...`、`go depth 20`）
3. Stockfish 将分析结果通过 stdout 返回
4. `python-chess` 库封装了 UCI 协议的解析，提供 Pythonic API

### 3.2 Stockfish 的底层逻辑

**Stockfish 不是机器学习，也不是深度学习，而是基于传统搜索算法的国际象棋引擎。**

其核心技术：

| 技术 | 说明 |
|------|------|
| **Alpha-Beta 剪枝搜索** | 在 Minimax 搜索树上剪掉不可能更优的分支，大幅减少搜索量 |
| **迭代加深** | 从浅到深逐层搜索，利用浅层结果排序深层搜索，提高剪枝效率 |
| **置换表** | 哈希表缓存已搜索的局面评估，避免重复计算 |
| **评估函数** | 手工编写的启发式函数，考虑子力、兵结构、王安全、子力活跃度等 |
| **NNUE** | Efficiently Updatable Neural Network，Stockfish 12+ 引入的浅层神经网络评估，替代部分手工评估 |

**关键理解**：
- Stockfish 的核心是**搜索**（Search），不是学习（Learning）
- NNUE 是一个**小型前馈神经网络**（约 4 层），用于局面评估，而非端到端下棋
- 训练数据来自 Stockfish 自身的高深度搜索结果
- NNUE 的推理速度极快（微秒级），因为网络很小且针对 CPU 优化

### 3.3 Stockfish 在本项目中的功能

#### 功能一：棋谱分析（逐着评价）

**文件**: `backend/app/services/stockfish_analyzer.py` 第 36-100 行 `analyze_game` 方法

```
对每一步棋：
1. 获取走子前的 FEN 局面
2. 调用 Stockfish 分析该局面（depth=20, multipv=3）
3. 获取最佳着法列表和评估分数
4. 分析实际走子的质量（与最佳着法对比）
5. 计算胜率变化、标注着法评价（!!/!/?!/??/??）
```

**着法评价标准**（第 322-340 行）：

| 评价 | 符号 | 分差（兵值） | 含义 |
|------|------|-------------|------|
| 妙手 | `!!` | < 0.05 且为最佳着法 | 精准找到最佳着法 |
| 好着 | `!` | 0.05-0.20 | 接近最佳选择 |
| 有趣 | `!?` | 0.20-0.50 | 有创意但非最优 |
| 不精确 | `?!` | 0.50-1.00 | 小失误 |
| 失误 | `?` | 1.00-2.00 | 明显错误 |
| 严重失误 | `??` | > 2.00 | 致命错误 |

#### 功能二：AI 对弈

**文件**: `backend/app/services/ai_player.py` 第 47-110 行 `get_move` 方法

```
根据难度配置：
1. 调用 Stockfish 分析（depth 根据难度调整：5-22）
2. 获取前 5 个候选着法（multipv=5）
3. 根据随机率和失误率选择着法：
   - 低难度：更大概率选择非最佳着法
   - 高难度：几乎总是选择最佳着法
```

**难度配置**（第 13-17 行）：

| 难度 | 搜索深度 | 随机率 | 失误率 |
|------|---------|--------|--------|
| 入门 | 5 | 25% | 10% |
| 初级 | 8 | 15% | 5% |
| 中级 | 12 | 8% | 2% |
| 高级 | 18 | 3% | 0% |
| 专家 | 22 | 0% | 0% |

#### 功能三：提示系统

**文件**: `backend/app/services/ai_player.py` 第 112-148 行 `get_hint` 方法

返回当前局面的最佳着法、评估分数和胜率。

### 3.4 降级机制

当 Stockfish 不可用时，自动切换到 Mock 模式：

**文件**: `backend/app/services/stockfish_analyzer.py` 第 34-36 行：

```python
except Exception as e:
    self._engine = None
    self._is_mock = True  # 降级为模拟分析器
```

Mock 模式使用随机数生成模拟分析结果，保证系统在无 Stockfish 时仍可运行。

---

## 问题 4：Flask-JWT-Extended、Werkzeug、Puzzle、SQLAlchemy 聚合、ECharts 详解

### 4.1 Flask-JWT-Extended

**是什么**：Flask 的 JWT 认证扩展库，提供 Token 生成、验证、刷新等完整功能。

**功能**：
- `create_access_token(identity)` — 生成 JWT Token
- `@jwt_required()` — 装饰器，要求请求携带有效 Token
- `get_jwt_identity()` — 从 Token 中提取用户标识
- `@jwt_required(optional=True)` — Token 可选，有则验证，无则放行

**本项目使用**：

| 场景 | 文件 | 行号 |
|------|------|------|
| 初始化 JWT | `app/__init__.py` | 第 22 行 `jwt.init_app(app)` |
| 配置密钥和过期时间 | `config.py` | 第 13-14 行 |
| 登录生成 Token | `routes/auth.py` | 第 86 行 |
| 保护需认证的路由 | `routes/auth.py` | 第 100 行 `@jwt_required()` |
| 可选认证 | `routes/practice.py` | 第 248 行 `@jwt_required(optional=True)` |
| 提取用户身份 | `routes/auth.py` | 第 106 行 `get_jwt_identity()` |

### 4.2 Werkzeug 密码哈希

**是什么**：Werkzeug 是 Flask 的底层 WSGI 工具库，提供密码哈希功能。

**原理**：使用 PBKDF2-HMAC-SHA256 算法 + 随机盐值（salt），将明文密码转换为不可逆的哈希值。

**为什么不用明文存储密码**：即使数据库泄露，攻击者也无法从哈希值反推出原始密码。

**本项目使用**：

**文件**: `backend/app/models/user.py`

```python
# 第 2 行 — 导入
from werkzeug.security import generate_password_hash, check_password_hash

# 第 20 行 — 设置密码（注册/修改密码时调用）
def set_password(self, password):
    self.password_hash = generate_password_hash(password)

# 第 23 行 — 验证密码（登录时调用）
def check_password(self, password):
    return check_password_hash(self.password_hash, password)
```

**工作流程**：
1. `generate_password_hash("mypassword")` → `"pbkdf2:sha256:260000$salt$hash"`（含算法、迭代次数、盐值、哈希值）
2. `check_password_hash(stored_hash, "mypassword")` → `True/False`（用相同盐值重新计算哈希并比对）

### 4.3 Puzzle 模型

**是什么**：残局题目的数据模型，对应数据库 `puzzles` 表。

**文件**: `backend/app/models/practice.py`

**核心字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `fen` | String(100) | 残局局面的 FEN 字符串 |
| `name` | String(200) | 残局名称 |
| `category` | String(20) | 分类（残局/战术/开局/将杀） |
| `difficulty` | String(20) | 难度（beginner/easy/medium/hard） |
| `hint` | Text | 提示信息 |
| `is_preset` | Boolean | 是否为系统预设残局 |
| `practice_count` | Integer | 练习次数 |
| `solve_count` | Integer | 解决次数 |

**预设残局**：由 `init_db.py` 中的 `init_system_puzzles()` 初始化 10 个经典残局（如后兵残局、车兵残局等）。

### 4.4 SQLAlchemy 聚合

**是什么**：SQLAlchemy 的聚合查询功能，用于对数据库记录进行统计计算。

**常用聚合函数**：

| 函数 | SQL 等价 | 说明 |
|------|---------|------|
| `db.func.count()` | `COUNT()` | 计数 |
| `db.func.max()` | `MAX()` | 最大值 |
| `db.func.min()` | `MIN()` | 最小值 |
| `db.func.avg()` | `AVG()` | 平均值 |
| `db.func.sum()` | `SUM()` | 求和 |

**本项目使用**：

**文件**: `backend/app/models/game.py` 第 53 行 — 自动编号：
```python
max_num = db.session.query(db.func.max(Game.game_number)).scalar() or 0
```

**文件**: `backend/import_openings.py` — 开局统计聚合：
```python
# 按 eco_code 分组，计算每个开局的胜率和使用次数
from sqlalchemy import func
stats = db.session.query(
    Game.eco_code,
    func.count(Game.id).label('total'),
    func.sum(case((Game.result == '1-0', 1), else_=0)).label('white_wins'),
).group_by(Game.eco_code).all()
```

**文件**: `backend/app/routes/stats.py` — ELO 分桶聚合：
```python
# 按 ELO 区间分组，计算平均步数
bucket = db.session.query(
    func.avg(Game.white_elo).label('avg_elo'),
    func.avg(Game.total_moves).label('avg_moves'),
    func.count(Game.id).label('game_count'),
).group_by(bucket_expr).all()
```

### 4.5 ECharts

**是什么**：Apache ECharts，基于 JavaScript 的开源可视化图表库。

**本项目使用的图表类型**：

| 图表 | 组件/视图 | 用途 |
|------|----------|------|
| 折线图 | `WinRateChart.vue` | 胜率曲线 + 分数曲线（双 Y 轴） |
| 散点图 | `Stats.vue` | ELO vs 步数关联分析 |
| 热力图 | `Stats.vue` | ELO×步数密度分布 |
| 箱线图 | `Stats.vue` | 步数分布五数概括 |
| 直方图 | `Stats.vue` | 步数频率分布 |
| 饼图 | `Stats.vue` | 开局分类占比 |
| 柱状图 | `Stats.vue` | 开局胜率排行 |

**ECharts 在 Vue 中的使用方式**：

```vue
<!-- 文件: frontend/src/components/WinRateChart.vue 第 2-8 行 -->
<v-chart
  ref="chartRef"
  :option="chartOption"      <!-- 响应式绑定配置 -->
  :autoresize="true"          <!-- 自动适应容器大小 -->
  @click="onChartClick"       <!-- 点击事件 -->
/>
```

`chartOption` 是一个 `computed` 属性，当数据或主题变化时自动更新图表。

---

## 问题 5：棋谱库总览页面的棋盘缩略图如何显示？

### 答案：通过 FEN 实时绘制，不是存储的图片

**核心机制**：每个棋谱在数据库中存储了 `final_fen` 字段（终局 FEN），前端通过 Canvas API 实时解析 FEN 并绘制棋盘缩略图。

### 5.1 数据来源

**文件**: `backend/app/models/game.py` 第 23 行：

```python
final_fen = db.Column(db.String(100), default='')  # 存储终局 FEN
```

`final_fen` 在棋谱导入时由 `import_pgn.py` 自动计算：解析 PGN 到最后一着，提取棋盘 FEN 字符串。

### 5.2 前端实时绘制

**文件**: `frontend/src/views/GameList.vue` 第 108-113 行 — Canvas 元素：

```html
<canvas
  :ref="el => setCanvasRef(game.id, el)"
  class="gl-card-canvas"
  width="160"
  height="160"
  :data-game-id="game.id"
/>
```

**文件**: `frontend/src/views/GameList.vue` 第 332-371 行 — `drawMiniBoard` 函数：

```javascript
function drawMiniBoard(game) {
  const canvas = canvasRefs[game.id]
  const ctx = canvas.getContext('2d')
  const size = 160, sq = size / 8

  // 1. 绘制棋盘格子（浅色 #f0d9b5 + 深色 #b58863）
  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      ctx.fillStyle = (r + c) % 2 === 0 ? lightColor : darkColor
      ctx.fillRect(c * sq, r * sq, sq, sq)
    }
  }

  // 2. 解析 FEN，绘制棋子（Unicode 字符）
  const fen = game.final_fen || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR'
  const pieceMap = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟',
  }
  const rows = fen.split(' ')[0].split('/')
  // ... 逐行逐字符解析 FEN，在 Canvas 上绘制棋子
}
```

### 5.3 性能优化：IntersectionObserver 懒加载

**文件**: `frontend/src/views/GameList.vue` 第 312-330 行：

```javascript
// 只绘制可见区域内的棋盘（懒加载）
canvasObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const canvas = entry.target
      const gameId = canvas.dataset.gameId
      if (gameId && !drawnCanvases.has(gameId)) {
        drawnCanvases.add(gameId)
        const game = games.value.find(g => g.id === parseInt(gameId))
        if (game) drawMiniBoard(game)
        canvasObserver.unobserve(canvas)  // 绘制后取消观察
      }
    }
  })
}, { rootMargin: '200px' })  // 提前 200px 开始加载
```

**完整流程**：

```
1. 后端存储 final_fen（如 "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R"）
2. API 返回棋谱列表（含 final_fen 字段）
3. 前端为每个棋谱创建 160×160 的 Canvas 元素
4. IntersectionObserver 检测 Canvas 进入视口
5. 调用 drawMiniBoard() 解析 FEN → 绘制棋盘格子 + Unicode 棋子
6. 无需请求任何图片，纯前端实时渲染
```

---

## 问题 6：Vite Dev 与 Flask Blueprint

### 6.1 Vite Dev

**是什么**：Vite（法语"快"）是下一代前端构建工具，`vite dev` 是其开发服务器命令。

**原理**：

| 特性 | 原理 |
|------|------|
| **极速冷启动** | 不打包，直接利用浏览器原生 ES Module（`<script type="module">`），按需编译 |
| **即时热更新** | 精确 HMR——修改某文件只更新该模块，不刷新整页 |
| **依赖预构建** | 首次启动用 esbuild 将 node_modules 依赖预构建为 ESM（比 Webpack 快 10-100 倍） |

**传统工具 vs Vite**：

```
Webpack:  启动 → 打包所有模块 → 启动服务器 → 浏览器加载（慢，随项目增大变慢）
Vite:     启动 → 直接启动服务器 → 浏览器按需请求模块 → 实时编译（快，不受项目大小影响）
```

**本项目配置**：

**文件**: `frontend/vite.config.js`

```javascript
// 第 31-37 行 — 开发服务器代理
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:5000',  // 转发到 Flask 后端
      changeOrigin: true,
    },
  },
}
```

开发时前端运行在 `localhost:3000`，API 请求 `/api/*` 自动代理到 Flask 的 `localhost:5000`。

### 6.2 Flask

**是什么**：Flask 是 Python 的轻量级 Web 框架，遵循 WSGI 规范。

**主要功能**：
- **路由**：URL 到处理函数的映射
- **请求/响应处理**：解析请求数据，构建响应
- **模板引擎**：Jinja2（本项目未使用，前后端分离）
- **扩展生态**：丰富的第三方扩展

**常见关联结构**：

```
Flask 应用
├── SQLAlchemy  — ORM 数据库操作
├── Flask-Migrate — 数据库迁移（Alembic 封装）
├── Flask-CORS  — 跨域资源共享
├── Flask-JWT-Extended — JWT 认证
├── Flask-Limiter — API 限流
├── Flask-Admin — 后台管理界面
└── Flasgger — Swagger API 文档
```

### 6.3 Blueprint

**是什么**：Blueprint 是 Flask 的模块化组织机制，将相关路由、模板、静态文件组织为独立模块。

**原理**：Blueprint 本身不实现功能，它是一个**路由注册的容器**。应用创建时，将 Blueprint 中定义的路由"注册"到应用上。

**类比理解**：Blueprint 就像插座排插——排插本身不供电，但提供了标准接口。把排插插到墙上（注册到 App），排插上的所有插口（路由）就都有电了。

**本项目 Blueprint 结构**：

**文件**: `backend/app/routes/__init__.py`

```python
def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix='/api/auth')       # 认证
    app.register_blueprint(games_bp, url_prefix='/api/games')     # 棋谱
    app.register_blueprint(players_bp, url_prefix='/api/players') # 棋手
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')# 分析
    app.register_blueprint(openings_bp, url_prefix='/api/openings')# 开局
    app.register_blueprint(practice_bp, url_prefix='/api/practice')# 练习
    app.register_blueprint(stats_bp, url_prefix='/api/stats')     # 统计
    app.register_blueprint(collections_bp, url_prefix='/api/collections')# 收藏
```

**Blueprint 的好处**：
1. **代码组织**：每个功能模块独立文件，避免单文件过大
2. **URL 前缀**：统一添加 `/api/auth`、`/api/games` 等前缀
3. **独立开发**：不同开发者可以独立开发不同 Blueprint
4. **可复用**：同一个 Blueprint 可以注册到多个应用

---

## 问题 7：设计模式与前端技术详解

### 7.1 后端设计模式

#### 观察者模式

**是什么**：定义对象间一对多的依赖关系，当一个对象状态改变时，所有依赖者自动收到通知。

**本项目体现**：Flask 的信号机制和回调函数。

**文件**: `backend/app/services/stockfish_analyzer.py` 第 88-93 行：

```python
# 分析回调 — 每分析完一步就通知调用者
if callback:
    progress = current_ply / total_plies
    try:
        callback(progress, move_data)  # 通知观察者
    except Exception as e:
        logger.warning("Callback error: %s", e)
```

调用者（如异步分析任务）注册回调函数，分析器每完成一步就调用回调报告进度，这就是观察者模式的应用。

#### Repository 模式

**是什么**：在业务逻辑和数据访问之间增加一层抽象，将数据库操作封装在 Repository 中。

**本项目体现**：Model 的 `to_dict()` 方法和 `get_moves_list()` 方法封装了数据访问逻辑。

**文件**: `backend/app/models/game.py` 第 57-92 行：

```python
def get_moves_list(self):
    """从 PGN 内容解析着法列表 — 封装了 PGN 解析的复杂性"""
    if not self.pgn_content:
        return []
    try:
        import chess.pgn
        game_obj = chess.pgn.read_game(StringIO(self.pgn_content))
        # ... 解析逻辑
        return moves
    except Exception:
        return []
```

外部代码只需调用 `game.get_moves_list()`，无需关心 PGN 解析细节。

#### 应用工厂模式

**是什么**：通过工厂函数创建应用实例，而非直接创建全局应用对象。

**文件**: `backend/app/__init__.py` 第 14-46 行：

```python
def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    # ... 初始化扩展、注册 Blueprint
    return app
```

**好处**：
1. **多配置**：可创建不同配置的应用实例（开发/测试/生产）
2. **避免循环导入**：扩展对象（db, jwt 等）在模块级创建，但不绑定应用
3. **测试友好**：每个测试可创建独立应用实例

#### Swagger 与 Flasgger

**Swagger**：REST API 文档规范（OpenAPI Specification），定义了 API 文档的标准格式。

**Flasgger**：Flask 的 Swagger 集成库，自动从代码注释生成 API 文档。

**文件**: `backend/app/swagger_config.py` 第 1-21 行：

```python
swagger_template = {
    "info": {
        "title": "Chess Data Management API",
        "version": "1.0.0"
    },
    "securityDefinitions": {
        "Bearer": {"type": "apiKey", "name": "Authorization", "in": "header"}
    }
}

def setup_swagger(app):
    swagger = Swagger(app, template=swagger_template)
```

访问 `http://localhost:5000/apidocs` 即可查看交互式 API 文档。

### 7.2 前端技术

#### Pinia

**是什么**：Vue 3 的官方状态管理库，替代 Vuex。

**原理**：基于 Vue 3 的响应式系统（`ref`/`reactive`），提供跨组件的共享状态。

**文件**: `frontend/src/store/userStore.js`

```javascript
export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')  // 响应式状态
  const isLoggedIn = computed(() => !!token.value)          // 计算属性

  async function login(credentials) {                       // 异步操作
    const res = await loginApi(credentials)
    token.value = res.data.token
    localStorage.setItem('token', res.data.token)
  }

  return { token, isLoggedIn, login }  // 暴露给组件使用
})
```

**组件中使用**：
```javascript
const userStore = useUserStore()
console.log(userStore.isLoggedIn)  // 自动响应式
await userStore.login({ username, password })
```

#### Composition API

**是什么**：Vue 3 的编程范式，用函数组织逻辑，替代 Vue 2 的 Options API（data/methods/computed 分散定义）。

**对比**：

```javascript
// Options API（Vue 2 风格）— 逻辑按类型分散
export default {
  data() { return { count: 0 } },
  computed: { double() { return this.count * 2 } },
  methods: { increment() { this.count++ } }
}

// Composition API（Vue 3 风格）— 逻辑按功能聚合
const count = ref(0)
const double = computed(() => count.value * 2)
function increment() { count.value++ }
```

**本项目大量使用 Composition API**，所有 `<script setup>` 组件都是 Composition API 风格。

#### Props 驱动

**是什么**：父组件通过 Props 向子组件传递数据，子组件通过 Events 向父组件通信，形成单向数据流。

**文件**: `frontend/src/components/ChessBoard.vue` Props 定义：

```javascript
const props = defineProps({
  fen: { type: String, default: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1' },
  lastMove: { type: Object, default: null },
  orientation: { type: String, default: 'white' },
  interactive: { type: Boolean, default: false },
  // ...
})

const emit = defineEmits(['move-made', 'promotion'])
```

**数据流**：`父组件(fen数据) → Props → ChessBoard(渲染) → Events → 父组件(处理走子)`

#### 计算属性（computed）

**是什么**：基于响应式依赖自动缓存的派生数据。只有依赖变化时才重新计算。

**文件**: `frontend/src/store/practiceStore.js` 第 48-54 行：

```javascript
// 当前轮次 — 从 FEN 字符串中推导，无需额外存储
const currentTurn = computed(() => {
  if (!currentFen.value) return 'white'
  return currentFen.value.includes(' w ') ? 'white' : 'black'
})
```

**文件**: `frontend/src/components/WinRateChart.vue` 第 34-36 行：

```javascript
// 玩家视角翻转 — 黑方玩家看到的是 100-白方胜率
const isPlayerBlack = computed(() => props.playerColor === 'b')
```

**"玩家视角翻转"的含义**：胜率数据始终以白方视角存储。当用户执黑时，`winRateData` 计算属性将 `100 - white_win_rate` 作为显示值，让用户看到的是"我的胜率"而非"对手的胜率"。

#### 代码分割与懒加载

**是什么**：将应用代码按路由拆分为多个小块（chunk），按需加载，减少首屏加载体积。

**文件**: `frontend/src/router/index.js` 第 6 行：

```javascript
component: () => import('@/views/GameList.vue')  // 动态 import
```

**原理**：
1. `import()` 是 ES2020 动态导入语法，返回 Promise
2. Vite/Rollup 构建时遇到 `import()`，自动将目标模块拆分为独立 JS 文件
3. 用户访问该路由时，浏览器才下载对应的 JS 文件

**文件**: `frontend/vite.config.js` 第 42-45 行 — 手动分块配置：

```javascript
manualChunks: {
  'element-plus': ['element-plus'],  // UI 库单独分块
  echarts: ['echarts', 'vue-echarts'],  // 图表库单独分块
}
```

**效果**：首屏只加载核心代码（~200KB），ECharts 等大库按需加载（~800KB），提升首屏速度。

---

## 问题 8："创建内存对话"是什么？

### 答案：是服务器内存中的 Python 字典，存储 PracticeSession 对象

**"内存对话"不是 HTTP 接口，而是后端 Python 进程内存中的一个字典数据结构。**

**文件**: `backend/app/routes/practice.py` 第 18 行：

```python
sessions = {}  # 全局字典，存储所有活跃的对局会话
```

### 8.1 工作原理

```
1. 用户点击"开始对弈" → POST /practice/start
2. 后端创建 PracticeSession 对象（含棋盘状态、AI 引擎、走法历史）
3. 生成唯一 session_id（UUID）
4. 存入 sessions 字典：sessions[session_id] = { 'session': session_obj, ... }
5. 返回 session_id 给前端
6. 后续走子/悔棋/提示请求都携带 session_id
7. 后端从 sessions[session_id] 取出会话对象进行操作
```

**文件**: `backend/app/routes/practice.py` 第 278-291 行：

```python
session_id = str(uuid.uuid4())
sessions[session_id] = {
    'session': session_obj,     # PracticeSession 实例
    'user_id': None,            # 关联用户
    'puzzle_id': db_puzzle_id,  # 关联残局
    'started_at': datetime.utcnow(),
}
```

**文件**: `backend/app/routes/practice.py` 第 313-319 行 — 走子时查找会话：

```python
entry = sessions.get(session_id)
if not entry:
    return jsonify({'error': 'session_expired'}), 410  # 会话不存在/已过期

session_obj = entry['session']
result = session_obj.user_move(move_san)
```

### 8.2 为什么叫"内存"对话？

因为 `sessions` 字典存储在 **Python 进程的内存**中，不是数据库中。这意味着：
- **优点**：读写极快（纳秒级），适合实时对弈
- **缺点**：服务器重启后会话丢失；不支持多进程/多服务器部署

### 8.3 会话的生命周期

```
创建 → 走子/悔棋/提示 → 对局结束 → 保存到数据库 → 从内存删除
```

**文件**: `backend/app/routes/practice.py` 第 325-327 行：

```python
if result.get('is_game_over'):
    _save_session_to_db(session_obj, ...)  # 保存到数据库
    session_obj.close()                     # 关闭 AI 引擎
    sessions.pop(session_id, None)          # 从内存移除
```

---

## 问题 9：PGN 示例文件

PGN 文件已单独生成，包含 10 局最新经典对局，见项目根目录 `sample_games.pgn` 和 `sample_games_2.pgn`。

---

## 问题 10：数据库为何设计这么多表？如何符合范式理论？表间关联是什么？

### 10.1 数据库表总览

本项目共 **10 张表**，按业务域分组：

| 业务域 | 表名 | 模型文件 | 核心职责 |
|--------|------|----------|----------|
| **用户域** | `users` | `backend/app/models/user.py` | 系统登录用户 |
| **棋手域** | `players` | `backend/app/models/player.py` | 国际象棋棋手（职业棋手数据） |
| **棋谱域** | `games` | `backend/app/models/game.py` | 棋谱对局记录（核心表） |
| **赛事域** | `tournaments` | `backend/app/models/tournament.py` | 锦标赛/赛事 |
| **分析域** | `analyses` | `backend/app/models/analysis.py` | Stockfish 引擎分析结果 |
| **开局域** | `openings` | `backend/app/models/opening.py` | ECO 开局库 |
| **用户关系域** | `collections` | `backend/app/models/collection.py` | 用户收藏 |
| **用户关系域** | `browsing_history` | `backend/app/models/browsing_history.py` | 浏览历史 |
| **练习域** | `puzzles` | `backend/app/models/practice.py` | 残局面/题目 |
| **练习域** | `practice_games` | `backend/app/models/practice.py` | AI 练习对局记录 |

---

### 10.2 范式理论回顾

| 范式 | 核心要求 | 通俗解释 |
|------|----------|----------|
| **1NF（第一范式）** | 字段不可再分，列原子性 | 一个字段只存一个值，不能塞列表 |
| **2NF（第二范式）** | 非主键列完全依赖主键（消除部分依赖） | 联合主键时不能只依赖其中一列 |
| **3NF（第三范式）** | 非主键列不能传递依赖于主键（消除传递依赖） | 不能"依赖的依赖" |
| **BCNF（巴斯-科德范式）** | 任何决定因素都必须是候选键 | 3NF 的加强版 |
| **反范式** | 适当冗余以提升查询性能 | 违反 3NF 但换性能 |

---

### 10.3 逐表范式分析

#### 10.3.1 `users` — 用户表

**文件**: `backend/app/models/user.py`

```
id(PK) | username | password_hash | email | is_admin | created_at
```

- **1NF**：所有字段原子（`username`、`email` 都是单一字符串）
- **2NF**：单列主键 `id`，不存在部分依赖
- **3NF**：每个字段都直接依赖 `id`，没有传递依赖
- ✅ **符合 3NF**

**典型反范式考虑**：是否需要冗余 `collection_count` 字段以避免每次 `COUNT(*)`？
本项目选择**不冗余**，因收藏量小，JOIN 成本低。

---

#### 10.3.2 `players` — 棋手表

**文件**: `backend/app/models/player.py`

```
id(PK) | name | title | country | elo_rating | birth_date | created_at
```

- **1NF/2NF/3NF**：所有字段都直接描述"一个棋手"
- ✅ **符合 3NF**
- **特殊点**：`title`（GM/IM/FM）、`country` 都做成了独立字段而非字典，便于索引和分组

---

#### 10.3.3 `tournaments` — 赛事表

**文件**: `backend/app/models/tournament.py`

```
id(PK) | name | start_date | end_date | location | category
```

- **1NF/2NF/3NF**：每字段都直接描述"一场赛事"
- ✅ **符合 3NF**

**设计理由**：把赛事独立成表，是因为**一场赛事下有多局棋**（一对多），如果用 `game.tournament_name` 字段直接存名字，会出现**数据冗余**（同一赛事名重复存 N 次），且更新赛事名时要改 N 处。这就是 1NF → 3NF 解决的典型问题。

---

#### 10.3.4 `games` — 棋谱表（核心表）

**文件**: `backend/app/models/game.py` 第 6-27 行

```
id(PK) | game_number | white_player_id(FK→players) | black_player_id(FK→players)
       | tournament_id(FK→tournaments) | date | result | pgn_content
       | eco_code | opening_name | total_moves | final_fen
       | white_elo | black_elo | termination | time_control | created_at
```

- **1NF**：所有字段原子
- **2NF**：单主键 `id`，无部分依赖
- **3NF 关键设计**：
  - ❌ 错误做法：把"白方棋手姓名"直接存在 `games` 表 → 数据冗余（同一棋手姓名出现 N 次）
  - ✅ 正确做法：只存 `white_player_id`，姓名通过 JOIN `players` 表获得
  - 这就是**消除传递依赖**（`name` 传递依赖 `id`）
- ✅ **符合 3NF**

**部分字段的解释**：
- `white_elo`/`black_elo` 冗余于 `players.elo_rating`：但这是**业务合理性**——棋手 ELO 会随时间变化，每局棋要记录**对局发生时的 ELO** 而非当前 ELO。这是有意的**快照反范式**。

---

#### 10.3.5 `analyses` — 分析结果表

**文件**: `backend/app/models/analysis.py`

```
id(PK) | game_id(FK→games, UNIQUE) | analysis_data(JSON) 
       | opening_eco | key_moves(JSON) | win_rate_curve(JSON) | created_at
```

- **1NF**：JSON 字段内部虽然嵌套，但**整体作为一个值**存储（SQLite/PG 的 JSON 列），符合 1NF
- **2NF/3NF**：单主键，每个字段描述"一局棋的分析"
- ✅ **符合 3NF**

**JSON 字段的设计**：`analysis_data`、`key_moves`、`win_rate_curve` 都用 JSON 存储。理由：
- 这些字段结构会随分析功能扩展而变化（增加新指标）
- 不适合为每个指标建列（列数膨胀）
- 不适合拆成关联表（查询时要 N+1 次 JOIN）

**反范式权衡**：JSON 不能直接 `WHERE` 高效查询。本项目用 `analysis_data` JSON 字段存完整数据 + `opening_eco` 等关键字段独立成列做索引，是**混合范式**设计。

---

#### 10.3.6 `openings` — 开局库表

**文件**: `backend/app/models/opening.py`

```
id(PK) | eco_code(UNIQUE) | name | variation | moves(JSON) 
       | category | description | popularity 
       | white_win_rate | black_win_rate | draw_rate
```

- **1NF/2NF/3NF**：每个字段描述"一种开局"
- ✅ **符合 3NF**

**为何独立成表**：
- ECO 编码是国际标准（500+ 种），需要独立维护
- `moves` 字段存具体走法序列（JSON 数组）
- `popularity` / `white_win_rate` 等为统计字段，会随数据库棋谱数变化而更新（批量计算后回写）

---

#### 10.3.7 `collections` — 收藏表

**文件**: `backend/app/models/collection.py`

```
id(PK) | user_id(FK→users) | game_id(FK→games) | note | created_at
UNIQUE(user_id, game_id)
```

- **1NF/2NF/3NF**：单主键
- ✅ **符合 3NF**

**为何独立成表（而非用 JSON 数组存 `user.favorite_game_ids`）**：
- 收藏数量可能很多，JSON 数组无法高效查询、统计
- 收藏需要带附加属性（`note` 笔记、`created_at` 收藏时间）
- 收藏需要唯一性约束（`UNIQUE(user_id, game_id)`）
- 收藏关系天然就是**多对多**（一个用户可收藏多局，一局可被多用户收藏）

---

#### 10.3.8 `browsing_history` — 浏览历史表

**文件**: `backend/app/models/browsing_history.py`

```
id(PK) | user_id(FK→users) | game_id(FK→games) | viewed_at
UNIQUE(user_id, game_id)
```

- 与 `collections` 结构同构（同为多对多 + 时间戳）
- ✅ **符合 3NF**
- 与 `collections` 的差异：业务含义不同（"看过"vs"收藏"），不能合并

---

#### 10.3.9 `puzzles` — 残局面表

**文件**: `backend/app/models/practice.py` 第 6-37 行

```
id(PK) | puzzle_number(UNIQUE) | name | category | difficulty 
       | description | hint | fen | source_game_id(FK→games)
       | from_move | created_by(FK→users) | is_preset 
       | practice_count | solve_count | created_at
```

- **1NF/2NF/3NF**：标准第三范式
- ✅ **符合 3NF**

**关键设计**：
- `source_game_id` 引用 `games`：题目来源于真实对局某一局面（可追溯）
- `created_by` 引用 `users`：记录创建者（管理员/普通用户）
- `is_preset`：区分系统预设题目 vs 用户自建
- `practice_count` / `solve_count`：**反范式**——为避免每次统计 `COUNT(*)`，直接冗余计数（高读低写场景的性能优化）

---

#### 10.3.10 `practice_games` — 练习对局表

**文件**: `backend/app/models/practice.py` 第 67-80 行

```
id(PK) | user_id(FK→users) | mode | puzzle_id(FK→puzzles) 
       | source_game_id | from_move | start_fen | user_color | ...
```

- ✅ **符合 3NF**
- 与 `puzzles` 的关系：练习对局可以"基于某个残局题目"（`puzzle_id`）或"从某局棋的某步开始"（`source_game_id + from_move`）

---

### 10.4 表间关联关系（ER 总览）

```
                  ┌─────────────┐
                  │   users     │
                  │  (用户)     │
                  └──────┬──────┘
                         │ 1
       ┌─────────────────┼─────────────────┐
       │ N               │ N               │ N
       ▼                 ▼                 ▼
┌─────────────┐   ┌──────────────┐   ┌──────────────────┐
│ collections │   │  browsing_   │   │  practice_games  │
│  (收藏)     │   │  history     │   │  (练习对局)      │
└──────┬──────┘   └──────┬───────┘   └────────┬─────────┘
       │ N                │ N                  │ N
       │ 1                │ 1                  │ 0..1
       ▼                 ▼                    ▼
   ┌───────────────────────────────────────┐
   │              games                    │◄──────┐
   │            (棋谱,核心)                │       │
   │                                       │       │
   │  white_player_id  ──┐                 │       │
   │  black_player_id  ──┤                 │       │
   │  tournament_id    ──┤                 │       │
   │  eco_code         ──┤ (索引)          │       │
   └──────┬──────────────┴─────────────────┘       │
          │ 1                                       │
          │ 1                                       │
          ▼ N                                       │
   ┌─────────────┐         ┌──────────────┐         │
   │  analyses   │         │   puzzles    │─────────┘
   │  (分析结果) │         │  (残局题目)  │  source_game_id
   └─────────────┘         └──────┬───────┘
                                 │ N
                                 │ 1
                                 ▼
                            ┌─────────┐
                            │  users  │ (created_by)
                            └─────────┘

   ┌──────────────┐         ┌──────────────────┐
   │  players     │◄────────│  games           │ (white/black_player_id)
   │  (棋手)      │  N   1  │                  │
   └──────────────┘         └──────────────────┘

   ┌──────────────┐         ┌──────────────────┐
   │ tournaments  │◄────────│  games           │ (tournament_id)
   │  (赛事)      │  N   1  │                  │
   └──────────────┘         └──────────────────┘

   ┌──────────────┐
   │  openings    │  ← 逻辑引用（eco_code 字符串，未建 FK）
   │  (开局库)    │
   └──────────────┘
```

---

### 10.5 主要外键关联（代码定位）

| 外键 | 位置 | 引用的表 |
|------|------|----------|
| `Game.white_player_id` | `game.py` 第 9 行 | `players.id` |
| `Game.black_player_id` | `game.py` 第 10 行 | `players.id` |
| `Game.tournament_id` | `game.py` 第 11 行 | `tournaments.id` |
| `Analysis.game_id` (UNIQUE) | `analysis.py` 第 7 行 | `games.id`（一对一） |
| `Collection.user_id` | `collection.py` 第 7 行 | `users.id` |
| `Collection.game_id` | `collection.py` 第 8 行 | `games.id` |
| `BrowsingHistory.user_id` | `browsing_history.py` 第 7 行 | `users.id` |
| `BrowsingHistory.game_id` | `browsing_history.py` 第 8 行 | `games.id` |
| `Puzzle.source_game_id` | `practice.py` 第 12 行 | `games.id` |
| `Puzzle.created_by` | `practice.py` 第 13 行 | `users.id` |
| `PracticeGame.user_id` | `practice.py` 第 69 行 | `users.id` |
| `PracticeGame.puzzle_id` | `practice.py` 第 71 行 | `puzzles.id` |

---

### 10.6 关联类型详解

| 关系 | 表 A | 表 B | 类型 | 业务含义 |
|------|------|------|------|----------|
| `users ↔ collections` | users | collections | **一对多** | 一个用户可收藏多局 |
| `games ↔ collections` | games | collections | **一对多** | 一局可被多用户收藏 |
| `users ↔ games`（多对多） | users | games | **多对多**（通过 collections） | 收藏关系 |
| `users ↔ browsing_history` | users | browsing_history | **一对多** | 一个用户可浏览多局 |
| `games ↔ browsing_history` | games | browsing_history | **一对多** | 一局可被多用户浏览 |
| `games ↔ analyses` | games | analyses | **一对一**（`UNIQUE`） | 一局对应一份分析 |
| `players ↔ games`（白方） | players | games | **一对多** | 一棋手可下多局白棋 |
| `players ↔ games`（黑方） | players | games | **一对多** | 一棋手可下多局黑棋 |
| `tournaments ↔ games` | tournaments | games | **一对多** | 一赛事含多局 |
| `puzzles ↔ games` | puzzles | games | **多对一**（`source_game_id`） | 多题可源自同一局 |
| `users ↔ puzzles` | users | puzzles | **一对多**（`created_by`） | 一用户可创建多题 |
| `puzzles ↔ practice_games` | puzzles | practice_games | **一对多** | 一题可被练习多次 |

---

### 10.7 设计哲学总结

| 原则 | 在本项目的体现 |
|------|----------------|
| **实体分离** | 棋手（`players`）、赛事（`tournaments`）、棋谱（`games`）三者独立，避免字段冗余 |
| **避免数组字段** | 多对多关系（用户-棋谱）用中间表（`collections`）而非 JSON 数组 |
| **JSON 字段谨慎使用** | 仅在结构不稳定/嵌套深的场景（`analyses.analysis_data`、`puzzles.moves`）使用 |
| **业务反范式** | `white_elo` 快照、`practice_count` 计数冗余等场景接受反范式以换性能 |
| **唯一约束防重复** | `Collection(user_id, game_id)` `UNIQUE` — 防止重复收藏 |
| **懒加载策略** | `lazy='select'` / `lazy='dynamic'` 区分：详情用 `select`（一次性加载），列表用 `dynamic`（返回查询对象，避免 N+1） |

**核心结论**：本项目数据库设计**整体符合 3NF**（10 张表无传递依赖、无部分依赖），但在**性能敏感字段**（`white_elo` 快照、`solve_count` 计数）做了**有意识的反范式**。多对多关系一律通过中间表实现，绝不滥用 JSON 数组字段，这是教科书级的范式-性能平衡实践。

---

## 问题 11：数据筛选、排序、聚合用的是什么语句？关联了哪些表？

### 11.1 ORM 技术栈

本项目使用 **SQLAlchemy 2.x ORM**（非原生 SQL），通过 Python 方法链式调用最终翻译为 SQL 语句。

**导入位置**：几乎每个路由文件顶部都有
```python
from sqlalchemy import func, case, cast, Integer  # 聚合函数
from sqlalchemy.orm import joinedload             # 预加载关联
```

---

### 11.2 五大查询操作类型

#### 11.2.1 单表过滤（WHERE）— `filter()`

**典型场景**：筛选棋手、棋谱、开局列表的搜索/筛选条件

**文件**：`backend/app/routes/games.py` 第 102-153 行

```python
# 棋手姓名模糊匹配（白方或黑方）
player = request.args.get('player', '').strip()
if player:
    wp = db.session.query(Player.id).filter(Player.name.ilike(f'%{player}%')).subquery()
    query = query.filter(db.or_(
        Game.white_player_id.in_(wp),       # IN 子查询
        Game.black_player_id.in_(wp),
    ))

# 日期范围
if date_from:
    query = query.filter(Game.date >= date_from)  # >= 比较
if date_to:
    query = query.filter(Game.date <= date_to)

# ECO 前缀
if eco:
    query = query.filter(Game.eco_code.ilike(f'{eco}%'))  # LIKE 'A%'

# 精确匹配
if result_filter:
    query = query.filter(Game.result == result_filter)    # = 比较
```

**生成的 SQL 类型**：
```sql
SELECT * FROM games
WHERE white_player_id IN (SELECT id FROM players WHERE name LIKE '%xxx%')
   OR black_player_id IN (...)
   AND date >= '2024-01-01'
   AND date <= '2024-12-31'
   AND eco_code LIKE 'B%'
   AND result = '1-0'
```

**关联的表**：`games`（主表） + 子查询引用 `players.id`

---

#### 11.2.2 多表关联（JOIN）— `joinedload()`

**典型场景**：列表查询时一次性加载关联数据，避免 N+1 查询

**文件**：`backend/app/routes/games.py` 第 100-102 行

```python
from sqlalchemy.orm import joinedload

query = Game.query.options(
    joinedload(Game.white_player),   # LEFT OUTER JOIN players white ON ...
    joinedload(Game.black_player),   # LEFT OUTER JOIN players black ON ...
)
```

**原理**：
- `joinedload` 在主查询时**通过 JOIN 一次**加载关联对象
- 避免访问每条 `game.white_player.name` 时再发一次 SQL
- 默认使用 `LEFT OUTER JOIN`（即使无关联数据也保留主表记录）

**生成的 SQL 类型**：
```sql
SELECT games.*, white_1.*, black_1.*
FROM games
LEFT OUTER JOIN players AS white_1 ON games.white_player_id = white_1.id
LEFT OUTER JOIN players AS black_1 ON games.black_player_id = black_1.id
WHERE ...
```

**关联的表**：`games` JOIN `players`（两次，分别对应白方/黑方）

---

#### 11.2.3 排序（ORDER BY）— `order_by()`

**典型场景**：按 ELO/日期/步数等字段排序

**文件**：`backend/app/routes/games.py` 第 147-154 行

```python
sort_map = {
    'created_at': Game.created_at,
    'date': Game.date,
    'white_elo': Game.white_elo,
    'black_elo': Game.black_elo,
    'total_moves': Game.total_moves,
    'eco_code': Game.eco_code,
}
sort_col = sort_map.get(sort, Game.created_at)

if order == 'asc':
    query = query.order_by(sort_col.asc())     # ASC 升序
else:
    query = query.order_by(sort_col.desc())    # DESC 降序
```

**关键设计**：用 `sort_map` 字典做白名单校验，**防止 SQL 注入**（用户输入的 sort 字段不会直接拼到 SQL 中）。

**其他典型排序**：
- `players.py` 第 122-130 行：按 `elo_rating` / `name` / `created_at` 排序
- `openings.py` 第 90-99 行：按 `eco_code` / `popularity` / 各种 `win_rate` 排序
- `practice.py` 第 626-630 行：按 `created_at` / `difficulty` / `total_moves` / `hints_used` 排序

---

#### 11.2.4 聚合统计（GROUP BY）— `group_by() + func.*`

**典型场景**：统计分析 API（ELO 分布、开局胜率、棋手战绩等）

**文件 1**：`backend/app/routes/games.py` 第 737-754 行 — ELO 分桶

```python
from sqlalchemy import func

avg_elo_expr = func.round((Game.white_elo + Game.black_elo) / 2.0 / 10) * 10

query = db.session.query(
    avg_elo_expr.label('avg_elo_bucket'),
    func.avg(Game.total_moves).label('avg_moves'),     # AVG() 函数
    func.count(Game.id).label('game_count'),           # COUNT() 函数
).filter(*base_filter).group_by(
    avg_elo_expr,
).order_by(avg_elo_expr)
```

**生成的 SQL 类型**：
```sql
SELECT
  ROUND((white_elo + black_elo) / 2.0 / 10) * 10 AS avg_elo_bucket,
  AVG(total_moves) AS avg_moves,
  COUNT(id) AS game_count
FROM games
WHERE white_elo IS NOT NULL AND ...
GROUP BY ROUND((white_elo + black_elo) / 2.0 / 10) * 10
ORDER BY avg_elo_bucket
```

**文件 2**：`backend/app/routes/games.py` 第 840-852 行 — 开局胜率（条件聚合）

```python
from sqlalchemy import case

openings_query = db.session.query(
    Game.eco_code,
    func.count(Game.id).label('total'),
    func.sum(case((Game.result == '1-0', 1), else_=0)).label('white_wins'),
    func.sum(case((Game.result == '0-1', 1), else_=0)).label('black_wins'),
    func.sum(case((Game.result == '1/2-1/2', 1), else_=0)).label('draws'),
    func.avg(Game.total_moves).label('avg_moves'),
    func.avg((Game.white_elo + Game.black_elo) / 2.0).label('avg_elo'),
).filter(*base_filter).group_by(
    Game.eco_code,
).order_by(func.count(Game.id).desc()).limit(50)
```

**生成的 SQL 类型**：
```sql
SELECT
  eco_code,
  COUNT(id) AS total,
  SUM(CASE WHEN result = '1-0' THEN 1 ELSE 0 END) AS white_wins,
  SUM(CASE WHEN result = '0-1' THEN 1 ELSE 0 END) AS black_wins,
  SUM(CASE WHEN result = '1/2-1/2' THEN 1 ELSE 0 END) AS draws,
  AVG(total_moves) AS avg_moves,
  AVG((white_elo + black_elo) / 2.0) AS avg_elo
FROM games
WHERE result IN ('1-0', '0-1', '1/2-1/2')
GROUP BY eco_code
ORDER BY COUNT(id) DESC
LIMIT 50
```

**关联的表**：**仅 `games` 单表**（聚合不涉及 JOIN，因为统计字段都在 games 表内）

---

#### 11.2.5 关联子查询（Correlated Subquery / IN）

**典型场景**：跨表筛选（按棋手姓名找棋谱）

**文件**：`backend/app/routes/games.py` 第 108-110 行

```python
wp = db.session.query(Player.id).filter(Player.name.ilike(f'%{player}%')).subquery()
query = query.filter(db.or_(
    Game.white_player_id.in_(wp),
    Game.black_player_id.in_(wp),
))
```

**原理**：
1. 先用子查询查出所有匹配姓名的棋手 ID
2. 用 `IN` 谓词筛选该 ID 出现在 `white_player_id` 或 `black_player_id` 的棋局

**生成的 SQL 类型**：
```sql
SELECT * FROM games
WHERE white_player_id IN (SELECT id FROM players WHERE name LIKE '%xxx%')
   OR black_player_id IN (SELECT id FROM players WHERE name LIKE '%xxx%')
```

**关联的表**：`games` 主表 + 子查询引用 `players`（`IN` 子查询，非 JOIN）

---

### 11.3 实际路由查询清单

按"操作类型"分类整理本项目所有路由的查询模式：

#### A. 筛选过滤类（`filter` / `filter_by`）

| 路由 | 文件:行号 | 筛选字段 | 关联表 |
|------|----------|----------|--------|
| `GET /games` | `games.py` L102-138 | player/date/eco/result/search | `games`+`players` (子查询) |
| `GET /games/filters` | `games.py` L33-34 | DISTINCT eco_code/result | `games` |
| `GET /players` | `players.py` L91-104 | search/country/title/min_elo/max_elo | `players` |
| `GET /players/filters` | `players.py` L25-26 | DISTINCT title/country | `players` |
| `GET /openings` | `openings.py` L70-84 | category/search/eco | `openings` |
| `GET /puzzles` | `practice.py` L99-105 | category/difficulty/source_game_id | `puzzles` |
| `GET /practice/games` | `practice.py` L589-618 | difficulty/mode/result | `practice_games` |
| `GET /practice/search_games` | `practice.py` L250-256 | search | `games`+`players` (子查询) |
| `GET /collections` | `collections.py` L44 | user_id | `collections` |
| `GET /analysis/<id>` | `analysis.py` L585 | game_id | `analyses` |
| `GET /browsing` | `browsing.py` (browsing模块) | user_id | `browsing_history` |

#### B. 关联加载类（`joinedload`）

| 路由 | 文件:行号 | 关联表 |
|------|----------|--------|
| `GET /games` | `games.py` L100-102 | `games` JOIN `players` (2次) |
| `GET /practice/search_games` | `practice.py` L250 | `games` JOIN `players` (2次) |
| `GET /browsing` | `browsing.py` | `browsing_history` JOIN `games` (用 `relationship`) |

#### C. 聚合统计类（`group_by` + `func.*`）

| 路由 | 文件:行号 | 聚合维度 | 关联表 |
|------|----------|----------|--------|
| `GET /games/stats/elo-vs-moves` | `games.py` L737-822 | ELO桶 × 步数桶 | `games` |
| `GET /games/stats/openings` | `games.py` L835-920 | ECO × ELO桶 | `games` |
| `GET /players/<id>/stats` | `player.py` L33-44 (model方法) | result 分类 | `games` (白/黑) |

#### D. 精确查找类（`filter_by` / `get` / `first`）

| 路由 | 文件:行号 | 查询方式 |
|------|----------|----------|
| `GET /games/<id>` | `games.py` (查询代码) | `Game.query.get(id)` |
| `GET /analysis/<id>` | `analysis.py` L585 | `Analysis.query.filter_by(game_id=...)` |
| `GET /collections/...` | `collections.py` L108, L150, L185, L221 | `filter_by(user_id, game_id)` 组合 |

---

### 11.4 关键 SQL 操作对照表

| SQLAlchemy 方法 | 对应 SQL 关键字 | 示例 |
|----------------|----------------|------|
| `Model.query.filter_by(x=y)` | `WHERE x = y` | `Collection.query.filter_by(user_id=u)` |
| `Model.query.filter(x == y)` | `WHERE x = y` | `Game.result == '1-0'` |
| `Model.query.filter(x >= y)` | `WHERE x >= y` | `Game.date >= '2024-01-01'` |
| `Model.query.filter(x.ilike('%y%'))` | `WHERE x LIKE '%y%'` | `Player.name.ilike('%Carlsen%')` |
| `Model.query.filter(x.in_(subquery))` | `WHERE x IN (...)` | `Game.white_player_id.in_(wp)` |
| `Model.query.filter(db.or_(a, b))` | `WHERE a OR b` | `db.or_(Game.result=='1-0', ...)` |
| `Model.query.filter(db.and_(a, b))` | `WHERE a AND b` | `db.and_(result=='1-0', color=='w')` |
| `query.options(joinedload(x))` | `LEFT OUTER JOIN` | `joinedload(Game.white_player)` |
| `query.order_by(x.asc())` | `ORDER BY x ASC` | `Game.date.asc()` |
| `query.order_by(x.desc())` | `ORDER BY x DESC` | `Game.elo_rating.desc()` |
| `query.group_by(x)` | `GROUP BY x` | `group_by(Game.eco_code)` |
| `query.limit(n)` | `LIMIT n` | `query.limit(5000)` |
| `query.distinct()` | `DISTINCT` | `db.session.query(Game.eco_code).distinct()` |
| `query.paginate(page, per_page)` | `LIMIT/OFFSET` | 自动拼装分页 |
| `func.count(x)` | `COUNT(x)` | 计数 |
| `func.avg(x)` | `AVG(x)` | 平均值 |
| `func.sum(x)` | `SUM(x)` | 求和 |
| `func.min(x)` / `func.max(x)` | `MIN(x)` / `MAX(x)` | 极值 |
| `func.round(x)` | `ROUND(x)` | 四舍五入 |
| `func.random()` | `RANDOM()` | 随机排序 |
| `func.substr(x, 1, 1)` | `SUBSTR(x, 1, 1)` | 字符串截取 |
| `func.abs(x)` | `ABS(x)` | 绝对值 |
| `case((cond, val), else_=0)` | `CASE WHEN cond THEN val ELSE 0 END` | 条件分支 |

---

### 11.5 设计特点

| 特点 | 体现位置 | 优点 |
|------|----------|------|
| **白名单防 SQL 注入** | `sort_map` 字典 + `get(sort, default)` | 用户输入的字段名不会直接拼到 SQL |
| **避免 N+1 查询** | `joinedload` 预加载关联对象 | 列表查询性能提升 10-100 倍 |
| **子查询替代 JOIN** | `IN (subquery)` 而非 `JOIN` | 跨表筛选时代码更直观 |
| **聚合下推到数据库** | `func.avg/count/sum` 在 SQL 层完成 | 避免 Python 加载全量数据 |
| **跨数据库可移植** | 使用 SQLAlchemy 抽象 | 同一份代码可跑在 SQLite/PG/MySQL |

**核心结论**：本项目数据库操作**全部走 SQLAlchemy ORM**，未使用原生 SQL 字符串拼接。筛选（`filter/filter_by`）、排序（`order_by`）、聚合（`group_by + func.*`）、关联（`joinedload`）四大类操作覆盖所有查询场景，**关联的表**主要是 `games`（核心表）、`players`（棋手）、`collections/browsing_history`（用户关系表）、`puzzles/practice_games`（练习域表）。所有 SQL 关键字都通过 ORM 方法映射，避免了 SQL 注入风险并保证了数据库可移植性。

---

## 附录：关键代码文件索引

| 功能 | 文件 | 关键行号 |
|------|------|----------|
| JWT Token 生成 | `backend/app/routes/auth.py` | L86 |
| JWT 配置 | `backend/config.py` | L13-14 |
| Token 前端存储 | `frontend/src/store/userStore.js` | L19-20 |
| Token 请求拦截 | `frontend/src/api/request.js` | L13-16 |
| Token 过期处理 | `frontend/src/api/request.js` | L62-78 |
| 胜率曲线图 | `frontend/src/components/WinRateChart.vue` | L38-48, L246 |
| 数据分析页 | `frontend/src/views/Stats.vue` | L131-155 |
| Stockfish 初始化 | `backend/app/services/stockfish_analyzer.py` | L24-36 |
| 棋谱分析逻辑 | `backend/app/services/stockfish_analyzer.py` | L36-100 |
| AI 对弈逻辑 | `backend/app/services/ai_player.py` | L47-110 |
| 难度配置 | `backend/app/services/ai_player.py` | L13-17 |
| 密码哈希 | `backend/app/models/user.py` | L2, L20-23 |
| 棋盘缩略图绘制 | `frontend/src/views/GameList.vue` | L332-371 |
| Canvas 懒加载 | `frontend/src/views/GameList.vue` | L312-330 |
| Vite 代理配置 | `frontend/vite.config.js` | L31-37 |
| Blueprint 注册 | `backend/app/routes/__init__.py` | 全文 |
| 应用工厂 | `backend/app/__init__.py` | L14-46 |
| Swagger 配置 | `backend/app/swagger_config.py` | L1-21 |
| 内存会话 | `backend/app/routes/practice.py` | L18, L278-291 |
| 路由懒加载 | `frontend/src/router/index.js` | L6 等 |
| Pinia Store | `frontend/src/store/userStore.js` | 全文 |
| Practice Store | `frontend/src/store/practiceStore.js` | L48-54 |

---

# 答辩后补充问答（针对老师提出的 3 个问题）

## Q12. 危险操作（删除/修改）是否直接落库？如何做权限控制？

**答**：答辩前未做审核，确实存在风险。答辩后我们新增了完整的"修改申请-审核"链路：

1. **新增 `ModificationRequest` 表**（[`backend/app/models/admin_models.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/models/admin_models.py)）：保存申请的目标、动作、原始数据快照、审核状态
2. **前端危险操作改为提交申请**（[`frontend/src/views/PuzzleLibrary.vue`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/frontend/src/views/PuzzleLibrary.vue)）：`DELETE` 按钮 → `POST /api/mod-requests`
3. **管理员控制台审核**（[`frontend/src/views/AdminDashboard.vue`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/frontend/src/views/AdminDashboard.vue)）：通过/拒绝 + 写入 `comment`
4. **审核通过后端自动落库**（[`backend/app/traffic.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/traffic.py) `_apply_mod_request`）：执行真正的 DELETE/UPDATE
5. **路由级守卫**（[`frontend/src/router/index.js`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/frontend/src/router/index.js)）：`/admin` 仅 `is_admin=true` 可访问

## Q13. 12 张表是否过度设计？哪些可以静态化为 JSON？

**答**：12 张表都是必要的。具体分类：

| 表 | 不可静态化原因 |
|----|----------------|
| `users`, `games`, `analyses`, `puzzles`, `practice_games`, `collections`, `browsing_history` | 用户行为数据，必须写入数据库以便查询/统计 |
| `api_access_logs`, `modification_requests` | 监控与审计数据，每秒都可能产生 |
| `tournaments`, `players` | 与 `games` 多对多关联，关系型建模更自然 |
| `openings` | 数据量大但更新频率低；保留为表 + 唯一索引 `(eco_code)` 查询更快 |

> **不建议改静态 JSON**：JSON 无法做 `JOIN`，会破坏范式；数据规模在百万级以内 SQL 都可接受。

## Q14. puzzles.created_by 为空、登录其他账号结果一致 → 个性化未实现？

**答**：**确实是 Bug，已修复。**

**根因**（[`backend/app/routes/auth.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/auth.py) L137）：
```python
create_access_token(identity=str(user.id))  # JWT 存 user.id
```
但 [`backend/app/routes/practice.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/routes/practice.py) L239 错误地用 `username` 查找：
```python
user = User.query.filter_by(username=identity).first()  # ← 永远查不到
```
导致 `user=None` → `created_by=None`。

**修复**：
```python
# 兼容 username（旧） 与 user_id（str/int，新）
if identity is not None:
    user = User.query.filter_by(username=identity).first()
    if not user:
        try: user = User.query.get(int(identity))
        except (TypeError, ValueError): user = None
```

**测试验证**（`backend/tests/test_e2e_fixes.py`）：
- alice 创建残局 id=11, created_by=1 ✅
- bob 创建残局 id=12, created_by=2 ✅
- alice 列表 only_mine: `['Alice P1']`，bob 列表 only_mine: `['Bob P1']` ✅
- 游客访问仅见 10 条系统预设 ✅

**前端配套**（[`frontend/src/views/PuzzleLibrary.vue`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/frontend/src/views/PuzzleLibrary.vue)）：新增"我创建的"筛选 + "创建残局"按钮。

## Q15. 端到端测试如何跑？

**答**：
```powershell
cd backend
python tests/test_e2e_fixes.py
```
4 个阶段共 14 个断言全过，输出示例：
```
=== 阶段 1：用户注册 ===         1. register alice & bob: OK
=== 阶段 2：个性化残局 ===       2.1-2.6 全 OK
=== 阶段 3：修改申请审核 ===     3.1-3.4 全 OK
=== 阶段 4：流量监测 ===         4.1-4.2 全 OK
=== 全部测试通过！===
```

## Q16. 流量监测如何识别不同 token / 用户？

**答**：[`backend/app/traffic.py`](file:///d:/Users/pc/AppData/Local/Programs/trae_projects/ces/backend/app/traffic.py) 在 `after_request` 钩子中：

```python
verify_jwt_in_request(optional=True)
identity = get_jwt_identity()
if identity:
    user = User.query.filter_by(username=identity).first() or User.query.get(int(identity))
    user_id = user.id
    username = user.username

# 同时保存 token MD5 前 16 位（仅指纹，不存明文）
token_fp = hashlib.md5(auth[7:].encode()).hexdigest()[:16]
```

每条 `ApiAccessLog` 包含 `user_id / username / token_fingerprint / method / path / status_code / duration_ms / ip_address / accessed_at`。管理后台可按 `user_id` 聚合看到"谁在什么时候调用了哪些 API"。

