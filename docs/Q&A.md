# 答辩问答（Q&A）

> 收录答辩现场和日常复盘中可能遇到的高频问题，按主题分类。

---

## 一、架构与选型

### Q1：为什么选 Flask 而不是 Django / Spring Boot？

**A**：
1. **轻量灵活**：Flask 没有"强制目录结构"，可以完全按业务需求组织 4 层架构
2. **生态够用**：Flask 周边库（Flask-JWT-Extended、Flask-Admin、Flasgger、Flask-Migrate）覆盖毕设全部需求
3. **学习成本低**：核心概念 30 分钟能讲完，重点放在业务上
4. **性能满足**：单进程 Flask 就能应对毕设演示，gunicorn 4 worker 已绰绰有余

Django 自带 admin 反而限制定制化，Spring Boot 重量级杀鸡用牛刀。

### Q2：为什么选 Vue 3 + Vite 而非 React？

**A**：
1. **Composition API** 风格统一，逻辑复用比 mixin 更优雅
2. **`<script setup>` 语法糖**减少样板代码
3. **Vite 冷启动 < 1 秒**，开发体验好
4. **Element Plus** 组件丰富，适合中后台 + 业务前台
5. **Pinia** 替代 Vuex，API 更接近 React Hooks，类型友好

### Q3：数据库为什么用 SQLite，毕设生产不用 PostgreSQL？

**A**：
1. **零运维**：单文件部署，docker volume 挂载即可
2. **SQLAlchemy 抽象**：切换 PG 只需改 `DATABASE_URL` 环境变量
3. **演示友好**：答辩现场不用搭数据库服务
4. **小数据量优势**：日活 < 1000 时，SQLite 性能反而比 PG 强

部署到 Render 时我们已对接 Neon PostgreSQL，零代码修改。

---

## 二、核心功能

### Q4：Stockfish 引擎是怎么集成的？

**A**：
```
Python 进程 (StockfishAnalyzer)
  ↓ async with chess.engine.SimpleEngine.popen_uci()
Stockfish 子进程
  ↓ UCI 协议（stdin/stdout）
  ↓ 发送：uci / position fen X / go depth 20
  ↓ 接收：info depth 1 score cp 25 ... bestmove e2e4
```

实现细节：
- 在 `app/services/stockfish_analyzer.py`
- 解析 `info` 行抽取 depth/score/pv
- `asyncio.run()` 同步包装
- 路径解析 4 级回退（环境变量 → Windows 路径 → Linux 路径）
- **失败自动降级 Mock 模式**（防 Docker 内无引擎崩溃）

### Q5：异步分析任务如何持久化？gunicorn 多 worker 不会丢吗？

**A**：
- 任务状态存数据库（`analysis_tasks` 表）
- Worker A 处理请求时，先 `INSERT` 任务到表（pending）
- 状态机：`pending → running → completed/failed/cancelled`
- 前端轮询 `GET /api/analysis/tasks/:id/status` 查询
- 即使 Worker A 重启，B 接手时从 DB 读 status
- **保证不丢任务，不重复扣费**

### Q6：AI 对弈 5 档难度怎么实现的？

**A**：
| 档位 | Stockfish Skill Level | Search Time | 走法随机性 |
|------|----------------------|-------------|-----------|
| 入门 | 1-3 | 100ms | 30% 走次优解 |
| 初级 | 4-7 | 300ms | 10% |
| 中级 | 8-12 | 500ms | 0% |
| 高级 | 13-18 | 1s | 0% |
| 专家 | 20 | 3s | 0% |

走法随机性在 `ai_player.py` 中用 `random.random() < 0.3` 选取第二选择实现。

### Q7：复盘分析中"妙手/好着/失误"如何判定？

**A**：基于胜率变化（Win Rate Delta）：

| 标签 | 触发条件 |
|------|----------|
| 妙手 (!!) | 胜率变化 > 20% |
| 好着 (!) | 胜率变化 5%~20% |
| 中性 | -5%~5% |
| 失误 (?) | -20%~-5% |
| 漏着 (??) | < -20% |

从 Stockfish 拿到每个着法的 `score_cp` → 转换为 `win_pct` → 计算相邻着法的差值 → 标注。

---

## 三、数据与安全

### Q8：13 张表是否过度设计？

