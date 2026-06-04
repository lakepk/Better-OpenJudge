# Web 分工清单 — 你需要做的事情

---

## ✅ 已由 `data/` 队友完成

| # | 事项 | 关键文件 | 说明 |
|---|------|----------|------|
| D1 | Flask Web 服务器 | `data/app.py` | 30+ 路由：注册/登录、题目列表/详情、代码提交、个人中心、管理员面板 |
| D2 | 权限系统 | `data/app.py` | `@login_required`（需登录）、`@admin_required`（需管理员）两个装饰器 |
| D3 | 提交入口 | `data/app.py:171-210` | `POST /problem/<id>/submit` 接收代码 → 调用 `create_submission()` → 跳转到提交详情页 |
| D4 | 评测状态展示 | `data/templates/submission_detail.html` | 前端已能展示 `Pending/AC/WA/TLE/...` 等所有状态徽章 |
| D5 | 数据库全部建表 | `data/database.py:11-122` | 7 张表：users、problems、test_cases、submissions、announcements、tags、problem_tags |
| D6 | 评测结果写入函数 | `data/database.py:367-375` | `update_submission_result()` — 接收 status/score/time/memory/compiler_output/judge_detail |
| D7 | 题目统计更新函数 | `data/database.py:402-420` | `update_problem_stats()` — 自动统计总提交数和 AC 数 |
| D8 | 前端全部模板 | `data/templates/*.html` | 12 个 Jinja2 页面，含完整 CSS 样式和响应式布局 |
| D9 | Session 管理 | `data/app.py:6` | Flask session，`user_id`/`username`/`role`/`nickname` 四个字段 |

---

## ✅ 已由 `judge/` 队友完成

| # | 事项 | 关键文件 | 说明 |
|---|------|----------|------|
| J1 | 评测状态枚举 | `judge/judge/config.py:9-16` | `JudgeStatus` 类：AC / WA / TLE / MLE / RE / CE / SE |
| J2 | 编译器 | `judge/judge/core/compiler.py` | `Compiler.compile(lang, src_path, output_dir)` → 支持 cpp（g++）和 python |
| J3 | 运行器 | `judge/judge/core/runner.py` | `Runner.run_single_case(input_file, output_file, time_limit, memory_limit)` — 沙箱执行，超时自动 kill |
| J4 | 比对器 | `judge/judge/core/checker.py` | `Checker.check(user_out, ans_out)` — 行级严格比对（忽略行末空白） |
| J5 | 评测总控 | `judge/judge/core/controller.py` | `JudgeController(task_data).start(test_cases)` → 返回完整 JSON 结果 |
| J6 | 调用示例 | `judge/judge/main.py` | 展示了 task_data 格式和 test_cases 格式的 mock 数据 |

---

## 🔴  TODO：你需要做的事情（`web/`）

### 第 1 步：环境准备

| # | 待办事项 | 你的笔记/方案 |
|---|----------|--------------|
| T1 | 写 `requirements.txt`（列出所有 Python 依赖：flask, gunicorn, werkzeug，judge 的依赖还有哪些？） | |
| T2 | 确认 judge 模块能被 Python import（`judge/judge/` 有两层嵌套，`sys.path` 怎么处理？） | |
| T3 | 确认服务器上已安装 `g++`（judge 编译 C++ 需要），`python3`（运行 Python 代码需要） | |

---

### 第 2 步：桥接核心 — `web/bridge.py`

**目标：** 用户提交代码后，启动一个后台线程去做评测，用户立即看到"Pending"状态，之后刷新页面就能看到结果。

| # | 待办事项 | 需要解决的问题（填空） |
|---|----------|----------------------|
| T4 | **异步入口函数** `judge_async(submission_id)` | 用 `threading.Thread` 还是 `concurrent.futures`？线程需要 daemon 吗？ |
| T5 | **从 DB 获取评测所需数据** | 需要调用 `database.py` 里的哪些函数？分别拿到什么字段？ |
| T6 | **测试数据：DB → 临时文件** | judge 只接受文件路径 `{"in": "1.in", "out": "1.out"}`，但测试数据存在 SQLite 的 `test_cases` 表里（TEXT 字段）。你需要怎么转换？临时文件放哪里？评测完要不要删？ |
| T7 | **组装 task_data** | 对照 `judge/main.py` 里的格式，你需要把哪些 DB 字段映射到 task_data 的哪些 key？字段名和单位是否一致？（注意：DB 里 time_limit 单位是 ms，但 judge config 注释写的是秒） |
| T8 | **调用评测器** | `JudgeController(task_data).start(test_cases)` 返回的 JSON 结构是什么样的？对照 `controller.py` 的 return 语句写出字段名 |
| T9 | **结果写回 DB** | 用 `update_submission_result()` 把评测结果写回。需要把 `JudgeController` 返回值里的哪些字段映射到 `update_submission_result()` 的哪些参数？ |
| T10 | **更新题目统计** | 调用 `update_problem_stats(problem_id)` 更新通过率 |
| T11 | **异常处理** | 如果评测过程崩了（Python 异常），submission 的状态应该变成什么？要给用户看到什么信息？ |

