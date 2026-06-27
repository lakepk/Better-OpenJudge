import os

from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps
from database import *
from flask_wtf.csrf import CSRFProtect
import markdown

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-use-env-var-in-production')
csrf = CSRFProtect(app)

# 启动时初始化数据库
init_db()


@app.context_processor
def inject_utils():
    """注入模板工具函数"""
    def page_url(page_num):
        args = dict(request.args)
        args['page'] = str(page_num)
        return '?' + '&'.join(f'{k}={v}' for k, v in args.items())
    return dict(page_url=page_url, all_tags=get_all_tags())


def render_markdown(text):
    """将 Markdown 文本安全渲染为 HTML，消除 XSS 风险"""
    if not text:
        return ''
    return markdown.markdown(
        text,
        extensions=[
            'fenced_code',
            'tables',
            'codehilite',
            'nl2br',
        ],
        extension_configs={
            'codehilite': {
                'css_class': 'highlight',
                'guess_lang': False,
            }
        }
    )


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
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    difficulty = request.args.get('difficulty', None, type=int)
    tag = request.args.get('tag', '').strip() or None

    is_admin = session.get('role') == 'admin'
    problems, total = get_all_problems(is_admin=is_admin, page=page,
                                        search=search, difficulty=difficulty, tag=tag)
    total_pages = max(1, (total + 19) // 20)

    # 已登录用户获取 AC 题目 ID 集合
    user_ac_set = get_user_ac_problem_ids(session.get('user_id')) if session.get('user_id') else set()

    return render_template('index.html',
                           user=session,
                           problems=problems,
                           announcements=announcements,
                           user_ac_set=user_ac_set,
                           page=page, total_pages=total_pages, total=total,
                           search=search, difficulty=difficulty or 0, tag=tag)

@app.route('/health')
def health_check():
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        return {"status":"ok", "database":"connected"}, 200
    except Exception as e:
        return {"status":"error", "database":str(e)}, 503


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
        
        # === 新增：检查是否被否定 ===
        locked, lock_msg = is_account_locked(username)
        if locked:
            return render_template('login.html', error=lock_msg, user=session)
        # ===========================

        success, result = verify_user(username, password)
        if success:
            reset_login_failures(username) # new
            session['user_id'] = result['id']
            session['username'] = result['username']
            session['role'] = result['role']
            session['nickname'] = result['nickname']
            return redirect(url_for('index'))
        else:
            record_login_failure(username) #new
            return render_template('login.html', error=result, user=session)

    return render_template('login.html', error=request.args.get('error'), user=session)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# ==================== 排行榜 ====================
@app.route('/ranking')
def ranking():
    page = request.args.get('page', 1, type=int)
    ranking_data, total = get_ranking(page=page, per_page=50)
    total_pages = max(1, (total + 49) // 50)
    return render_template('ranking.html',
                           user=session,
                           ranking=ranking_data,
                           page=page, total_pages=total_pages, total=total)


# ==================== 比赛系统 ====================
@app.route('/contests')
def contest_list():
    page = request.args.get('page', 1, type=int)
    is_admin = session.get('role') == 'admin'
    contests, total = get_all_contests(include_hidden=is_admin, page=page)
    total_pages = max(1, (total + 19) // 20)

    import datetime
    now = datetime.datetime.now().isoformat()

    return render_template('contests.html',
                           user=session,
                           contests=contests,
                           now=now,
                           page=page, total_pages=total_pages, total=total)


@app.route('/contest/<int:contest_id>')
def contest_detail(contest_id):
    contest = get_contest_by_id(contest_id)
    if not contest:
        return render_template('error.html',
                               message='比赛不存在', user=session), 404

    if not contest['is_visible'] and session.get('role') != 'admin':
        return render_template('error.html',
                               message='比赛不存在', user=session), 404

    standings = get_contest_standings(contest_id)
    is_registered = False
    if session.get('user_id'):
        is_registered = is_registered_for_contest(contest_id, session['user_id'])

    import datetime
    now = datetime.datetime.now().isoformat()

    return render_template('contest_detail.html',
                           user=session,
                           contest=contest,
                           standings=standings,
                           is_registered=is_registered,
                           now=now)


@app.route('/contest/<int:contest_id>/register', methods=['POST'])
@login_required
def contest_register(contest_id):
    success, msg = register_for_contest(contest_id, session['user_id'])
    return redirect(url_for('contest_detail', contest_id=contest_id))


# ==================== 管理员 - 比赛管理 ====================
@app.route('/admin/contests')
@login_required
@admin_required
def admin_contest_list():
    page = request.args.get('page', 1, type=int)
    contests, total = get_all_contests(include_hidden=True, page=page)
    total_pages = max(1, (total + 19) // 20)
    return render_template('admin/contests.html',
                           user=session,
                           contests=contests,
                           page=page, total_pages=total_pages, total=total)


@app.route('/admin/create_contest', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_contest():
    all_problems, _ = get_all_problems(is_admin=True, page=1, per_page=1000)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '')
        start_time = request.form.get('start_time', '')
        end_time = request.form.get('end_time', '')
        is_visible = int(request.form.get('is_visible', 1))

        if not title or not start_time or not end_time:
            return render_template('admin/create_contest.html',
                                   error='标题、开始时间和结束时间为必填项',
                                   user=session,
                                   all_problems=all_problems)

        contest_id = create_contest(title, description, start_time, end_time,
                                     session['user_id'], is_visible)

        # 添加题目
        problem_ids = request.form.getlist('problem_ids')
        for pid in problem_ids:
            if pid.strip():
                add_problem_to_contest(contest_id, int(pid))

        return redirect(url_for('contest_detail', contest_id=contest_id))

    return render_template('admin/create_contest.html',
                           user=session,
                           all_problems=all_problems)


@app.route('/admin/edit_contest/<int:contest_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_contest(contest_id):
    contest = get_contest_by_id(contest_id)
    if not contest:
        return render_template('error.html',
                               message='比赛不存在', user=session), 404

    all_problems, _ = get_all_problems(is_admin=True, page=1, per_page=1000)
    existing_problem_ids = {p['id'] for p in contest['problems']}

    if request.method == 'POST':
        update_data = {
            'title': request.form.get('title', '').strip(),
            'description': request.form.get('description', ''),
            'start_time': request.form.get('start_time', ''),
            'end_time': request.form.get('end_time', ''),
            'is_visible': int(request.form.get('is_visible', 1)),
        }
        update_contest(contest_id, **update_data)

        # 更新题目：先全部移除，再重新添加
        for p in contest['problems']:
            remove_problem_from_contest(contest_id, p['id'])
        problem_ids = request.form.getlist('problem_ids')
        for pid in problem_ids:
            if pid.strip():
                add_problem_to_contest(contest_id, int(pid))

        return redirect(url_for('contest_detail', contest_id=contest_id))

    return render_template('admin/create_contest.html',
                           user=session,
                           contest=contest,
                           all_problems=all_problems,
                           existing_problem_ids=existing_problem_ids)


@app.route('/admin/delete_contest/<int:contest_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_contest(contest_id):
    delete_contest(contest_id)
    return redirect(url_for('admin_contest_list'))


# ==================== 用户个人中心 ====================
@app.route('/profile')
@login_required
def profile():
    user = get_user_by_id(session['user_id'])
    page = request.args.get('page', 1, type=int)
    submissions, total = get_submissions_by_user(session['user_id'], page=page)
    total_pages = max(1, (total + 19) // 20)
    return render_template('profile.html',
                           profile_user=user,
                           submissions=submissions,
                           user=session,
                           page=page, total_pages=total_pages, total=total)


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
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    difficulty = request.args.get('difficulty', None, type=int)
    tag = request.args.get('tag', '').strip() or None

    problems, total = get_all_problems(is_admin=is_admin, page=page,
                                        search=search, difficulty=difficulty, tag=tag)
    total_pages = max(1, (total + 19) // 20)

    # 已登录用户获取 AC 题目 ID 集合
    user_ac_set = get_user_ac_problem_ids(session.get('user_id')) if session.get('user_id') else set()

    return render_template('problems.html',
                           problems=problems,
                           user=session,
                           user_ac_set=user_ac_set,
                           page=page, total_pages=total_pages, total=total,
                           search=search, difficulty=difficulty or 0, tag=tag)


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

    # 渲染 Markdown 字段为安全 HTML
    problem['rendered_description'] = render_markdown(problem['description'])
    problem['rendered_input_format'] = render_markdown(problem['input_format'])
    problem['rendered_output_format'] = render_markdown(problem['output_format'])
    problem['rendered_hint'] = render_markdown(problem['hint'])

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
    page = request.args.get('page', 1, type=int)
    submissions, total = get_submissions_by_user(session['user_id'], page=page)
    total_pages = max(1, (total + 19) // 20)
    return render_template('submissions.html',
                           submissions=submissions,
                           user=session,
                           page=page, total_pages=total_pages, total=total)


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


@app.route('/api/submission/<int:submission_id>/status')
@login_required
def api_submission_status(submission_id):
    """JSON API：返回提交的当前状态，供前端 AJAX 轮询"""
    submission = get_submission_detail(submission_id)
    if not submission:
        return {"error": "提交记录不存在"}, 404
    if submission['user_id'] != session['user_id'] and session.get('role') != 'admin':
        return {"error": "无权查看此提交"}, 403
    return {
        "id": submission['id'],
        "status": submission['status'],
        "score": submission['score'],
        "time_used": submission['time_used'],
        "memory_used": submission['memory_used'],
    }


# ==================== 管理员 - 题目管理 ====================
@app.route('/admin/problems')
@login_required
@admin_required
def admin_problem_list():
    page = request.args.get('page', 1, type=int)
    problems, total = get_all_problems(is_admin=True, page=page)
    total_pages = max(1, (total + 19) // 20)
    return render_template('admin/problems.html',
                           problems=problems,
                           user=session,
                           page=page, total_pages=total_pages, total=total)


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
        use_spj = int(request.form.get('use_spj', 0))
        spj_script = request.form.get('spj_script', '')

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
                                    memory_limit=memory_limit,
                                    use_spj=use_spj,
                                    spj_script=spj_script)

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
            'is_visible': int(request.form.get('is_visible', 1)),
            'use_spj': int(request.form.get('use_spj', 0)),
            'spj_script': request.form.get('spj_script', '')
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


@app.route('/admin/rejudge_problem/<int:problem_id>', methods=['POST'])
@login_required
@admin_required
def admin_rejudge_problem(problem_id):
    """重判某个题目的所有历史提交"""
    problem = get_problem_by_id(problem_id)
    if not problem:
        return render_template('error.html',
                               message='题目不存在',
                               user=session), 404

    submission_ids = get_submission_ids_by_problem(problem_id)
    if not submission_ids:
        return redirect(url_for('admin_problem_list'))

    # 重置所有提交为 Pending
    for sid in submission_ids:
        reset_submission_for_rejudge(sid)

    # 更新题目统计
    update_problem_stats(problem_id)

    # 尝试调用评测机异步重判
    try:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web'))
        from bridge import judge_async
        for sid in submission_ids:
            judge_async(sid)
        flash_msg = f"已重置 {len(submission_ids)} 条提交并触发重判"
    except ImportError:
        flash_msg = f"已重置 {len(submission_ids)} 条提交为 Pending（评测机未连接，将自动重判）"

    return redirect(url_for('admin_problem_list'))


@app.route('/admin/rejudge_submission/<int:submission_id>', methods=['POST'])
@login_required
@admin_required
def admin_rejudge_submission(submission_id):
    """重判单个提交"""
    sub = get_submission_detail(submission_id)
    if not sub:
        return render_template('error.html',
                               message='提交记录不存在',
                               user=session), 404

    reset_submission_for_rejudge(submission_id)
    update_problem_stats(sub['problem_id'])

    try:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web'))
        from bridge import judge_async
        judge_async(submission_id)
    except ImportError:
        pass

    return redirect(url_for('admin_submission_list'))


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
    page = request.args.get('page', 1, type=int)
    users, total = get_all_users(page=page)
    total_pages = max(1, (total + 19) // 20)
    return render_template('admin/users.html',
                           users=users,
                           user=session,
                           page=page, total_pages=total_pages, total=total)


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
    page = request.args.get('page', 1, type=int)
    submissions, total = get_all_submissions(page=page)
    total_pages = max(1, (total + 19) // 20)
    return render_template('admin/submissions.html',
                           submissions=submissions,
                           user=session,
                           page=page, total_pages=total_pages, total=total)


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


# ==================== API v1 ====================
from flask import Blueprint, jsonify

api_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')


def api_login_required(f):
    """API token 认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({"error": "缺少 Authorization: Bearer <token> 头"}), 401
        token = auth[7:]
        user = get_user_by_token(token)
        if not user:
            return jsonify({"error": "无效的 API Token"}), 401
        request.api_user = user
        return f(*args, **kwargs)
    return decorated


@api_bp.route('/problems')
def api_problems():
    """GET /api/v1/problems?page=1&search=&difficulty=&tag="""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    difficulty = request.args.get('difficulty', None, type=int)
    tag = request.args.get('tag', '').strip() or None

    problems, total = get_all_problems(is_admin=False, page=page,
                                        search=search, difficulty=difficulty, tag=tag)
    total_pages = max(1, (total + 19) // 20)

    return jsonify({
        "page": page,
        "per_page": 20,
        "total": total,
        "total_pages": total_pages,
        "problems": problems,
    })


@api_bp.route('/problem/<int:problem_id>')
def api_problem_detail(problem_id):
    """GET /api/v1/problem/<id>"""
    problem = get_problem_by_id(problem_id)
    if not problem or not problem['is_visible']:
        return jsonify({"error": "题目不存在"}), 404
    # 不返回敏感管理字段
    return jsonify({
        "id": problem['id'],
        "title": problem['title'],
        "description": problem['description'],
        "input_format": problem['input_format'],
        "output_format": problem['output_format'],
        "sample_input": problem['sample_input'],
        "sample_output": problem['sample_output'],
        "hint": problem['hint'],
        "source": problem['source'],
        "difficulty": problem['difficulty'],
        "time_limit": problem['time_limit'],
        "memory_limit": problem['memory_limit'],
        "tags": problem.get('tags', []),
        "accepted_count": problem['accepted_count'],
        "submission_count": problem['submission_count'],
    })


@api_bp.route('/submit', methods=['POST'])
@api_login_required
def api_submit():
    """POST /api/v1/submit  — JSON body: {problem_id, code, language}"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请求体需为 JSON"}), 400

    problem_id = data.get('problem_id')
    code = data.get('code', '')
    language = data.get('language', 'cpp')

    if not problem_id or not code.strip():
        return jsonify({"error": "problem_id 和 code 不能为空"}), 400

    problem = get_problem_by_id(int(problem_id))
    if not problem or not problem['is_visible']:
        return jsonify({"error": "题目不存在"}), 404

    submission_id = create_submission(request.api_user['id'],
                                       int(problem_id),
                                       code,
                                       language)
    # TODO: 对接评测机 judge_submission(submission_id)

    return jsonify({
        "submission_id": submission_id,
        "status": "Pending",
    }), 201


@api_bp.route('/submission/<int:submission_id>')
@api_login_required
def api_submission(submission_id):
    """GET /api/v1/submission/<id>"""
    sub = get_submission_detail(submission_id)
    if not sub:
        return jsonify({"error": "提交记录不存在"}), 404
    if sub['user_id'] != request.api_user['id'] and request.api_user['role'] != 'admin':
        return jsonify({"error": "无权查看此提交"}), 403
    return jsonify({
        "id": sub['id'],
        "problem_id": sub['problem_id'],
        "problem_title": sub['problem_title'],
        "status": sub['status'],
        "score": sub['score'],
        "time_used": sub['time_used'],
        "memory_used": sub['memory_used'],
        "language": sub['language'],
        "compiler_output": sub['compiler_output'],
        "created_at": sub['created_at'],
    })


app.register_blueprint(api_bp)


# ==================== 启动应用 ====================
if __name__ == '__main__':
    app.run(debug=True, port=5000)