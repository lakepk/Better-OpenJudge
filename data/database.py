import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = 'judge.db'
def get_db():
    """Get a connection to the database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    conn.execute("PRAGMA foreign_keys = ON")
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
            contest_id INTEGER DEFAULT NULL,
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
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            is_visible INTEGER DEFAULT 1,
            created_by INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    # Create contest_problems table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contest_problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contest_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (contest_id) REFERENCES contests(id) ON DELETE CASCADE,
            FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE,
            UNIQUE(contest_id, problem_id)
        )
    ''')

    conn.commit()
    conn.close()
    print("Database Initialized Successfully.")


def migrate_add_contest_id():
    """Add contest_id column to existing submissions table if missing."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(submissions)")
    columns = [row['name'] for row in cursor.fetchall()]
    if 'contest_id' not in columns:
        cursor.execute("ALTER TABLE submissions ADD COLUMN contest_id INTEGER DEFAULT NULL")
        conn.commit()
    conn.close()





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
    cursor.execute("DELETE FROM contest_problems WHERE problem_id = ?", (problem_id,))
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
def create_submission(user_id, problem_id, code, language='cpp', contest_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO submissions (user_id, problem_id, code, language, contest_id)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, problem_id, code, language, contest_id)
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


# ==================== Contests ====================

def create_contest(title, description, start_time, end_time, created_by, is_visible=1):
    """Create a new contest. Returns the new contest_id."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO contests (title, description, start_time, end_time, is_visible, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (title, description, start_time, end_time, is_visible, created_by)
    )
    contest_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return contest_id


def update_contest(contest_id, **kwargs):
    """Update contest fields. Allowed: title, description, start_time, end_time, is_visible."""
    allowed = ['title', 'description', 'start_time', 'end_time', 'is_visible']
    updates = []
    values = []
    for key, value in kwargs.items():
        if key in allowed:
            updates.append(f"{key} = ?")
            values.append(value)
    if not updates:
        return False
    values.append(contest_id)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE contests SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return True


def delete_contest(contest_id):
    """Delete a contest and its problem associations."""
    conn = get_db()
    cursor = conn.cursor()
    # Nullify contest_id on submissions that reference this contest
    cursor.execute("UPDATE submissions SET contest_id = NULL WHERE contest_id = ?", (contest_id,))
    cursor.execute("DELETE FROM contest_problems WHERE contest_id = ?", (contest_id,))
    cursor.execute("DELETE FROM contests WHERE id = ?", (contest_id,))
    conn.commit()
    conn.close()


def get_all_contests(is_admin=False):
    """Return all visible contests (admin sees all)."""
    conn = get_db()
    cursor = conn.cursor()
    if is_admin:
        cursor.execute(
            "SELECT c.*, u.username as creator_name "
            "FROM contests c JOIN users u ON c.created_by = u.id "
            "ORDER BY c.start_time DESC"
        )
    else:
        cursor.execute(
            "SELECT c.*, u.username as creator_name "
            "FROM contests c JOIN users u ON c.created_by = u.id "
            "WHERE c.is_visible = 1 "
            "ORDER BY c.start_time DESC"
        )
    contests = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return contests


def get_contest_by_id(contest_id):
    """Get a single contest with creator name and associated problems."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT c.*, u.username as creator_name "
        "FROM contests c JOIN users u ON c.created_by = u.id "
        "WHERE c.id = ?", (contest_id,)
    )
    contest = cursor.fetchone()
    if contest:
        contest = dict(contest)
        # Get problems in this contest
        cursor.execute(
            "SELECT p.id, p.title, p.difficulty, cp.sort_order "
            "FROM contest_problems cp "
            "JOIN problems p ON cp.problem_id = p.id "
            "WHERE cp.contest_id = ? "
            "ORDER BY cp.sort_order, cp.id",
            (contest_id,)
        )
        contest['problems'] = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return contest if contest else None


def add_problem_to_contest(contest_id, problem_id, sort_order=0):
    """Associate a problem with a contest."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO contest_problems (contest_id, problem_id, sort_order) "
        "VALUES (?, ?, ?)",
        (contest_id, problem_id, sort_order)
    )
    conn.commit()
    conn.close()


def remove_problem_from_contest(contest_id, problem_id):
    """Remove a problem from a contest."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM contest_problems WHERE contest_id = ? AND problem_id = ?",
        (contest_id, problem_id)
    )
    conn.commit()
    conn.close()


