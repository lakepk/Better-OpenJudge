# Demo Branch 设计文档

> 路演分支（Luyan），用于展示 Better-OpenJudge 的核心功能。
> 基于当前 `Luyan` 分支开发。

---

## 一、数据库设计

只需新建 **2 张表**，`submissions` 表新增 1 列，其余全部复用现有结构。

### 1.1 修改 `submissions` 表

```sql
ALTER TABLE submissions ADD COLUMN contest_id INTEGER DEFAULT NULL;
```

- `NULL` = 常规练习提交，不计入比赛
- 非 NULL = 属于某场比赛（用于排行过滤和可见性控制）

### 1.2 新建 `contests` 表

```sql
CREATE TABLE IF NOT EXISTS contests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    description   TEXT    DEFAULT '',
    start_time    TEXT    NOT NULL,   -- ISO 8601 格式
    end_time      TEXT    NOT NULL,
    is_visible    INTEGER DEFAULT 1,
    created_by    INTEGER NOT NULL,
    created_at    TEXT    DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (created_by) REFERENCES users(id)
);
```

### 1.3 新建 `contest_problems` 表

```sql
CREATE TABLE IF NOT EXISTS contest_problems (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    contest_id  INTEGER NOT NULL,
    problem_id  INTEGER NOT NULL,
    sort_order  INTEGER DEFAULT 0,
    FOREIGN KEY (contest_id)  REFERENCES contests(id)  ON DELETE CASCADE,
    FOREIGN KEY (problem_id)  REFERENCES problems(id)  ON DELETE CASCADE,
    UNIQUE(contest_id, problem_id)
);
```

### 1.4 设计取舍

- **不建比赛报名表**：路演版简化，登录即可参赛
- **不设分值字段**：ACM 赛制每道题权重相等
- **仅管理员可创建比赛**：复用现有 admin 权限体系

---

## 二、路由与页面设计

### 2.1 新增路由

| 路由 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/contests` | GET | 所有人 | 比赛列表页 |
| `/contest/<id>` | GET | 所有人 | 比赛详情 + 题目清单 + 简易排行榜 |
| `/contest/<id>/ranking` | GET | 所有人 | 比赛完整排行榜 |
| `/ranking` | GET | 所有人 | 全局排行榜 |
| `/admin/contests` | GET | 管理员 | 比赛管理列表 |
| `/admin/create_contest` | GET/POST | 管理员 | 创建比赛 |
| `/admin/edit_contest/<id>` | GET/POST | 管理员 | 编辑比赛 |
| `/admin/delete_contest/<id>` | POST | 管理员 | 删除比赛 |

### 2.2 修改现有路由

- **`/problem/<id>/submit`**（GET + POST）：接收可选 `?contest_id=` 参数，提交时写入 `contest_id`
- **`/submission/<id>`**：增加比赛可见性控制——比赛进行中时仅提交者本人和管理员可查看该提交
- **`/problem/<id>`**：比赛中访问时显示"返回比赛"链接

### 2.3 页面清单

```
新增模板（6 个）：
  contests.html              — 比赛列表卡片
  contest_detail.html        — 比赛首页（题目表 + 紧凑排行榜）
  contest_ranking.html       — 比赛完整排行榜
  ranking.html               — 全局排行榜
  admin/contests.html        — 管理后台比赛列表
  admin/create_contest.html  — 创建/编辑比赛表单

修改模板（4 个）：
  submit.html                — textarea 替换为 Monaco Editor
  submission_detail.html     — 代码块加语法高亮（highlight.js CDN）
  problem_detail.html        — 比赛中访问时显示"返回比赛"链接
  index.html                 — 首页改为控制台仪表盘布局
  base.html                  — 导航栏加「比赛」「排行榜」入口
