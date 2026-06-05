import os

from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps
from database import *

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-use-env-var-in-production')

# 启动时初始化数据库
init_db()


# ==================== 权限装饰器 ====================
def login_required(f):
    """要求用户登录"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """要求管理员身份"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return "权限不足，仅限管理员访问", 403
        return f(*args, **kwargs)
    return decorated_function


# ==================== 首页 ====================
@app.route('/')
def index():
    announcements = get_announcements()
    problems = get_all_problems(is_admin=(session.get('role') == 'admin'))
    return render_template('index.html',
                           user=session,
                           problems=problems,
                           announcements=announcements)


# ==================== 用户系统 ====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    # 临时关闭公开注册
    return redirect(url_for('login', error='注册功能暂时关闭'))
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        email = request.form.get('email', '').strip()
        nickname = request.form.get('nickname', '').strip()

        # 表单验证
        if not username or not password:
            return render_template('register.html', error='用户名和密码不能为空')
        if len(username) < 3:
            return render_template('register.html', error='用户名至少3个字符')
        if len(username) > 20:
            return render_template('register.html', error='用户名最多20个字符')
        if password != confirm:
            return render_template('register.html', error='两次密码不一致')
        if len(password) < 6:
            return render_template('register.html', error='密码至少6位')

        success, message = create_user(username, password, email, nickname)
        if success:
            return render_template('login.html',
                                   success='注册成功，请登录',
                                   user=session)
        else:
            return render_template('register.html', error=message, user=session)

    return render_template('register.html', user=session)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('login.html', error='请输入用户名和密码', user=session)

        success, result = verify_user(username, password)
        if success:
            session['user_id'] = result['id']
            session['username'] = result['username']
            session['role'] = result['role']
            session['nickname'] = result['nickname']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error=result, user=session)

    return render_template('login.html', error=request.args.get('error'), user=session)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# ==================== 用户个人中心 ====================
@app.route('/profile')
@login_required
def profile():
    user = get_user_by_id(session['user_id'])
    submissions = get_submissions_by_user(session['user_id'], limit=20)
    return render_template('profile.html',
                           profile_user=user,
                           submissions=submissions,
                           user=session)


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        email = request.form.get('email', '').strip()

        update_user_profile(session['user_id'],
                            nickname=nickname,
                            email=email)
        session['nickname'] = nickname  # 更新 session 中的昵称
        return redirect(url_for('profile'))

    user = get_user_by_id(session['user_id'])
    return render_template('edit_profile.html',
                           profile_user=user,
                           user=session)


# ==================== 题目系统 ====================
@app.route('/problems')
def problem_list():
    is_admin = session.get('role') == 'admin'
    problems = get_all_problems(is_admin=is_admin)
    return render_template('problems.html',
                           problems=problems,
                           user=session)


@app.route('/problem/<int:problem_id>')
def problem_detail(problem_id):
    problem = get_problem_by_id(problem_id)

    if not problem:
        return render_template('error.html',
                               message='题目不存在',
                               user=session), 404

    if not problem['is_visible'] and session.get('role') != 'admin':
        return render_template('error.html',
                               message='题目不存在',
                               user=session), 404

    return render_template('problem_detail.html',
                           problem=problem,
                           user=session)


@app.route('/problem/<int:problem_id>/submit', methods=['GET', 'POST'])
@login_required
def submit_code(problem_id):
    problem = get_problem_by_id(problem_id)

    if not problem:
        return render_template('error.html',
                               message='题目不存在',
                               user=session), 404

    if not problem['is_visible'] and session.get('role') != 'admin':
        return render_template('error.html',
                               message='题目不存在',
                               user=session), 404

    if request.method == 'POST':
        code = request.form.get('code', '')
        language = request.form.get('language', 'cpp')

        if not code.strip():
            return render_template('submit.html',
                                   problem=problem,
                                   user=session,
                                   error='代码不能为空')

        # 创建提交记录
        submission_id = create_submission(session['user_id'],
                                          problem_id,
                                          code,
                                          language)

        # TODO: 对接评测机
        # judge_submission(submission_id)

        return redirect(url_for('submission_detail',
                                submission_id=submission_id))

    return render_template('submit.html',
                           problem=problem,
                           user=session)


# ==================== 提交记录 ====================
@app.route('/submissions')
@login_required
def submission_list():
    submissions = get_submissions_by_user(session['user_id'], limit=50)
    return render_template('submissions.html',
                           submissions=submissions,
                           user=session)


@app.route('/submission/<int:submission_id>')
@login_required
def submission_detail(submission_id):
    submission = get_submission_detail(submission_id)

    if not submission:
        return render_template('error.html',
                               message='提交记录不存在',
                               user=session), 404

    # 普通用户只能看自己的提交
    if submission['user_id'] != session['user_id'] and session.get('role') != 'admin':
        return render_template('error.html',
                               message='无权查看此提交',
                               user=session), 403

    return render_template('submission_detail.html',
                           submission=submission,
                           user=session)


# ==================== 管理员 - 题目管理 ====================
@app.route('/admin/problems')
@login_required
@admin_required
def admin_problem_list():
    problems = get_all_problems(is_admin=True)
    return render_template('admin/problems.html',
                           problems=problems,
                           user=session)