---

### 第 3 步：打通 Flask — 修改 `data/app.py`

| # | 待办事项 | 填空 |
|---|----------|------|
| T12 | 在 `submit_code()` 函数里，`create_submission()` 之后、`redirect` 之前，调用 `judge_async(submission_id)` | 需要 `import` 什么？路径怎么处理？ |
| T13 | 原来的 TODO 注释要不要删掉？ | |

---

### 第 4 步：生产启动 — `web/run.py`

| # | 待办事项 | 填空 |
|---|----------|------|
| T14 | 创建一个能被 gunicorn 导入的 `app` 对象 | 直接 `from data.app import app` 就行，还是需要额外配置？`secret_key` 要不要改？`debug=True` 在生产环境要关掉吗？ |

---

### 第 5 步：Docker 化

| # | 待办事项 | 填空 |
|---|----------|------|
| T15 | **Dockerfile**：基于什么镜像？`python:3.11-slim`？需要额外 `apt install g++` 吗？工作目录、COPY 哪些文件夹、`pip install -r requirements.txt`、EXPOSE 哪个端口、CMD 是什么？ | |
| T16 | **docker-compose.yml**：有哪些 service？只需要一个 `web` 服务还是需要把 judge 拆成独立服务？ports 映射？（建议 `"8080:8080"` 然后前面套 nginx）数据库文件 `judge.db` 放 volume 里持久化吗？ | |

---

### 第 6 步：部署到服务器

| # | 待办事项 | 你的操作记录 |
|---|----------|-------------|
| T17 | 服务器上安装 Docker + Docker Compose | |
| T18 | 把项目代码推到服务器（git clone / scp / rsync） | |
| T19 | 在项目根目录执行 `docker-compose up -d` | |
| T20 | 验证：创建管理员账号（怎么在 SQLite 里手动把 role 改成 admin？），创建题目 + 测试数据，提交代码，看评测结果 | |

---

## 📊 数据流总览（对照检查）

```
POST /problem/<id>/submit
        │
        ▼
[data/app.py] submit_code()
        │
        ├─ create_submission()         ← D3（已做）
        │       │
        │       ▼
        │   INSERT INTO submissions    ← 状态 = 'Pending'
        │       │
        │       ▼
        ├─ judge_async(submission_id)  ← T4（你做）
        │       │
        │       ▼   (后台线程)
        │   [web/bridge.py]
        │       │
        │       ├─ get_submission_detail()    ← T5
        │       ├─ get_problem_by_id()        ← T5
        │       ├─ get_test_cases()           ← T5
        │       │       │
        │       │       ▼
        │       │   写入临时文件 .in / .out    ← T6
        │       │       │
        │       │       ▼
        │       │   JudgeController(task_data).start(test_cases)
        │       │       │                     ← J5（已有）
        │       │       ├─ Compiler.compile() ← J2
        │       │       ├─ Runner.run()       ← J3
        │       │       └─ Checker.check()    ← J4
        │       │       │
        │       │       ▼
        │       │   评测结果 JSON              ← T8
        │       │       │
        │       ├─ update_submission_result() ← T9（D6 已提供函数）
        │       ├─ update_problem_stats()     ← T10（D7 已提供函数）
        │       └─ 清理临时文件               ← T6
        │
        └─ redirect → submission_detail 页面
                        │
                        ▼
                用户看到 Pending → 刷新后看到结果
```

---

## ⚠️ 注意事项（排查过的坑）

1. **judge 模块路径**：`judge/` 下有两层 `judge/judge/`，import 时注意 `sys.path` 要加到外层 `judge/` 还是内层 `judge/judge/`
2. **时间单位**：DB 里 `time_limit` 是 ms（整数），但 judge 的 `main.py` demo 里用的是 `1.0`（秒）。`runner.py` 里 `timeout` 参数传给 `subprocess.run()`，单位是秒。需要做单位转换
3. **内存单位**：DB 里 `memory_limit` 是 KB（65536 = 64MB），judge 里注释写的是 MB。需要确认实际是怎么用的
4. **临时文件**：judge 运行时在 `config.py` 里指定了 `RUN_DIR`，默认是 `judge/judge/run_tmp/`。bridge 里写临时测试数据文件时，放哪？
5. **并发安全**：如果两个用户同时提交，两个线程会不会往同一个临时目录写文件？`JudgeController` 已经用 `submission_id` 隔离了 workspace 目录，但你写测试数据文件时也要注意