```

---

## 三、Monaco Editor 集成

### 3.1 加载方式

CDN 加载，无需 npm/打包工具：

```html
<script src="https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs/loader.js"></script>
```

首次约 800KB（gzip），浏览器缓存后秒开。

### 3.2 编辑器初始化

```
页面加载 → loader.js 完成 → require(['vs/editor/editor.main'], callback)
→ 在 <div id="editor-container"> 上创建编辑器
→ 内容变化时同步写入隐藏 <textarea name="code">
→ 表单提交走原有逻辑，零后端改动
```

### 3.3 编辑器配置

- 主题：`vs-dark`（深色，接近 VS Code 视觉）
- 语言：默认 C++，下拉框切换 C++/Python 时调用 `setModelLanguage`
- 字体：14px，关闭 minimap，启用括号着色
- 语法检测：Monaco 自带 tokenizer 自动标注语法错误（红色波浪线），无需后端

### 3.4 改动范围

| 文件 | 改动 |
|------|------|
| `data/templates/submit.html` | 替换 `<textarea>` 为 Monaco 容器 + 隐藏 textarea + JS 初始化 |
| `data/app.py` | **无改动**（表单字段名不变） |

---

## 四、比赛逻辑 & 排行算法

### 4.1 比赛生命周期

- **未开始**：题目不可查看/不可提交，显示倒计时
- **进行中**：可查看题目、提交代码；他人提交在结束前不可见
- **已结束**：全部公开，题目可继续练习但不计入比赛成绩

### 4.2 排行榜算法（ACM 赛制）

**排序规则**：AC 数降序 → 罚时升序 → 昵称字典序

**罚时计算**（每题累计）：
```
罚时 = (首次 AC 时间 - 比赛开始时间) + (首次 AC 前该题的 WA/TLE 次数 × 20 分钟)
```

**实现方式**：`database.py` 中新增 `get_contest_ranking(contest_id)` 函数，
SQL 先找每用户每题首次 AC 记录作为 winner，再 COUNT 该 AC 之前的 WA/TLE 数，
最后 GROUP BY 用户聚合 AC 数和总罚时。

未 AC 的题目不贡献罚时（这是 ACM 赛制核心特征）。

### 4.3 全局排行榜

只统计 `contest_id IS NULL` 的练习提交（不混入比赛数据），按 AC 数降序排列：

```sql
SELECT u.nickname, COUNT(DISTINCT s.problem_id) as ac_count
FROM users u
JOIN submissions s ON u.id = s.user_id
WHERE s.status = 'AC' AND s.contest_id IS NULL
GROUP BY u.id
ORDER BY ac_count DESC
```

### 4.4 比赛提交可见性控制

在 `submission_detail` 路由中增加判断：
- 如果提交关联了比赛且比赛进行中 + 当前用户既非提交者也非管理员 → 返回 403
- 比赛结束后恢复所有人可见

### 4.5 交题入口

1. **从比赛页面进入**：`/contest/<cid>/problem/<pid>` → 提交跳转带 `?contest_id=` → 页面显示"比赛模式"横幅
2. **从题库进入**：不带 contest_id，走练习模式

---

## 五、首页功能入口面板

替换当前简单首页为控制台/仪表盘风格，卡片网格展示所有功能入口。

### 5.1 布局

```
┌──────────────────────────────────────────────────┐
│  公告区（保留）                                     │
├────────────┬────────────┬────────────┬───────────┤
│ 📝 题库     │ 🏆 比赛     │ 🏅 排行榜   │ 👤 个人中心│
├────────────┴────────────┴────────────┴───────────┤
│ 🔧 管理面板（仅管理员可见）                          │
│ ┌──────────┬──────────┬──────────┬──────────────┐│
│ │📋 题目管理│👥 用户管理│📢 公告管理│🏗 比赛管理     ││
│ │📊 提交总览│          │          │              ││
│ └──────────┴──────────┴──────────┴──────────────┘│
├──────────────────────────────────────────────────┤
│  题目列表（保留）                                   │
└──────────────────────────────────────────────────┘
```

### 5.2 实现方式

- 纯 CSS 卡片网格（`box-shadow` + `border-radius` + `hover` 动效）
- 管理员行用 `{% if session.role == 'admin' %}` 控制显隐
- 未登录时导航区显示"登录"和"注册"入口

---

## 完整改动汇总

| 区域 | 新增 | 修改 |
|------|------|------|
| 数据库 | `contests` 表、`contest_problems` 表 | `submissions` 加 `contest_id` 列 |
| Flask 路由 | 8 个新路由 | 3 个路由增加参数/可见性逻辑 |
| Python | `database.py` 约 8 个新函数 | `app.py` 约 6 个新视图 + 首页改版 |
| 模板 | 6 个新模板 | 5 个模板修改 |
| 静态资源 | 无 | 无（Monaco + highlight.js 均走 CDN） |