@app.route('/admin/create_problem', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_problem():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '')
        input_format = request.form.get('input_format', '')
        output_format = request.form.get('output_format', '')
        sample_input = request.form.get('sample_input', '')
        sample_output = request.form.get('sample_output', '')
        hint = request.form.get('hint', '')
        source = request.form.get('source', '')
        difficulty = int(request.form.get('difficulty', 1))
        time_limit = int(request.form.get('time_limit', 1000))
        memory_limit = int(request.form.get('memory_limit', 65536))
        tags_str = request.form.get('tags', '')

        if not title:
            return render_template('admin/create_problem.html',
                                   error='题目标题不能为空',
                                   user=session)

        problem_id = create_problem(title=title,
                                    description=description,
                                    input_format=input_format,
                                    output_format=output_format,
                                    sample_input=sample_input,
                                    sample_output=sample_output,
                                    hint=hint,
                                    source=source,
                                    difficulty=difficulty,
                                    time_limit=time_limit,
                                    memory_limit=memory_limit)

        # 处理标签
        if tags_str:
            tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            for tag in tags:
                add_tag_to_problem(problem_id, tag)

        return redirect(url_for('problem_detail', problem_id=problem_id))

    return render_template('admin/create_problem.html', user=session)


@app.route('/admin/edit_problem/<int:problem_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_problem(problem_id):
    problem = get_problem_by_id(problem_id)
    if not problem:
        return render_template('error.html',
                               message='题目不存在',
                               user=session), 404

    if request.method == 'POST':
        update_data = {
            'title': request.form.get('title', '').strip(),
            'description': request.form.get('description', ''),
            'input_format': request.form.get('input_format', ''),
            'output_format': request.form.get('output_format', ''),
            'sample_input': request.form.get('sample_input', ''),
            'sample_output': request.form.get('sample_output', ''),
            'hint': request.form.get('hint', ''),
            'source': request.form.get('source', ''),
            'difficulty': int(request.form.get('difficulty', 1)),
            'time_limit': int(request.form.get('time_limit', 1000)),
            'memory_limit': int(request.form.get('memory_limit', 65536)),
            'is_visible': int(request.form.get('is_visible', 1))
        }

        update_problem(problem_id, **update_data)

        # 更新标签
        tags_str = request.form.get('tags', '')
        if tags_str:
            # 清除旧标签
            existing_tags = get_problem_tags(problem_id)
            for t in existing_tags:
                remove_tag_from_problem(problem_id, t['name'])
            # 添加新标签
            tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            for tag in tags:
                add_tag_to_problem(problem_id, tag)

        return redirect(url_for('problem_detail', problem_id=problem_id))

    return render_template('admin/edit_problem.html',
                           problem=problem,
                           user=session)


@app.route('/admin/delete_problem/<int:problem_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_problem(problem_id):
    delete_problem(problem_id)
    return redirect(url_for('admin_problem_list'))


# ==================== 管理员 - 测试数据管理 ====================
@app.route('/admin/problem/<int:problem_id>/test_cases')
@login_required
@admin_required
def admin_test_cases(problem_id):
    problem = get_problem_by_id(problem_id)
    if not problem:
        return render_template('error.html',
                               message='题目不存在',
                               user=session), 404

    test_cases = get_test_cases(problem_id)
    return render_template('admin/test_cases.html',
                           problem=problem,
                           test_cases=test_cases,
                           user=session)


@app.route('/admin/problem/<int:problem_id>/add_test_case', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_test_case(problem_id):
    problem = get_problem_by_id(problem_id)
    if not problem:
        return render_template('error.html',
                               message='题目不存在',
                               user=session), 404

    if request.method == 'POST':
        input_data = request.form.get('input', '')
        output_data = request.form.get('output', '')
        case_order = int(request.form.get('case_order', 1))
        score = int(request.form.get('score', 10))
        is_hidden = int(request.form.get('is_hidden', 0))

        add_test_case(problem_id, input_data, output_data,
                      case_order=case_order,
                      score=score,
                      is_hidden=is_hidden)

        return redirect(url_for('admin_test_cases', problem_id=problem_id))

    return render_template('admin/add_test_case.html',
                           problem=problem,
                           user=session)


@app.route('/admin/delete_test_case/<int:case_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_test_case(case_id):
    delete_test_case(case_id)
    return redirect(request.referrer or url_for('index'))


# ==================== 管理员 - 用户管理 ====================
@app.route('/admin/users')
@login_required
@admin_required
def admin_user_list():
    users = get_all_users()
    return render_template('admin/users.html',
                           users=users,
                           user=session)


@app.route('/admin/toggle_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_toggle_user(user_id):
    toggle_user_active(user_id)
    return redirect(url_for('admin_user_list'))


# ==================== 管理员 - 提交记录总览 ====================
@app.route('/admin/submissions')
@login_required
@admin_required
def admin_submission_list():
    submissions = get_all_submissions(limit=200)
    return render_template('admin/submissions.html',
                           submissions=submissions,
                           user=session)


# ==================== 管理员 - 公告管理 ====================
@app.route('/admin/announcements')
@login_required
@admin_required
def admin_announcement_list():
    announcements = get_announcements()
    return render_template('admin/announcements.html',
                           announcements=announcements,
                           user=session)


@app.route('/admin/create_announcement', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_announcement():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '')
        is_pinned = int(request.form.get('is_pinned', 0))

        if title:
            create_announcement(title, content, is_pinned)

        return redirect(url_for('admin_announcement_list'))

    return render_template('admin/create_announcement.html', user=session)


@app.route('/admin/delete_announcement/<int:announcement_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_announcement(announcement_id):
    delete_announcement(announcement_id)
    return redirect(url_for('admin_announcement_list'))


# ==================== 启动应用 ====================
if __name__ == '__main__':
    app.run(debug=True, port=5000)