import sqlite3
import secrets
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = 'judge.db'
def get_db():
    """Get a connection to the database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn

def init_db():
    """Initialize the database with the required tables."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT DEFAULT '',
            nickname TEXT DEFAULT '',
            role TEXT DEFAULT 'user',
            avatar_url TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            failed_login_attempts INTEGER DEFAULT 0,
            locked_until TIMESTAMP
        )
    ''')
    
    # Create problems table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            input_format TEXT DEFAULT '',
            output_format TEXT DEFAULT '',
            sample_input TEXT DEFAULT '',
            sample_output TEXT DEFAULT '',
            hint TEXT DEFAULT '',
            source TEXT DEFAULT '',
            difficulty INTEGER DEFAULT 1,
            time_limit INTEGER DEFAULT 1000,
            memory_limit INTEGER DEFAULT 65536,
            is_visible BOOLEAN DEFAULT 1,
            accepted_count INTEGER DEFAULT 0,
            submission_count INTEGER DEFAULT 0,
            spj_script TEXT DEFAULT '',
            use_spj BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create test_cases table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id INTEGER NOT NULL,
            case_order INTEGER DEFAULT 1,
            input TEXT NOT NULL,
            output TEXT NOT NULL,
            score INTEGER DEFAULT 10,
            is_hidden BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (problem_id) REFERENCES problems(id)
        )
    ''')

    # Create submissions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            language TEXT DEFAULT 'cpp',
            status TEXT DEFAULT 'Pending',
            score INTEGER DEFAULT 0,
            time_used INTEGER DEFAULT 0,
            memory_used INTEGER DEFAULT 0,
            compiler_output TEXT DEFAULT '',
            judge_detail TEXT DEFAULT '',
            queue_position INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (problem_id) REFERENCES problems(id)
        )
    ''')

    # Create announcements table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            is_pinned BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP      
        )
    ''')

    # Create tags table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    
    # Create problem_tags table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS problem_tags (
            problem_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (problem_id, tag_id),
            FOREIGN KEY (problem_id) REFERENCES problems(id),
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        )
    ''')

    # Create contests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            is_visible BOOLEAN DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    # Create contest_problems table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contest_problems (
            contest_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            problem_order INTEGER DEFAULT 1,
            score INTEGER DEFAULT 100,
            PRIMARY KEY (contest_id, problem_id),
            FOREIGN KEY (contest_id) REFERENCES contests(id),
            FOREIGN KEY (problem_id) REFERENCES problems(id)
        )
    ''')

    # Create contest_registrations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contest_registrations (
            contest_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (contest_id, user_id),
            FOREIGN KEY (contest_id) REFERENCES contests(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Create api_tokens table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN locked_until TIMESTAMP")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE problems ADD COLUMN spj_script TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE problems ADD COLUMN use_spj BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE submissions ADD COLUMN queue_position INTEGER")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
    print("Database Initialized Successfully.")






# Users' command
def create_user(username, password, email='', nickname=''):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return False, "用户名已存在"
    
    password_hash = generate_password_hash(password)
    cursor.execute(
        "INSERT INTO users (username, password_hash, email, nickname) VALUES (?, ?, ?, ?)",
        (username, password_hash, email, nickname if nickname else username)
    )
    conn.commit()
    conn.close()
    return True, "注册成功"


def verify_user(username, password):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,))
    user = cursor.fetchone()

    if user is None:
        conn.close()
        return False, "用户名不存在或已被禁用"
    
    # === new: 服务端二次检查锁定状态 ===
    if user['locked_until']:
        import datetime
        locked_until = datetime.datetime.fromisoformat(user['locked_until'])
        if locked_until > datetime.datetime.now():
            conn.close()
            return False, "账号已被锁定，请稍后重试"
    
    if check_password_hash(user['password_hash'], password):
        cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user['id'],))
        conn.commit()
        conn.close()
        return True, dict(user)
    else:
        conn.close()
        return False, "密码错误"
    

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

