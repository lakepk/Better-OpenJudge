# data/ — Web 层（路由、数据库、前端模板）

本目录是 LiteJudge 的 Web 层，包含 Flask 路由、SQLite 数据访问层和 Jinja2 模板。

---

## 文件结构

```
data/
├── app.py                  # Flask 主应用（路由、权限控制、API）
├── database.py             # 数据库操作层（建表、CRUD、业务查询）
├── requirements.txt        # Python 依赖
├── judge.db                # SQLite 数据库文件（运行时生成）
├── README.md               # 本文件
└── templates/              # Jinja2 模板
    ├── base.html           # 基础布局（导航栏、CSS、分页宏）
    ├── index.html          # 首页：公告 + 题目列表（含搜索筛选）
    ├── error.html          # 错误页（404/403）
    ├── login.html          # 登录页（含 CSRF token + 锁定提示）
    ├── register.html       # 注册页
    ├── problems.html       # 题目列表（含搜索、筛选、AC 标记）
    ├── problem_detail.html # 题目详情（Markdown 渲染 + 提交入口）
    ├── submit.html         # 代码提交页（CodeMirror 6 编辑器）
    ├── submissions.html    # 我的提交列表
    ├── submission_detail.html # 提交详情（highlight.js 高亮 + AJAX 轮询）
    ├── profile.html        # 个人中心
    ├── edit_profile.html   # 编辑个人资料
    ├── ranking.html        # 排行榜
    ├── contests.html       # 比赛列表
    ├── contest_detail.html # 比赛详情（题目列表 + 计分板）
    └── admin/              # 管理员模板
        ├── problems.html         # 题目管理列表（含重判按钮）
        ├── create_problem.html   # 创建/编辑题目表单（含 SPJ 配置）
        ├── edit_problem.html     # 编辑题目（复用 create_ 逻辑 + 预填）
        ├── test_cases.html       # 测试数据管理（含重判入口）
        ├── add_test_case.html    # 添加测试点表单
        ├── users.html            # 用户管理列表
        ├── submissions.html      # 全部提交管理（含单条重判按钮）
        ├── announcements.html    # 公告管理列表
        ├── create_announcement.html # 创建公告表单
        ├── contests.html         # 比赛管理列表
        └── create_contest.html   # 创建/编辑比赛表单（题目多选）
```

---

## app.py — 路由架构

### 权限模型

| 装饰器 | 作用 | 失败行为 |
|--------|------|---------|
| 无 | 公开访问 | — |
| `@login_required` | 已登录 | 302 → `/login` |
| `@admin_required` | role='admin' | 403 "权限不足" |
| 两者叠加 | 先登录检查、再管理员检查 | — |

### 路由模块（共 40+ 个端点）

| 模块 | 路由前缀 | 数量 | 主要功能 |
|------|---------|------|---------|
| 首页 | `/`, `/health` | 2 | 题目列表 + 健康检查 |
| 用户系统 | `/login`, `/register`, `/logout` | 3 | 登录（含限速锁）、注册、登出 |
| 排行榜 | `/ranking` | 1 | 用户 AC 排名 |
| 个人中心 | `/profile`, `/profile/edit` | 2 | 个人资料 + 编辑 |
| 题目系统 | `/problems`, `/problem/<id>`, `/problem/<id>/submit` | 3 | 列表（搜索筛选）、详情（Markdown）、提交 |
| 提交记录 | `/submissions`, `/submission/<id>` | 2 | 我的提交列表 + 详情 |
| 轮询 API | `/api/submission/<id>/status` | 1 | 前端 AJAX 轮询评测状态 |
| 比赛系统 | `/contests`, `/contest/<id>`, `/contest/<id>/register` | 3 | 比赛列表 + 详情/计分板 + 报名 |
| 管理员-题目 | `/admin/problems`, `/admin/create_problem`, `/admin/edit_problem/<id>`, `/admin/delete_problem/<id>`, `/admin/rejudge_problem/<id>`, `/admin/rejudge_submission/<id>` | 6 | CRUD + 重判 |
| 管理员-测试数据 | `/admin/problem/<id>/test_cases`, `/admin/problem/<id>/add_test_case`, `/admin/delete_test_case/<id>` | 3 | 测试点 CRUD |
| 管理员-用户 | `/admin/users`, `/admin/toggle_user/<id>` | 2 | 用户列表 + 启用/禁用 |
| 管理员-提交 | `/admin/submissions` | 1 | 全站提交总览 |
| 管理员-公告 | `/admin/announcements`, `/admin/create_announcement`, `/admin/delete_announcement/<id>` | 3 | 公告 CRUD |
| 管理员-比赛 | `/admin/contests`, `/admin/create_contest`, `/admin/edit_contest/<id>`, `/admin/delete_contest/<id>` | 4 | 比赛 CRUD |
| API v1 | `/api/v1/problems`, `/api/v1/problem/<id>`, `/api/v1/submit`, `/api/v1/submission/<id>` | 4 | JSON REST API（Bearer Token 认证） |

