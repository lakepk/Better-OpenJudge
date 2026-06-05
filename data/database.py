import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = 'judge.db'
def get_db():
    """Get a connection to the database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
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
            is_active BOOLEAN DEFAULT 1
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
    
    if check_password_hash(user['password_hash'], password):
        cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user['id'],))
        conn.commit()
        conn.close()
        return True, dict(user)
    else:
        conn.close()
        return False, "密码错误"
    

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


def get_all_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, role, is_active, created_at, last_login FROM users ORDER BY id")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users


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
def get_all_problems(is_admin=False):
    conn = get_db()
    cursor = conn.cursor()
    if is_admin:
        cursor.execute("SELECT id, title, difficulty, time_limit, memory_limit, accepted_count, submission_count, is_visible, created_at FROM problems ORDER BY id DESC")
    else:
        cursor.execute("SELECT id, title, difficulty, time_limit, memory_limit, accepted_count, submission_count, created_at FROM problems WHERE is_visible = 1 ORDER BY id DESC")
    problems = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return problems


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


def create_problem(title, description, input_format, output_format, sample_input, sample_output, hint='', source='', difficulty=1, time_limit=1000, memory_limit=65536):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO problems (title, description, input_format, output_format,sample_input, sample_output, hint, source,difficulty, time_limit, memory_limit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (title, description, input_format, output_format, sample_input, sample_output, hint, source, difficulty, time_limit, memory_limit))
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
        'title', 'description', 'input_format', 'output_format', 'sample_input', 'sample_output', 'hint', 'source', 'difficulty', 'time_limit', 'memory_limit', 'is_visible'
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


def get_submissions_by_user(user_id, limit=50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT s.id, s.problem_id, p.title as problem_title, s.status, s.score, s.time_used, s.memory_used, s.language, s.created_at FROM submissions s JOIN problems p ON s.problem_id = p.id WHERE s.user_id = ? ORDER BY s.created_at DESC LIMIT ?", (user_id, limit))
    submissions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return submissions


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
    conn = get_db()
    cursor = conn.cursor()
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


def get_submissions_by_problem(problem_id, limit=50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.user_id, u.username, s.status, s.score,
               s.time_used, s.memory_used, s.language, s.created_at
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        WHERE s.problem_id = ?
        ORDER BY s.created_at DESC
        LIMIT ?
    """, (problem_id, limit))
    submissions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return submissions


def get_all_submissions(limit=100):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.user_id, u.username, s.problem_id, p.title as problem_title,
               s.status, s.score, s.time_used, s.memory_used, s.language, s.created_at
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        JOIN problems p ON s.problem_id = p.id
        ORDER BY s.created_at DESC
        LIMIT ?
    """, (limit,))
    submissions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return submissions




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