def is_account_locked(username):
    """检查账号是否在锁定期内"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT locked_until FROM users WHERE username = ?",
        (username,)
    )
    row = cursor.fetchone()
    conn.close()
    if row and row['locked_until']:
        import datetime
        locked_until = datetime.datetime.fromisoformat(row['locked_until'])
        if locked_until > datetime.datetime.now():
            wait_minutes = int((locked_until - datetime.datetime.now()).total_seconds() // 60) + 1
            return True, f"账号已被锁定，请 {wait_minutes} 分钟后重试"
    return False, ""


def record_login_failure(username):
    """记录登录失败，超过阈值自动锁定"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET failed_login_attempts = failed_login_attempts + 1 WHERE username = ?",
        (username,)
    )
    cursor.execute(
        "SELECT failed_login_attempts FROM users WHERE username = ?",
        (username,)
    )
    attempts = cursor.fetchone()
    if attempts and attempts['failed_login_attempts'] >= MAX_LOGIN_ATTEMPTS:
        import datetime
        lock_until = datetime.datetime.now() + datetime.timedelta(minutes=LOCKOUT_MINUTES)
        cursor.execute(
            "UPDATE users SET locked_until = ? WHERE username = ?",
            (lock_until.isoformat(), username)
        )
    conn.commit()
    conn.close()


def reset_login_failures(username):
    """登录成功后重新计数"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE username = ?",
        (username,)
    )
    conn.commit()
    conn.close()
    

def get_user_by_id(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


def get_user_by_username(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


def update_user_profile(user_id, nickname='', email='', avatar_url=''):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET nickname = ?, email = ?, avatar_url = ? WHERE id = ?", (nickname, email, avatar_url, user_id))
    conn.commit()
    conn.close()
    return True


def get_all_users(page=1, per_page=20):
    conn = get_db()
    cursor = conn.cursor()
    offset = (page - 1) * per_page

    cursor.execute("SELECT COUNT(*) as cnt FROM users")
    total = cursor.fetchone()['cnt']

    cursor.execute(
        "SELECT id, username, email, role, is_active, created_at, last_login FROM users ORDER BY id LIMIT ? OFFSET ?",
        (per_page, offset)
    )
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users, total


def toggle_user_active(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT is_active FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if user:
        new_status = 0 if user['is_active'] else 1
        cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
        conn.commit()
    conn.close()




# problem's command
def get_all_problems(is_admin=False, page=1, per_page=20, search='', difficulty=None, tag=None):
    """获取题目列表，支持搜索、难度筛选、标签筛选、分页"""
    conn = get_db()
    cursor = conn.cursor()
    offset = (page - 1) * per_page

    conditions = []
    params = []

    if not is_admin:
        conditions.append("p.is_visible = 1")

    if search:
        conditions.append("p.title LIKE ?")
        params.append(f"%{search}%")

    if difficulty is not None and difficulty > 0:
        conditions.append("p.difficulty = ?")
        params.append(difficulty)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # 标签筛选需要 JOIN
    if tag:
        tag_join = "JOIN problem_tags pt_filter ON p.id = pt_filter.problem_id JOIN tags t_filter ON pt_filter.tag_id = t_filter.id"
        tag_cond = " AND t_filter.name = ?"
        count_params = params + [tag]  # params for COUNT
        query_params = params + [tag]  # params for SELECT
    else:
        tag_join = ""
        tag_cond = ""
        count_params = list(params)
        query_params = list(params)

    # COUNT 查询
    count_sql = f"SELECT COUNT(DISTINCT p.id) as cnt FROM problems p {tag_join} WHERE {where_clause}{tag_cond}"
    cursor.execute(count_sql, count_params)
    total = cursor.fetchone()['cnt']

    # 数据查询
    columns = "p.id, p.title, p.difficulty, p.time_limit, p.memory_limit, p.accepted_count, p.submission_count"
    if is_admin:
        columns += ", p.is_visible"
    columns += ", p.created_at"

    data_sql = f"SELECT DISTINCT {columns} FROM problems p {tag_join} WHERE {where_clause}{tag_cond} ORDER BY p.id DESC LIMIT ? OFFSET ?"
    cursor.execute(data_sql, query_params + [per_page, offset])
    problems = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return problems, total


def get_problem_by_id(problem_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM problems WHERE id = ?", (problem_id,))
    problem = cursor.fetchone()

    if problem:
        problem = dict(problem)
        cursor.execute("SELECT t.name FROM tags t JOIN problem_tags pt ON t.id = pt.tag_id WHERE pt.problem_id = ?", (problem_id,))
        problem['tags'] = [row['name'] for row in cursor.fetchall()]
    else:
        problem = None
    
    conn.close()
    return problem


def create_problem(title, description, input_format, output_format, sample_input, sample_output, hint='', source='', difficulty=1, time_limit=1000, memory_limit=65536, use_spj=0, spj_script=''):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO problems (title, description, input_format, output_format, sample_input, sample_output, hint, source, difficulty, time_limit, memory_limit, use_spj, spj_script) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, description, input_format, output_format, sample_input, sample_output, hint, source, difficulty, time_limit, memory_limit, use_spj, spj_script)
    )
    problem_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return problem_id


def add_tag_to_problem(problem_id, tag_name):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
    cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
    tag_id = cursor.fetchone()['id']
    cursor.execute("INSERT OR IGNORE INTO problem_tags (problem_id, tag_id) VALUES (?, ?)",(problem_id, tag_id))
    
    conn.commit()
    conn.close()
    return True



def update_problem(problem_id, **kwargs):
    allowed_fields = [
        'title', 'description', 'input_format', 'output_format', 'sample_input', 'sample_output', 'hint', 'source', 'difficulty', 'time_limit', 'memory_limit', 'is_visible', 'spj_script', 'use_spj'
    ]
    updates = []
    values = []
    for key, value in kwargs.items():
        if key in allowed_fields:
            updates.append(f"{key} = ?")
            values.append(value)

    if not updates:
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(problem_id)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE problems SET {', '.join(updates)} WHERE id = ?", 
        values
    )
    conn.commit()
    conn.close()
    return True


def delete_problem(problem_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM problem_tags WHERE problem_id = ?", (problem_id,))
    cursor.execute("DELETE FROM test_cases WHERE problem_id = ?", (problem_id,))
    cursor.execute("DELETE FROM submissions WHERE problem_id = ?", (problem_id,))
    cursor.execute("DELETE FROM problems WHERE id = ?", (problem_id,))
    conn.commit()
    conn.close()


def get_problem_tags(problem_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.id, t.name FROM tags t
        JOIN problem_tags pt ON t.id = pt.tag_id
        WHERE pt.problem_id = ?
    """, (problem_id,))
    tags = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tags