**A**：详见 [OPTIMIZATION_REPORT.md 第 2 节](OPTIMIZATION_REPORT.md#2-问题-2-13-张表分表是否过度)。

核心论点：**分表是业务域划分，不是性能优化**。每张表都有独立查询路径，不可合并。

### Q9：危险操作怎么审核？

**A**：详见 [OPTIMIZATION_REPORT.md 第 1 节](OPTIMIZATION_REPORT.md#1-问题-1危险操作无审核--缺后端管理页面)。

引入 `modification_requests` 表 + 审核 API。普通用户提交 `pending` 申请，管理员审批后才执行业务。

### Q10：密码怎么存储？

**A**：
- 使用 `werkzeug.security.generate_password_hash`（PBKDF2-SHA256）
- 自动加盐，单向哈希不可逆
- 数据库只存哈希，原密码不落盘
- JWT 中只放 `user_id`，不放 `username`（减小攻击面）

### Q11：JWT 怎么防止被劫持？

**A**：
- 24h 过期（`JWT_ACCESS_TOKEN_EXPIRES`）
- 签名密钥从环境变量 `JWT_SECRET_KEY` 读取
- 前端 `localStorage` 存储，HTTP-only 选项可后续开启
- 关键 API 二次校验：用户改密码会要求原密码
- API 流量日志记录 `token_fingerprint`（前 16 位摘要），便于异常追踪

### Q12：CORS 怎么配置？

**A**：
- `Flask-CORS` 初始化时从 `CORS_ORIGINS` 环境变量读取白名单
- 生产推荐：`CORS_ORIGINS=https://your-domain.vercel.app`
- 开发环境可用 `*` 全部放行
- Vercel 部署使用 `routes` 配置反向代理 `/api/*`，可绕过 CORS

---

## 四、部署与运维

### Q13：项目怎么部署的？花多少钱？

**A**：详见 [DEPLOYMENT.md](DEPLOYMENT.md)。

| 方案 | 费用 | 适用场景 |
|------|------|----------|
| Render + Vercel + Neon | $0 | **推荐毕设演示**，三件套免费 |
| Hugging Face Spaces | $0 + 持久化 $5/月 | **国内访问**，无信用卡 |
| Oracle Cloud ARM | $0（永久） | **重度使用**，永久免费 |
| 雨云/腾讯云 | ¥10-30/月 | **国内访问**，付费稳定 |

**毕设答辩推荐 Render + Vercel**：三件套都是白嫖，演示无门槛。

### Q14：为什么数据会被清空？free tier 不是有 persistent storage 吗？

**A**：
- Hugging Face 默认是 **临时文件系统**，重启容器数据丢失
- 开启 Persistent Storage（$5/月）才能持久化
- Render 也有类似问题，free 实例 15 分钟无访问会休眠
- **应对方案**：
  1. 免费层：定期备份（`flask backup-db`）到对象存储
  2. 付费层：开启 Persistent Storage
  3. 使用 PostgreSQL（数据不存容器文件）

### Q15：Stockfish 在 Docker 里跑得动吗？CPU 密集会不会拖垮服务？

**A**：
- Render free 实例 0.1 CPU，深度 20 跑分析需要 30-60 秒，建议用异步任务
- HF Spaces 16GB 内存 + 2 CPU，满血版 Stockfish 跑得很快
- 参数 `ANALYSIS_THREADS=1, ANALYSIS_HASH=256` 控制资源占用
- **多用户并发**：async 队列 + gunicorn 4 worker，最多 4 个分析并行

### Q16：怎么监控 API 流量？

**A**：
- `api_access_logs` 表自动记录所有 API 调用
- 管理 API `GET /api/admin/traffic` 返回：
  - 总请求数、平均延迟、错误率
  - 按用户、按端点、按时间分组
  - Token 指纹（便于追溯）
- 前端管理页面：可视化大屏

---

## 五、答辩技巧

### Q17：被问到不熟悉的部分怎么办？

**A**：
- 诚实说"这块我目前用得不多，我了解的是..."
- 但要说一个相关的、你知道的东西
- 不要硬编技术细节，老师一追问就破

### Q18：项目最难的部分是什么？

**A**：**Stockfish 路径解析**。
- 在 Windows / WSL / Docker / HF 各环境路径不同
- 用了 4 级回退策略才稳定
- 失败时降级 Mock 模式（防止启动崩溃）

### Q19：能讲一下项目最大的亮点吗？

**A**：
1. **完整业务闭环**：上传 → 分析 → 训练 → 复盘 → 数据可视化
2. **多端点部署支持**：一套代码支持 5 种部署方案
3. **可观测性**：API 流量 + 修改审核 + 错误日志
4. **AI 集成深度**：Stockfish 不仅用来分析，还驱动 AI 对弈和复盘

### Q20：如果继续做下去，最想加什么功能？

**A**：
1. **WebSocket 实时对弈**（现在用轮询）
2. **多用户实时协作**（一起看棋谱）
3. **PWA 移动端**（离线模式 + 推送通知）
4. **大模型接入**：用 GPT 分析每个着法的"自然语言讲解"
5. **P2P 对战**：WebRTC 直连，0 服务器成本