def get_contest_problems(contest_id):
    """Get all problems in a contest, ordered by sort_order."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT p.*, cp.sort_order "
        "FROM contest_problems cp "
        "JOIN problems p ON cp.problem_id = p.id "
        "WHERE cp.contest_id = ? "
        "ORDER BY cp.sort_order, cp.id",
        (contest_id,)
    )
    problems = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return problems


# ==================== Ranking ====================

def get_global_ranking(limit=50):
    """Global ranking by AC count (practice submissions only, no contest submissions)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.nickname, COUNT(DISTINCT s.problem_id) as ac_count,
               COUNT(DISTINCT s.id) as submit_count
        FROM users u
        JOIN submissions s ON u.id = s.user_id
        WHERE s.status = 'AC' AND s.contest_id IS NULL
        GROUP BY u.id
        ORDER BY ac_count DESC, u.nickname ASC
        LIMIT ?
    """, (limit,))
    ranking = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return ranking


def get_contest_ranking(contest_id):
    """ACM-ICPC style ranking for a contest.

    Sort by: AC count DESC → total penalty ASC → nickname ASC.
    Penalty = (AC_time - contest_start) + (WA/TLE count before first AC × 20 min).
    """
    conn = get_db()
    cursor = conn.cursor()

    # Get contest start time
    cursor.execute("SELECT start_time FROM contests WHERE id = ?", (contest_id,))
    contest = cursor.fetchone()
    if not contest:
        conn.close()
        return []
    start_str = contest['start_time']

    # Find all AC submissions in this contest — one per (user, problem), earliest AC
    cursor.execute("""
        SELECT s.user_id, u.nickname,
               s.problem_id, p.title as problem_title,
               s.created_at,
               s.id as submission_id
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        JOIN problems p ON s.problem_id = p.id
        WHERE s.contest_id = ? AND s.status = 'AC'
          AND NOT EXISTS (
              SELECT 1 FROM submissions earlier
              WHERE earlier.user_id = s.user_id
                AND earlier.problem_id = s.problem_id
                AND earlier.contest_id = ?
                AND earlier.status = 'AC'
                AND earlier.created_at < s.created_at
          )
        ORDER BY s.user_id, s.created_at
    """, (contest_id, contest_id))
    ac_rows = [dict(row) for row in cursor.fetchall()]

    if not ac_rows:
        conn.close()
        return []

    # Build per-user stats
    user_stats = {}
    for row in ac_rows:
        uid = row['user_id']
        if uid not in user_stats:
            user_stats[uid] = {
                'user_id': uid,
                'nickname': row['nickname'],
                'ac_count': 0,
                'total_penalty': 0,
                'problems': {}
            }
        stats = user_stats[uid]

        # Count WA/TLE before this AC for this problem
        cursor.execute("""
            SELECT COUNT(*) as wa_count FROM submissions
            WHERE user_id = ? AND problem_id = ? AND contest_id = ?
              AND status IN ('WA', 'TLE', 'RE', 'MLE')
              AND created_at < ?
        """, (uid, row['problem_id'], contest_id, row['created_at']))
        wa_info = cursor.fetchone()
        wa_count = wa_info['wa_count'] if wa_info else 0

        # Penalty minutes
        cursor.execute(
            "SELECT (strftime('%%s', ?) - strftime('%%s', ?)) / 60.0 as penalty_min",
            (row['created_at'], start_str)
        )
        time_penalty = cursor.fetchone()['penalty_min'] or 0
        total = time_penalty + wa_count * 20

        stats['ac_count'] += 1
        stats['total_penalty'] += total
        stats['problems'][row['problem_id']] = {
            'problem_title': row['problem_title'],
            'penalty': total,
            'wa_count': wa_count,
            'submission_id': row['submission_id'],
        }

    conn.close()

    # Sort: AC count DESC → penalty ASC → nickname ASC
    ranking = sorted(user_stats.values(),
                     key=lambda x: (-x['ac_count'], x['total_penalty'], x['nickname']))

    # Add rank numbers
    for i, entry in enumerate(ranking):
        entry['rank'] = i + 1

    return ranking