def remove_tag_from_problem(problem_id, tag_name):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
    tag = cursor.fetchone()
    if tag:
        cursor.execute(
            "DELETE FROM problem_tags WHERE problem_id = ? AND tag_id = ?",
            (problem_id, tag['id'])
        )
        conn.commit()
    conn.close()


def get_all_tags():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tags ORDER BY name")
    tags = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tags


def get_user_ac_problem_ids(user_id):
    """获取某用户所有已 AC 的题目 ID 集合"""
    if not user_id:
        return set()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT problem_id FROM submissions WHERE user_id = ? AND status = 'AC'",
        (user_id,)
    )
    ac_ids = {row['problem_id'] for row in cursor.fetchall()}
    conn.close()
    return ac_ids


def get_ranking(page=1, per_page=50):
    """获取用户排行榜，按 AC 题数降序排列"""
    conn = get_db()
    cursor = conn.cursor()
    offset = (page - 1) * per_page

    cursor.execute(
        "SELECT COUNT(DISTINCT u.id) as cnt FROM users u WHERE u.is_active = 1"
    )
    total = cursor.fetchone()['cnt']

    cursor.execute("""
        SELECT
            u.id, u.username, u.nickname, u.avatar_url,
            COUNT(s.id) as submission_count,
            SUM(CASE WHEN s.status = 'AC' THEN 1 ELSE 0 END) as ac_count,
            COUNT(DISTINCT CASE WHEN s.status = 'AC' THEN s.problem_id END) as solved_count
        FROM users u
        LEFT JOIN submissions s ON u.id = s.user_id
        WHERE u.is_active = 1
        GROUP BY u.id
        ORDER BY solved_count DESC, ac_count DESC, submission_count ASC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    ranking = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return ranking, total




# Submissions' commmand
def create_submission(user_id, problem_id, code, language='cpp'):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO submissions (user_id, problem_id, code, language) 
           VALUES (?, ?, ?, ?)""",
        (user_id, problem_id, code, language)
    )
    submission_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return submission_id


