# LiteJudge 数据库函数清单

## 初始化
| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `get_db()` | 无 | `sqlite3.Connection` | 获取数据库连接，设置 `row_factory = sqlite3.Row`，使查询结果可通过列名访问 |
| `init_db()` | 无 | 无 | 创建所有表结构，若表已存在则跳过，保证数据库结构完整 |

---

## 用户表 `users`

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | INTEGER | 自增 | 主键，用户唯一标识 |
| `username` | TEXT | - | 用户名，唯一，不可为空 |
| `password_hash` | TEXT | - | 密码哈希值（werkzeug 加密），不可为空 |
| `email` | TEXT | `''` | 邮箱地址 |
| `nickname` | TEXT | `''` | 昵称/显示名称 |
| `role` | TEXT | `'user'` | 角色：`'user'`（普通用户）或 `'admin'`（管理员） |
| `avatar_url` | TEXT | `''` | 头像URL |
| `created_at` | DATETIME | 当前时间 | 注册时间 |
| `last_login` | TIMESTAMP | NULL | 最后登录时间 |
| `is_active` | BOOLEAN | `1` | 账号状态：`1`正常，`0`禁用 |

### 用户操作函数
| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `create_user()` | `username, password, email='', nickname=''` | `(bool, str)` | 创建新用户。<br>返回 `(True, "注册成功")` 或 `(False, "用户名已存在")` |
| `verify_user()` | `username, password` | `(bool, dict/str)` | 验证登录。<br>成功返回 `(True, 用户数据字典)`<br>失败返回 `(False, 错误信息)`<br>验证通过后自动更新 `last_login` |
| `get_user_by_id()` | `user_id` | `dict 或 None` | 根据ID获取用户完整信息 |
| `get_user_by_username()` | `username` | `dict 或 None` | 根据用户名获取用户完整信息 |
| `get_all_users()` | 无 | `list[dict]` | 获取所有用户列表，不含密码哈希（管理员功能） |
| `update_user_profile()` | `user_id, nickname='', email='', avatar_url=''` | `bool` | 更新用户昵称、邮箱、头像 |
| `toggle_user_active()` | `user_id` | 无 | 切换用户启用/禁用状态（管理员功能） |

---

## 题目表 `problems`

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | INTEGER | 自增 | 主键，题目唯一标识 |
| `title` | TEXT | - | 题目标题，不可为空 |
| `description` | TEXT | `''` | 题目描述（支持 Markdown） |
| `input_format` | TEXT | `''` | 输入格式说明 |
| `output_format` | TEXT | `''` | 输出格式说明 |
| `sample_input` | TEXT | `''` | 样例输入 |
| `sample_output` | TEXT | `''` | 样例输出 |
| `hint` | TEXT | `''` | 提示信息 |
| `source` | TEXT | `''` | 题目来源（如：LeetCode 第X题） |
| `difficulty` | INTEGER | `1` | 难度等级：`1`简单，`2`中等，`3`困难 |
| `time_limit` | INTEGER | `1000` | 时间限制，单位毫秒（ms） |
| `memory_limit` | INTEGER | `65536` | 内存限制，单位千字节（KB），65536KB = 64MB |
| `is_visible` | BOOLEAN | `1` | 是否公开：`1`可见，`0`隐藏（仅管理员可见） |
| `accepted_count` | INTEGER | `0` | 通过次数（由 `update_problem_stats()` 自动更新） |
| `submission_count` | INTEGER | `0` | 提交总次数（由 `update_problem_stats()` 自动更新） |
| `created_at` | DATETIME | 当前时间 | 题目创建时间 |
| `updated_at` | DATETIME | 当前时间 | 题目最后更新时间 |

### 题目操作函数
| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `get_all_problems()` | `is_admin=False` | `list[dict]` | 获取题目列表。<br>管理员可看到所有题目（含隐藏），普通用户只能看到 `is_visible=1` 的题目 |
| `get_problem_by_id()` | `problem_id` | `dict 或 None` | 获取题目完整详情，附加 `tags` 字段（标签名列表） |
| `create_problem()` | `title, description, input_format, output_format, sample_input, sample_output, hint='', source='', difficulty=1, time_limit=1000, memory_limit=65536` | `int` | 创建新题目，返回新题目ID |
| `update_problem()` | `problem_id, **kwargs` | `bool` | 更新题目信息。<br>可更新字段：`title`, `description`, `input_format`, `output_format`, `sample_input`, `sample_output`, `hint`, `source`, `difficulty`, `time_limit`, `memory_limit`, `is_visible` |
| `delete_problem()` | `problem_id` | 无 | 级联删除：题目本身 + 关联的标签关系 + 测试数据 + 提交记录 |
| `update_problem_stats()` | `problem_id` | 无 | 统计该题目的总提交数和AC数，更新 `submission_count` 和 `accepted_count` |

---

