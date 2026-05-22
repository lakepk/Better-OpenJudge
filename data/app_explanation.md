# LiteJudge 路由总览

## 公开路由（无需登录）

| 路径 | 方法 | 说明 | 模板 |
|------|------|------|------|
| `/` | GET | 首页：展示公告列表和题目列表 | `index.html` |
| `/register` | GET | 显示注册页面 | `register.html` |
| `/register` | POST | 处理注册表单提交 | 重定向到登录页 |
| `/login` | GET | 显示登录页面 | `login.html` |
| `/login` | POST | 处理登录表单提交 | 重定向到首页 |
| `/logout` | GET | 清除 session，退出登录 | 重定向到首页 |
| `/problems` | GET | 题目列表（普通用户只能看到公开题目） | `problems.html` |
| `/problem/<id>` | GET | 题目详情（隐藏题目仅管理员可见） | `problem_detail.html` |

---

## 普通用户路由（需要登录）

| 路径 | 方法 | 权限 | 说明 | 模板 |
|------|------|------|------|------|
| `/profile` | GET | 登录 | 个人中心：查看个人信息和最近提交 | `profile.html` |
| `/profile/edit` | GET | 登录 | 编辑个人资料页面 | `edit_profile.html` |
| `/profile/edit` | POST | 登录 | 保存个人资料修改 | 重定向到 `/profile` |
| `/problem/<id>/submit` | GET | 登录 | 代码提交页面 | `submit.html` |
| `/problem/<id>/submit` | POST | 登录 | 处理代码提交，创建提交记录 | 重定向到 `/submission/<id>` |
| `/submissions` | GET | 登录 | 查看自己的提交记录 | `submissions.html` |
| `/submission/<id>` | GET | 登录 | 查看单条提交详情（普通用户只能看自己的） | `submission_detail.html` |

---

## 管理员路由（需要登录 + 管理员身份）

### 题目管理

| 路径 | 方法 | 说明 | 模板 |
|------|------|------|------|
| `/admin/problems` | GET | 题目管理列表（含隐藏题目） | `admin/problems.html` |
| `/admin/create_problem` | GET | 创建题目页面 | `admin/create_problem.html` |
| `/admin/create_problem` | POST | 处理创建题目 | 重定向到 `/problem/<id>` |
| `/admin/edit_problem/<id>` | GET | 编辑题目页面 | `admin/edit_problem.html` |
| `/admin/edit_problem/<id>` | POST | 保存题目修改 | 重定向到 `/problem/<id>` |
| `/admin/delete_problem/<id>` | POST | 删除题目（级联删除测试数据、提交记录、标签关联） | 重定向到 `/admin/problems` |

### 测试数据管理

| 路径 | 方法 | 说明 | 模板 |
|------|------|------|------|
| `/admin/problem/<id>/test_cases` | GET | 查看某题目的所有测试点 | `admin/test_cases.html` |
| `/admin/problem/<id>/add_test_case` | GET | 添加测试点页面 | `admin/add_test_case.html` |
| `/admin/problem/<id>/add_test_case` | POST | 保存新测试点 | 重定向到测试点列表 |
| `/admin/delete_test_case/<id>` | POST | 删除指定测试点 | 返回上一页 |

### 用户管理

| 路径 | 方法 | 说明 | 模板 |
|------|------|------|------|
| `/admin/users` | GET | 所有用户列表 | `admin/users.html` |
| `/admin/toggle_user/<id>` | POST | 启用/禁用用户 | 重定向到 `/admin/users` |

### 提交管理

| 路径 | 方法 | 说明 | 模板 |
|------|------|------|------|
| `/admin/submissions` | GET | 查看系统所有提交记录 | `admin/submissions.html` |

### 公告管理

| 路径 | 方法 | 说明 | 模板 |
|------|------|------|------|
| `/admin/announcements` | GET | 公告管理列表 | `admin/announcements.html` |
| `/admin/create_announcement` | GET | 创建公告页面 | `admin/create_announcement.html` |
| `/admin/create_announcement` | POST | 保存新公告 | 重定向到公告列表 |
| `/admin/delete_announcement/<id>` | POST | 删除指定公告 | 重定向到公告列表 |

---

## 错误页面

| 场景 | HTTP 状态码 | 说明 |
|------|------------|------|
| 题目不存在 | 404 | `problem_id` 对应的题目不存在 |
| 提交记录不存在 | 404 | `submission_id` 对应的提交不存在 |
| 权限不足 | 403 | 非管理员访问管理员页面 |
| 无权查看提交 | 403 | 普通用户查看他人的提交详情 |
| 未登录 | 302 | 重定向到登录页 |

---

## 权限控制说明

| 装饰器 | 作用 | 未满足时行为 |
|--------|------|-------------|
| `@login_required` | 要求已登录 | 重定向到 `/login` |
| `@admin_required` | 要求管理员身份 | 返回 403 "权限不足，仅限管理员访问" |
| 两者叠加 | 先检查登录，再检查管理员 | 未登录 → 重定向；非管理员 → 403 |