def update_submission_result(submission_id, status, score=0, time_used=0, memory_used=0, compiler_output='', judge_detail=''):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE submissions SET status = ?, score = ?, time_used = ?, memory_used = ?, compiler_output = ?, judge_detail = ? WHERE id = ?",
        (status, score, time_used, memory_used, compiler_output, judge_detail, submission_id)
    )
    conn.commit()
    conn.close()


def get_submissions_by_user(user_id, page=1, per_page=20):
    conn = get_db()
    cursor = conn.cursor()
    offset = (page - 1) * per_page

    cursor.execute("SELECT COUNT(*) as cnt FROM submissions WHERE user_id = ?", (user_id,))
    total = cursor.fetchone()['cnt']

    cursor.execute(
        "SELECT s.id, s.problem_id, p.title as problem_title, s.status, s.score, s.time_used, s.memory_used, s.language, s.created_at FROM submissions s JOIN problems p ON s.problem_id = p.id WHERE s.user_id = ? ORDER BY s.created_at DESC LIMIT ? OFFSET ?",
        (user_id, per_page, offset)
    )
    submissions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return submissions, total


def get_submission_detail(submission_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, p.title as problem_title, u.username
        FROM submissions s
        JOIN problems p ON s.problem_id = p.id
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ?
    """, (submission_id,))
    submission = cursor.fetchone()
    conn.close()
    return dict(submission) if submission else None


def update_problem_stats(problem_id):
    """Atomically recompute submission_count and accepted_count for a problem.

    Wrapped in BEGIN IMMEDIATE to prevent a race where two concurrent
    judge threads read the same state, then the faster thread's UPDATE
    is overwritten by the slower thread's stale data.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("BEGIN IMMEDIATE")
    cursor.execute(
        "SELECT COUNT(*) as total FROM submissions WHERE problem_id = ?",
        (problem_id,)
    )
    total = cursor.fetchone()['total']
    cursor.execute(
        "SELECT COUNT(*) as ac FROM submissions WHERE problem_id = ? AND status = 'AC'",
        (problem_id,)
    )
    ac = cursor.fetchone()['ac']
    cursor.execute(
        "UPDATE problems SET submission_count = ?, accepted_count = ? WHERE id = ?",
        (total, ac, problem_id)
    )
    conn.commit()
    conn.close()


def get_submission_ids_by_problem(problem_id):
    """获取某个题目的所有提交 ID 列表"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM submissions WHERE problem_id = ? ORDER BY id",
        (problem_id,)
    )
    ids = [row['id'] for row in cursor.fetchall()]
    conn.close()
    return ids


def reset_submission_for_rejudge(submission_id):
    """将单个提交重置为 Pending 状态以待重判"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE submissions SET status = 'Pending', score = 0, time_used = 0, memory_used = 0, compiler_output = '', judge_detail = '' WHERE id = ?",
        (submission_id,)
    )
    conn.commit()
    conn.close()


def get_queue_position(submission_id):
    """查询某提交在 Pending 队列中的位置"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) as pos FROM submissions WHERE status = 'Pending' AND id <= ?",
        (submission_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row['pos'] if row else 0


def get_submissions_by_problem(problem_id, page=1, per_page=20):
    conn = get_db()
    cursor = conn.cursor()
    offset = (page - 1) * per_page

    cursor.execute("SELECT COUNT(*) as cnt FROM submissions WHERE problem_id = ?", (problem_id,))
    total = cursor.fetchone()['cnt']

    cursor.execute("""
        SELECT s.id, s.user_id, u.username, s.status, s.score,
               s.time_used, s.memory_used, s.language, s.created_at
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        WHERE s.problem_id = ?
        ORDER BY s.created_at DESC
        LIMIT ? OFFSET ?
    """, (problem_id, per_page, offset))
    submissions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return submissions, total


def get_all_submissions(page=1, per_page=20):
    conn = get_db()
    cursor = conn.cursor()
    offset = (page - 1) * per_page

    cursor.execute("SELECT COUNT(*) as cnt FROM submissions")
    total = cursor.fetchone()['cnt']

    cursor.execute("""
        SELECT s.id, s.user_id, u.username, s.problem_id, p.title as problem_title,
               s.status, s.score, s.time_used, s.memory_used, s.language, s.created_at
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        JOIN problems p ON s.problem_id = p.id
        ORDER BY s.created_at DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    submissions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return submissions, total