## 测试数据表 `test_cases`

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | INTEGER | 自增 | 主键，测试点唯一标识 |
| `problem_id` | INTEGER | - | 外键，关联 `problems.id` |
| `case_order` | INTEGER | `1` | 测试点序号，决定评测顺序 |
| `input` | TEXT | - | 该测试点的标准输入数据 |
| `output` | TEXT | - | 该测试点的标准输出答案 |
| `score` | INTEGER | `10` | 该测试点分值 |
| `is_hidden` | BOOLEAN | `0` | 是否隐藏：`0`样例测试点（用户可见），`1`隐藏测试点（仅管理员可见） |
| `created_at` | DATETIME | 当前时间 | 创建时间 |

### 测试数据操作函数
| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `add_test_case()` | `problem_id, input_data, output_data, case_order=1, score=10, is_hidden=0` | 无 | 添加一个测试点 |
| `get_test_cases()` | `problem_id` | `list[dict]` | 获取某题目的所有测试点，按 `case_order` 升序排列 |
| `update_test_case()` | `case_id, **kwargs` | `bool` | 更新测试点。<br>可更新字段：`input`, `output`, `case_order`, `score`, `is_hidden` |
| `delete_test_case()` | `case_id` | 无 | 删除指定测试点 |

---

## 提交记录表 `submissions`

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | INTEGER | 自增 | 主键，提交唯一标识 |
| `user_id` | INTEGER | - | 外键，关联 `users.id` |
| `problem_id` | INTEGER | - | 外键，关联 `problems.id` |
| `code` | TEXT | - | 用户提交的源代码 |
| `language` | TEXT | `'cpp'` | 编程语言：`'cpp'`（C++）或 `'python'` |
| `status` | TEXT | `'Pending'` | 评测状态：`Pending`（等待中）、`Compiling`（编译中）、`Running`（运行中）、`AC`（通过）、`WA`（答案错误）、`TLE`（超时）、`MLE`（内存超限）、`RE`（运行错误）、`CE`（编译错误） |
| `score` | INTEGER | `0` | 得分 |
| `time_used` | INTEGER | `0` | 运行时间，单位毫秒（ms） |
| `memory_used` | INTEGER | `0` | 运行内存，单位千字节（KB） |
| `compiler_output` | TEXT | `''` | 编译错误信息（CE时显示） |
| `judge_detail` | TEXT | `''` | 评测详情（JSON字符串，记录各测试点结果） |
| `created_at` | TIMESTAMP | 当前时间 | 提交时间 |

### 评测状态流转
Pending → Compiling → [CE 或 Running]
Running → AC / WA / TLE / MLE / RE


### 提交记录操作函数
| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `create_submission()` | `user_id, problem_id, code, language='cpp'` | `int` | 创建提交记录，状态初始为 `Pending`，返回提交ID |
| `update_submission_result()` | `submission_id, status, score=0, time_used=0, memory_used=0, compiler_output='', judge_detail=''` | 无 | 评测完成后更新结果 |
| `get_submissions_by_user()` | `user_id, limit=50` | `list[dict]` | 获取某用户的提交记录，按时间倒序，最多50条 |
| `get_submissions_by_problem()` | `problem_id, limit=50` | `list[dict]` | 获取某题目的所有提交记录，含提交者用户名 |
| `get_all_submissions()` | `limit=100` | `list[dict]` | 获取系统全部提交记录（管理员功能） |
| `get_submission_detail()` | `submission_id` | `dict 或 None` | 获取单条提交的完整详情，含题目标题和用户名 |

---

## 公告表 `announcements`

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | INTEGER | 自增 | 主键，公告唯一标识 |
| `title` | TEXT | - | 公告标题，不可为空 |
| `content` | TEXT | `''` | 公告正文内容 |
| `is_pinned` | BOOLEAN | `0` | 是否置顶：`1`置顶，`0`不置顶 |
| `created_at` | TIMESTAMP | 当前时间 | 发布时间 |

### 公告操作函数
| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `get_announcements()` | 无 | `list[dict]` | 获取公告列表，置顶优先，同级别按时间倒序 |
| `create_announcement()` | `title, content, is_pinned=0` | 无 | 创建新公告 |
| `update_announcement()` | `announcement_id, **kwargs` | `bool` | 更新公告。<br>可更新字段：`title`, `content`, `is_pinned` |
| `delete_announcement()` | `announcement_id` | 无 | 删除指定公告 |

---

## 标签表 `tags`

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | INTEGER | 自增 | 主键，标签唯一标识 |
| `name` | TEXT | - | 标签名，唯一（如：动态规划、贪心、DFS、字符串） |

---

## 题目-标签关联表 `problem_tags`

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `problem_id` | INTEGER | - | 外键，关联 `problems.id` |
| `tag_id` | INTEGER | - | 外键，关联 `tags.id` |
| 联合主键 | - | - | `(problem_id, tag_id)` 组合唯一，防止重复关联 |

### 标签操作函数
| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `add_tag_to_problem()` | `problem_id, tag_name` | `bool` | 给题目添加标签。<br>标签不存在时自动创建，标签已关联时忽略（不重复添加） |
| `remove_tag_from_problem()` | `problem_id, tag_name` | 无 | 移除题目的指定标签（不删除标签本身） |
| `get_problem_tags()` | `problem_id` | `list[dict]` | 获取某题目的所有标签，每条包含 `id` 和 `name` |
| `get_all_tags()` | 无 | `list[dict]` | 获取系统中所有已创建的标签，按名称排序 |