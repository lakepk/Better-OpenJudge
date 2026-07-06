# OpenJudge 架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用  户  端                                     │
│                                                                          │
│  ┌──────────────────────┐            ┌──────────────────────────────┐   │
│  │   浏览器 (Web 版)     │            │   桌面应用 (desktop/)         │   │
│  │   HTML + CSS + JS    │            │                              │   │
│  │   Jinja2 模板渲染     │            │  PySide6 + QWebEngine        │   │
│  │   Ace Editor (CDN)   │            │  渲染同一套 HTML/CSS          │   │
│  │   highlight.js (CDN) │            │  零浏览器 chrome              │   │
│  └──────────┬───────────┘            │  硬编码服务器地址              │   │
│             │                        └──────────────┬───────────────┘   │
│             │  HTTP (HTML 页面)                      │  HTTP (REST API) │
│             │  Session Cookie                       │  Bearer Token   │
│             │                                       │                  │
└─────────────┼───────────────────────────────────────┼──────────────────┘
              │                                       │
              ▼                                       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         nginx (反向代理)                                 │
│                    https://tongpku.me/openjudge                          │
│                                                                          │
│              /          →  gunicorn :8080  (Web 页面)                    │
│              /api/v1/*  →  gunicorn :8080  (REST API)                   │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    gunicorn (3 workers) :8080                            │
│                       web/run.py  ─  入口                               │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    web/bridge.py  ─  桥接层                       │   │
│  │                                                                   │   │
│  │  • install() 猴子补丁: database.create_submission → 自动触发评测   │   │
│  │  • ThreadPoolExecutor (max_workers=4) 控制评测并发                 │   │
│  │  • _run_judge(): 取数据 → 写临时文件 → 调 JudgeController → 写回DB │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────┐      ┌──────────────────────────────────┐     │
│  │   data/app.py        │      │   judge/  ─  评测引擎             │     │
│  │   Flask 应用          │      │                                  │     │
│  │                      │      │  config.py     JudgeStatus 枚举   │     │
│  │  • 页面路由 (Jinja2)  │      │  core/                           │     │
│  │  • /api/v1/ 蓝图     │      │    ├─ compiler.py   编译         │     │
│  │  • CSRF 保护         │      │    ├─ runner.py     运行+内存测量 │     │
│  │  • XSS 过滤          │      │    ├─ checker.py    答案比对      │     │
│  │  • Markdown 渲染      │      │    └─ controller.py 编排流水线    │     │
│  │  • 北京时间转换       │      │                                  │     │
│  └──────────┬───────────┘      └──────────────────────────────────┘     │
│             │                                                            │
└─────────────┼────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      SQLite (judge.db · WAL 模式)                        │
│                                                                          │
│   ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌───────────────┐      │
│   │  users   │  │ problems │  │ submissions  │  │ test_cases    │      │
│   └──────────┘  └──────────┘  └──────────────┘  └───────────────┘      │
│   ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌───────────────┐      │
│   │ contests │  │  tags    │  │ api_tokens   │  │ announcements │      │
│   └──────────┘  └──────────┘  └──────────────┘  └───────────────┘      │
│   ┌──────────────────┐  ┌──────────────────────┐                        │
│   │ contest_problems │  │contest_registrations │                        │
│   └──────────────────┘  └──────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────────┘
```

## 评测流水线

```
用户提交代码
     │
     ▼
create_submission() ─── DB: status="Pending"
     │
     ▼  (bridge monkey-patch 自动触发)
judge_async(submission_id)
     │
     ▼  (ThreadPoolExecutor 入队)
_run_judge()
     │
     ├─ 1. 从 DB 读取题目配置、测试数据
     ├─ 2. 将测试数据写入临时文件 (/tmp/tc_{id}_*/)
     ├─ 3. JudgeController.start(test_cases)
     │      │
     │      ├─ compiler.compile()      ─ 编译源码 → 可执行文件
     │      ├─ runner.run_all_cases()   ─ 逐个测试点运行
     │      │     │
     │      │     └─ subprocess.Popen 启动子进程
     │      │        · preexec_fn: RLIMIT_AS 限制内存
     │      │        · daemon 线程: 超时 kill
     │      │        · /proc/[pid]/status VmHWM: 5ms 轮询峰值内存
     │      │
     │      └─ checker.check()          ─ 比对输出 / SPJ
     │
     ├─ 4. 结果写入 DB: status, score, time, memory
     ├─ 5. update_problem_stats()       ─ 更新通过率
     └─ 6. 清理临时文件
```

## 桌面端通信

```
OpenJudge.exe
     │
     ├─ 打开时: QWebEngineView.load("https://tongpku.me/openjudge")
     │          渲染服务器返回的 HTML/CSS/JS ─ 界面完全一致
     │
     ├─ 登录时: POST /api/v1/auth/login  → 拿到 Bearer Token
     │          Token 存在 QWebEngine 的 Cookie 存储中
     │
     ├─ 提交代码: POST /api/v1/submit → 服务器异步评测
     │
     └─ 轮询结果: GET /api/v1/submission/<id>  (每 2s，直到终态)
```

## 关键文件索引

| 文件 | 职责 |
|---|---|
| `web/run.py` | 生产入口，gunicorn 加载 |
| `web/bridge.py` | Flask ↔ Judge 桥接，猴子补丁 + 线程池 |
| `data/app.py` | Flask 路由、API 蓝图、模板过滤器 |
| `data/database.py` | 所有 SQL 操作，表结构定义 |
| `data/templates/` | Jinja2 模板 (Web 页面 + 桌面端渲染) |
| `judge/core/controller.py` | 评测流水线编排 |
| `judge/core/compiler.py` | GCC / Python 编译 |
| `judge/core/runner.py` | 子进程执行 + VmHWM 内存测量 |
| `judge/core/checker.py` | 输出比对 / SPJ |
| `desktop/main.py` | 桌面端入口，硬编码服务器地址 |
| `desktop/app.py` | QWebEngine 窗口，无浏览器 chrome |
| `desktop/OpenJudge.spec` | PyInstaller 打包配置 |