# Announcements' command
def get_announcements():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM announcements ORDER BY is_pinned DESC, created_at DESC"
    )
    announcements = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return announcements


def create_announcement(title, content, is_pinned=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO announcements (title, content, is_pinned) VALUES (?, ?, ?)",
        (title, content, is_pinned)
    )
    conn.commit()
    conn.close()


def update_announcement(announcement_id, **kwargs):
    allowed_fields = ['title', 'content', 'is_pinned']
    updates = []
    values = []
    for key, value in kwargs.items():
        if key in allowed_fields:
            updates.append(f"{key} = ?")
            values.append(value)

    if not updates:
        return False

    values.append(announcement_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE announcements SET {', '.join(updates)} WHERE id = ?",
        values
    )
    conn.commit()
    conn.close()
    return True


def delete_announcement(announcement_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
    conn.commit()
    conn.close()


# API tokens' command

def create_api_token(user_id, description=''):
    """为用户创建 API token"""
    conn = get_db()
    cursor = conn.cursor()
    token = secrets.token_hex(32)
    cursor.execute(
        "INSERT INTO api_tokens (user_id, token, description) VALUES (?, ?, ?)",
        (user_id, token, description)
    )
    conn.commit()
    conn.close()
    return token


def get_user_by_token(token):
    """通过 API token 获取用户，失败返回 None"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.* FROM users u
        JOIN api_tokens t ON u.id = t.user_id
        WHERE t.token = ? AND u.is_active = 1
    """, (token,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


def get_user_tokens(user_id):
    """获取某用户的所有 API token（不返回完整 token 字符串）"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, description, created_at FROM api_tokens WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    tokens = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tokens


def delete_api_token(token_id, user_id):
    """删除 API token"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM api_tokens WHERE id = ? AND user_id = ?",
        (token_id, user_id)
    )
    conn.commit()
    conn.close()


# Contests' command

def create_contest(title, description, start_time, end_time, created_by, is_visible=1):
    """创建比赛"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO contests (title, description, start_time, end_time, created_by, is_visible) VALUES (?, ?, ?, ?, ?, ?)",
        (title, description, start_time, end_time, created_by, is_visible)
    )
    contest_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return contest_id


def update_contest(contest_id, **kwargs):
    """更新比赛信息"""
    allowed_fields = ['title', 'description', 'start_time', 'end_time', 'is_visible']
    updates = []
    values = []
    for key, value in kwargs.items():
        if key in allowed_fields:
            updates.append(f"{key} = ?")
            values.append(value)
    if not updates:
        return False
    values.append(contest_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE contests SET {', '.join(updates)} WHERE id = ?",
        values
    )
    conn.commit()
    conn.close()
    return True


def delete_contest(contest_id):
    """删除比赛及其关联数据"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contest_registrations WHERE contest_id = ?", (contest_id,))
    cursor.execute("DELETE FROM contest_problems WHERE contest_id = ?", (contest_id,))
    cursor.execute("DELETE FROM contests WHERE id = ?", (contest_id,))
    conn.commit()
    conn.close()