### 关键辅助函数

| 函数 | 位置 | 用途 |
|------|------|------|
| `render_markdown(text)` | app.py L27 | Markdown → 安全 HTML（XSS 防护） |
| `page_url(page_num)` | app.py L20 | 生成保留筛选参数的分页链接 |
| `inject_utils()` | app.py L18 | 向所有模板注入 `page_url` + `all_tags` |
| `api_login_required` | app.py L834 | API Token 认证装饰器 |

---

## database.py — 数据库层

### 表结构（11 张表）

| 表 | 主键 | 记录数（典型） | 说明 |
|----|------|--------------|------|
| `users` | id | < 1000 | 用户账号、密码哈希、角色、登录锁 |
| `problems` | id | < 1000 | 题目正文、时空限制、SPJ 配置 |
| `test_cases` | id | 每题目 5-50 | 测试输入/输出、分值、是否隐藏 |
| `submissions` | id | < 10万 | 提交代码、评测结果、耗时内存 |
| `announcements` | id | < 100 | 公告标题、内容、置顶 |
| `tags` | id | < 200 | 标签名 |
| `problem_tags` | (problem_id, tag_id) | — | 题目↔标签多对多 |
| `contests` | id | < 50 | 比赛信息、起止时间 |
| `contest_problems` | (contest_id, problem_id) | — | 比赛↔题目关联（含分值） |
| `contest_registrations` | (contest_id, user_id) | — | 比赛报名 |
| `api_tokens` | id | < 500 | API 认证 token |

### 函数清单（共 60+ 个）

```
get_db()                     # 连接（WAL + busy_timeout）
init_db()                    # 建表 + 迁移 ALTER TABLE

# 用户 (10)
create_user() / verify_user() / get_user_by_id() / get_user_by_username()
get_all_users() / update_user_profile() / toggle_user_active()
is_account_locked() / record_login_failure() / reset_login_failures()

# 题目 (9)
get_all_problems() / get_problem_by_id() / create_problem() / update_problem()
delete_problem() / get_problem_tags() / remove_tag_from_problem() / add_tag_to_problem()
get_all_tags() / update_problem_stats()

# 提交 (8)
create_submission() / update_submission_result() / get_submissions_by_user()
get_submission_detail() / get_submissions_by_problem() / get_all_submissions()
get_submission_ids_by_problem() / reset_submission_for_rejudge()
get_queue_position()

# 公告 (4)
get_announcements() / create_announcement() / update_announcement()
delete_announcement()

# 排名 & AC (2)
get_user_ac_problem_ids() / get_ranking()

# API Token (4)
create_api_token() / get_user_by_token() / get_user_tokens() / delete_api_token()

# 比赛 (10)
create_contest() / update_contest() / delete_contest() / get_all_contests()
get_contest_by_id() / add_problem_to_contest() / remove_problem_from_contest()
register_for_contest() / is_registered_for_contest()
get_contest_standings() / get_contest_problems()

# 测试数据 (5)
add_test_case() / get_test_cases() / update_test_case() / delete_test_case()
```

### 数据库连接策略

- 每次函数调用独立 `get_db()` → 操作 → `conn.close()`（短连接）
- 启用 WAL 模式：读写并发不互斥
- `busy_timeout=5000`：写操作最多等 5 秒而非立即报错
- 查询结果使用 `sqlite3.Row`，支持列名访问 `row['column']`

---

## 依赖项

| 包 | 版本 | 用途 |
|----|------|------|
| flask | >=3.0 | Web 框架 |
| flask-wtf | — | CSRF 保护 |
| markdown | >=3.7 | Markdown → HTML 渲染 |
| Pygments | >=2.18 | 代码语法高亮（codehilite 扩展） |
| gunicorn | — | 生产 WSGI 服务器 |
| werkzeug | — | 密码哈希（Flask 依赖） |

---

## 开发要点

1. **CSRF**：所有 `<form method="post">` 必须包含 `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`
2. **XSS 防护**：`render_markdown()` 已经转义内嵌 HTML，模板用 `rendered_*` 字段 + `| safe`
3. **分页**：列表查询函数返回 `(items, total)` 元组，模板用 `pagination` 宏渲染
4. **编号风格**：Python 函数 `snake_case`，HTML 模板 `snake_case.html`，URL 路径 `kebab-case`
5. **数据库迁移**：使用 Alembic（`cd .. && alembic revision -m "描述"`），不使用裸 SQL 改表
6. **评测机对接**：`app.py` 中 `TODO: 对接评测机` 处留空，由 web/bridge.py 的 monkey-patch 实际触发评测