def get_all_contests(include_hidden=False, page=1, per_page=20):
    """获取比赛列表"""
    conn = get_db()
    cursor = conn.cursor()
    offset = (page - 1) * per_page

    if include_hidden:
        cursor.execute("SELECT COUNT(*) as cnt FROM contests")
    else:
        cursor.execute("SELECT COUNT(*) as cnt FROM contests WHERE is_visible = 1")
    total = cursor.fetchone()['cnt']

    if include_hidden:
        cursor.execute(
            "SELECT * FROM contests ORDER BY start_time DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        )
    else:
        cursor.execute(
            "SELECT * FROM contests WHERE is_visible = 1 ORDER BY start_time DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        )
    contests = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return contests, total


def get_contest_by_id(contest_id):
    """获取比赛详情，含题目列表和参赛人数"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contests WHERE id = ?", (contest_id,))
    contest = cursor.fetchone()
    if not contest:
        conn.close()
        return None

    contest = dict(contest)

    # 关联题目
    cursor.execute("""
        SELECT p.id, p.title, p.difficulty, cp.problem_order, cp.score as contest_score
        FROM contest_problems cp
        JOIN problems p ON cp.problem_id = p.id
        WHERE cp.contest_id = ?
        ORDER BY cp.problem_order
    """, (contest_id,))
    contest['problems'] = [dict(row) for row in cursor.fetchall()]

    # 参赛人数
    cursor.execute("SELECT COUNT(*) as cnt FROM contest_registrations WHERE contest_id = ?", (contest_id,))
    contest['registrations_count'] = cursor.fetchone()['cnt']

    conn.close()
    return contest


def add_problem_to_contest(contest_id, problem_id, problem_order=1, score=100):
    """将题目加入比赛"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO contest_problems (contest_id, problem_id, problem_order, score) VALUES (?, ?, ?, ?)",
        (contest_id, problem_id, problem_order, score)
    )
    conn.commit()
    conn.close()


def remove_problem_from_contest(contest_id, problem_id):
    """从比赛中移除题目"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM contest_problems WHERE contest_id = ? AND problem_id = ?",
        (contest_id, problem_id)
    )
    conn.commit()
    conn.close()


def register_for_contest(contest_id, user_id):
    """用户注册参赛"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO contest_registrations (contest_id, user_id) VALUES (?, ?)",
            (contest_id, user_id)
        )
        conn.commit()
        conn.close()
        return True, "注册成功"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "已注册过该比赛"


def is_registered_for_contest(contest_id, user_id):
    """检查用户是否已注册比赛"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM contest_registrations WHERE contest_id = ? AND user_id = ?",
        (contest_id, user_id)
    )
    result = cursor.fetchone()
    conn.close()
    return result is not None


def get_contest_standings(contest_id):
    """
    比赛计分板：统计每个参赛用户在该比赛题目上的得分情况。
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            u.id, u.username, u.nickname,
            COUNT(DISTINCT s.id) as total_submissions,
            SUM(CASE WHEN s.status = 'AC' THEN cp.score ELSE 0 END) as total_score,
            SUM(CASE WHEN s.status = 'AC' THEN 1 ELSE 0 END) as ac_count,
            MAX(s.created_at) as last_submit_time
        FROM contest_registrations cr
        JOIN users u ON cr.user_id = u.id
        JOIN contest_problems cp ON cr.contest_id = cp.contest_id
        LEFT JOIN submissions s ON s.user_id = u.id AND s.problem_id = cp.problem_id
            AND s.created_at >= (SELECT start_time FROM contests WHERE id = ?)
            AND s.created_at <= (SELECT end_time FROM contests WHERE id = ?)
        WHERE cr.contest_id = ?
        GROUP BY u.id
        ORDER BY total_score DESC, ac_count DESC, total_submissions ASC
    """, (contest_id, contest_id, contest_id))
    standings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return standings


def get_contest_problems(contest_id):
    """获取比赛关联的题目 ID 列表"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT problem_id FROM contest_problems WHERE contest_id = ? ORDER BY problem_order",
        (contest_id,)
    )
    ids = [row['problem_id'] for row in cursor.fetchall()]
    conn.close()
    return ids


# Test_cases' command
def update_test_case(case_id, **kwargs):
    allowed_fields = ['input', 'output', 'case_order', 'score', 'is_hidden']
    updates = []
    values = []
    for key, value in kwargs.items():
        if key in allowed_fields:
            updates.append(f"{key} = ?")
            values.append(value)

    if not updates:
        return False

    values.append(case_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE test_cases SET {', '.join(updates)} WHERE id = ?",
        values
    )
    conn.commit()
    conn.close()
    return True


def delete_test_case(case_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM test_cases WHERE id = ?", (case_id,))
    conn.commit()
    conn.close()


def add_test_case(problem_id, input_data, output_data, case_order=1, score=10, is_hidden=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO test_cases (problem_id, input, output, case_order, score, is_hidden)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (problem_id, input_data, output_data, case_order, score, is_hidden)
    )
    conn.commit()
    conn.close()


def get_test_cases(problem_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM test_cases WHERE problem_id = ? ORDER BY case_order",
        (problem_id,)
    )
    cases = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return cases