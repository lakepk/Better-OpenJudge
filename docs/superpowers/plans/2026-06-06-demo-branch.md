# Demo Branch (路演分支) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a demo-ready OJ branch with Monaco Editor IDE, contest system, ACM-penalty ranking/leaderboard, and a dashboard homepage.

**Architecture:** Extend the existing Flask + SQLite stack with 2 new DB tables (`contests`, `contest_problems`) + 1 column on `submissions`. Add 8 new routes, 6 new templates, modify 5 existing templates. Monaco Editor and highlight.js loaded via CDN — zero build-tooling required.

**Tech Stack:** Python 3.11+, Flask, SQLite, Jinja2, Monaco Editor 0.52 (CDN), highlight.js (CDN)

---

### Task 1: Database Schema — contests + contest_problems + contest_id on submissions

**Files:**
- Modify: `data/database.py:11-122` (init_db function)

- [ ] **Step 1: Add contest_id column to submissions table in init_db**

In `data/database.py`, find the `CREATE TABLE IF NOT EXISTS submissions` block (line 71-88). Add `contest_id` after the last column before the FOREIGN KEY constraints:

```python
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
```

- [ ] **Step 2: Add contests and contest_problems CREATE TABLE statements**

After the `problem_tags` table creation block (after line 118, before `conn.commit()`), add:

```python
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
```

- [ ] **Step 3: Add runtime migration for existing databases**

After the `init_db` function ends (after the `print` on line 122), add a migration helper. This adds `contest_id` to an existing `submissions` table if it was created by an older version of the code:

```python
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
```

- [ ] **Step 4: Call migration at startup**

In `data/app.py`, after `init_db()` on line 11, add:

```python
from database import migrate_add_contest_id
migrate_add_contest_id()
```

Add `migrate_add_contest_id` to the existing `from database import *` line by replacing it with explicit imports (we need to do this properly — see Task 5).

Actually, simpler: just call it after `init_db()`. We'll handle imports in Task 5.

- [ ] **Step 5: Commit**

```bash
git add data/database.py data/app.py
git commit -m "feat: add contests, contest_problems tables and contest_id on submissions"
```

---

### Task 2: database.py — Contest CRUD Functions

**Files:**
- Modify: `data/database.py` (append new functions before the final line)

- [ ] **Step 1: Add contest CRUD functions at end of database.py**

Append the following functions after the existing `get_test_cases` function (after line 570):

```python

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
    """Get a single contest with creator name."""
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
```

- [ ] **Step 2: Commit**

```bash
git add data/database.py
git commit -m "feat: add contest CRUD functions to database.py"
```

---

### Task 3: database.py — Ranking Query Functions

**Files:**
- Modify: `data/database.py` (append after contest functions)

- [ ] **Step 1: Add global ranking function**

Append after the contest functions added in Task 2:

```python

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
        # strftime('%s', ...) gives Unix timestamp in seconds; divide by 60 for minutes
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
```

- [ ] **Step 2: Commit**

```bash
git add data/database.py
git commit -m "feat: add ranking query functions (global + contest ACM-penalty)"
```

---

### Task 4: database.py modify create_submission + bridge.py update

**Files:**
- Modify: `data/database.py:353-364` (create_submission)
- Modify: `web/bridge.py:216-220` (_patched_create)

- [ ] **Step 1: Add contest_id parameter to database.create_submission**

In `data/database.py`, change `create_submission` (line 353):

```python
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
```

- [ ] **Step 2: Forward contest_id in bridge.py monkey-patch**

In `web/bridge.py`, update `_patched_create` (line 216):

```python
def _patched_create(user_id, problem_id, code, language='cpp', contest_id=None):
    """Drop-in replacement that triggers the judge after insert."""
    submission_id = _original_create(user_id, problem_id, code, language, contest_id)
    judge_async(submission_id)
    return submission_id
```

- [ ] **Step 3: Verify bridge imports still work**

The `_original_create` is captured before patching (line 213: `_original_create = db_module.create_submission`). Since `create_submission` is a function object, `_original_create` already references it correctly. The new `contest_id` parameter will be accepted because `_original_create` points to the updated function.

- [ ] **Step 4: Commit**

```bash
git add data/database.py web/bridge.py
git commit -m "feat: add contest_id parameter to create_submission flow"
```

---

### Task 5: app.py — Contest Public Routes

**Files:**
- Modify: `data/app.py` (insert new routes)

- [ ] **Step 1: Add import for contest/ranking DB functions**

At the top of `data/app.py`, the current import is `from database import *`. Since we added new functions to database.py, they're automatically available. But we also need to import `migrate_add_contest_id` if we added it in Task 1 Step 3.

Update line 5 to ensure `migrate_add_contest_id` is importable (already covered by `from database import *` since it's defined in that module).

- [ ] **Step 2: Add contest list route**

Insert after the existing problem routes (before line 217 `# 提交记录`):

```python
# ==================== 比赛系统 ====================
@app.route('/contests')
def contest_list():
    is_admin = session.get('role') == 'admin'
    contests = get_all_contests(is_admin=is_admin)
    return render_template('contests.html',
                           contests=contests,
                           user=session)


@app.route('/contest/<int:contest_id>')
def contest_detail(contest_id):
    contest = get_contest_by_id(contest_id)

    if not contest:
        return render_template('error.html',
                               message='比赛不存在',
                               user=session), 404

    if not contest['is_visible'] and session.get('role') != 'admin':
        return render_template('error.html',
                               message='比赛不存在',
                               user=session), 404

    # Check if contest is ongoing or ended (for showing ranking)
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    is_ongoing = contest['start_time'] <= now <= contest['end_time']
    is_ended = now > contest['end_time']

    # Get compact ranking (top 10 users)
    ranking = get_contest_ranking(contest_id)[:10] if is_ongoing or is_ended else []

    return render_template('contest_detail.html',
                           contest=contest,
                           is_ongoing=is_ongoing,
                           is_ended=is_ended,
                           ranking=ranking,
                           user=session)


@app.route('/contest/<int:contest_id>/ranking')
def contest_ranking(contest_id):
    contest = get_contest_by_id(contest_id)

    if not contest:
        return render_template('error.html',
                               message='比赛不存在',
                               user=session), 404

    ranking = get_contest_ranking(contest_id)

    return render_template('contest_ranking.html',
                           contest=contest,
                           ranking=ranking,
                           user=session)
```

- [ ] **Step 3: Commit**

```bash
git add data/app.py
git commit -m "feat: add public contest routes (list, detail, ranking)"
```

---

### Task 6: app.py — Admin Contest Routes

**Files:**
- Modify: `data/app.py` (insert after existing admin routes)

- [ ] **Step 1: Add admin contest management routes**

Insert before the `# 启动应用` section (before line 482):

```python
# ==================== 管理员 - 比赛管理 ====================
@app.route('/admin/contests')
@login_required
@admin_required
def admin_contest_list():
    contests = get_all_contests(is_admin=True)
    return render_template('admin/contests.html',
                           contests=contests,
                           user=session)


@app.route('/admin/create_contest', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_contest():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '')
        start_time = request.form.get('start_time', '')
        end_time = request.form.get('end_time', '')
        is_visible = int(request.form.get('is_visible', 1))
        problem_ids = request.form.get('problem_ids', '')  # comma-separated

        if not title or not start_time or not end_time:
            return render_template('admin/create_contest.html',
                                   error='标题、开始时间和结束时间不能为空',
                                   user=session)

        contest_id = create_contest(title=title,
                                     description=description,
                                     start_time=start_time,
                                     end_time=end_time,
                                     created_by=session['user_id'],
                                     is_visible=is_visible)

        # Associate problems
        if problem_ids:
            for pid_str in problem_ids.split(','):
                pid = pid_str.strip()
                if pid.isdigit():
                    add_problem_to_contest(contest_id, int(pid))

        return redirect(url_for('contest_detail', contest_id=contest_id))

    # GET: show empty form
    problems = get_all_problems(is_admin=True)
    return render_template('admin/create_contest.html',
                           problems=problems,
                           user=session)


@app.route('/admin/edit_contest/<int:contest_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_contest(contest_id):
    contest = get_contest_by_id(contest_id)
    if not contest:
        return render_template('error.html',
                               message='比赛不存在',
                               user=session), 404

    if request.method == 'POST':
        update_data = {
            'title': request.form.get('title', '').strip(),
            'description': request.form.get('description', ''),
            'start_time': request.form.get('start_time', ''),
            'end_time': request.form.get('end_time', ''),
            'is_visible': int(request.form.get('is_visible', 1))
        }
        update_contest(contest_id, **update_data)

        # Rebuild problem associations
        problem_ids = request.form.get('problem_ids', '')
        # Remove all existing
        for p in contest.get('problems', []):
            remove_problem_from_contest(contest_id, p['id'])
        # Add new ones
        if problem_ids:
            for pid_str in problem_ids.split(','):
                pid = pid_str.strip()
                if pid.isdigit():
                    add_problem_to_contest(contest_id, int(pid))

        return redirect(url_for('contest_detail', contest_id=contest_id))

    problems = get_all_problems(is_admin=True)
    return render_template('admin/create_contest.html',
                           contest=contest,
                           problems=problems,
                           user=session)


@app.route('/admin/delete_contest/<int:contest_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_contest(contest_id):
    delete_contest(contest_id)
    return redirect(url_for('admin_contest_list'))
```

- [ ] **Step 2: Commit**

```bash
git add data/app.py
git commit -m "feat: add admin contest CRUD routes"
```

---

### Task 7: app.py — Global Ranking Route + Modify Existing Routes

**Files:**
- Modify: `data/app.py`

- [ ] **Step 1: Add global ranking route**

Insert after the contest routes added in Task 5:

```python
@app.route('/ranking')
def global_ranking():
    ranking = get_global_ranking(limit=50)
    return render_template('ranking.html',
                           ranking=ranking,
                           user=session)
```

- [ ] **Step 2: Modify submit_code route to accept contest_id**

In `data/app.py`, modify the `submit_code` function (line 175-213). Change the POST handler to read `contest_id` from the form, and change the GET handler to read it from query params:

```python
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

    # Read contest_id from query param (GET) or form (POST)
    contest_id = request.args.get('contest_id') or request.form.get('contest_id')
    if contest_id:
        contest_id = int(contest_id)
    else:
        contest_id = None

    # If submitting within a contest, verify contest is ongoing
    if contest_id:
        contest = get_contest_by_id(contest_id)
        if not contest:
            return render_template('error.html',
                                   message='比赛不存在',
                                   user=session), 404
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        if not (contest['start_time'] <= now <= contest['end_time']):
            return render_template('error.html',
                                   message='比赛未开始或已结束，无法提交',
                                   user=session), 403

    if request.method == 'POST':
        code = request.form.get('code', '')
        language = request.form.get('language', 'cpp')

        if not code.strip():
            return render_template('submit.html',
                                   problem=problem,
                                   contest_id=contest_id,
                                   contest=contest if contest_id else None,
                                   user=session,
                                   error='代码不能为空')

        submission_id = create_submission(session['user_id'],
                                          problem_id,
                                          code,
                                          language,
                                          contest_id=contest_id)

        return redirect(url_for('submission_detail',
                                submission_id=submission_id))

    return render_template('submit.html',
                           problem=problem,
                           contest_id=contest_id,
                           contest=contest if contest_id else None,
                           user=session)
```

- [ ] **Step 3: Modify submission_detail route — contest visibility control**

In the `submission_detail` function (line 227-245), add contest visibility check after the existing permission check:

```python
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

    # 比赛中提交：比赛进行中时，仅提交者本人和管理员可查看
    if submission.get('contest_id'):
        contest = get_contest_by_id(submission['contest_id'])
        if contest:
            from datetime import datetime
            now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            is_ongoing = contest['start_time'] <= now <= contest['end_time']
            if is_ongoing and submission['user_id'] != session['user_id'] and session.get('role') != 'admin':
                return render_template('error.html',
                                       message='比赛进行中，暂不可查看他人提交',
                                       user=session), 403

    return render_template('submission_detail.html',
                           submission=submission,
                           user=session)
```

- [ ] **Step 4: Modify problem_detail route — contest-aware**

Update the `problem_detail` function (line 156-172) to accept an optional `contest_id` query parameter, and pass it to the template:

```python
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

    contest_id = request.args.get('contest_id')
    return render_template('problem_detail.html',
                           problem=problem,
                           contest_id=contest_id,
                           user=session)
```

- [ ] **Step 5: Update index route — include ranking snippet for homepage**

Modify the `index` function (line 36-43) to also fetch ranking data:

```python
@app.route('/')
def index():
    announcements = get_announcements()
    problems = get_all_problems(is_admin=(session.get('role') == 'admin'))
    top_users = get_global_ranking(limit=5)
    return render_template('index.html',
                           user=session,
                           problems=problems,
                           announcements=announcements,
                           top_users=top_users)
```

- [ ] **Step 6: Commit**

```bash
git add data/app.py
git commit -m "feat: add ranking route, contest-aware submit/problem-detail/submission-detail, homepage ranking"
```

---

### Task 8: Templates — base.html Nav Update + index.html Dashboard

**Files:**
- Modify: `data/templates/base.html`
- Modify: `data/templates/index.html`

- [ ] **Step 1: Add "比赛" and "排行榜" links to navigation**

In `data/templates/base.html`, update the nav links section (lines 149-157):

```html
        <div class="links">
            <a href="/problems">题目</a>
            <a href="/contests">比赛</a>
            <a href="/ranking">排行榜</a>
            {% if user and user.user_id %}
                <a href="/submissions">我的提交</a>
            {% endif %}
            {% if user and user.role == 'admin' %}
                <a href="/admin/problems">管理</a>
            {% endif %}
        </div>
```

- [ ] **Step 2: Redesign index.html with dashboard cards**

Replace `data/templates/index.html` entirely:

```html
{% extends "base.html" %}
{% block title %}首页 - LiteJudge{% endblock %}
{% block content %}

{% if announcements %}
<div class="card" style="background: #fffbe6; border-left: 4px solid #f39c12;">
    <h3>📢 公告</h3>
    {% for a in announcements %}
    <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #f0e4a8;">
        <strong>{{ a.title }}</strong>
        <p class="text-muted">{{ a.content }}</p>
    </div>
    {% endfor %}
</div>
{% endif %}

<!-- 功能入口面板 -->
<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px;">
    <a href="/problems" class="dashboard-card">
        <div class="dashboard-card-icon">📝</div>
        <div class="dashboard-card-title">题库</div>
        <div class="dashboard-card-desc">浏览所有题目</div>
    </a>
    <a href="/contests" class="dashboard-card">
        <div class="dashboard-card-icon">🏆</div>
        <div class="dashboard-card-title">比赛</div>
        <div class="dashboard-card-desc">参与限时竞赛</div>
    </a>
    <a href="/ranking" class="dashboard-card">
        <div class="dashboard-card-icon">🏅</div>
        <div class="dashboard-card-title">排行榜</div>
        <div class="dashboard-card-desc">全站 AC 排名</div>
    </a>
    {% if user and user.user_id %}
    <a href="/profile" class="dashboard-card">
        <div class="dashboard-card-icon">👤</div>
        <div class="dashboard-card-title">个人中心</div>
        <div class="dashboard-card-desc">我的提交与资料</div>
    </a>
    {% else %}
    <a href="/login" class="dashboard-card">
        <div class="dashboard-card-icon">🔑</div>
        <div class="dashboard-card-title">登录</div>
        <div class="dashboard-card-desc">登录以提交代码</div>
    </a>
    {% endif %}
</div>

<!-- 管理员面板 -->
{% if user and user.role == 'admin' %}
<div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 20px;">
    <a href="/admin/problems" class="dashboard-card dashboard-card-admin">
        <div class="dashboard-card-icon">📋</div>
        <div class="dashboard-card-title">题目管理</div>
        <div class="dashboard-card-desc">创建/编辑题目</div>
    </a>
    <a href="/admin/users" class="dashboard-card dashboard-card-admin">
        <div class="dashboard-card-icon">👥</div>
        <div class="dashboard-card-title">用户管理</div>
        <div class="dashboard-card-desc">查看/禁用用户</div>
    </a>
    <a href="/admin/announcements" class="dashboard-card dashboard-card-admin">
        <div class="dashboard-card-icon">📢</div>
        <div class="dashboard-card-title">公告管理</div>
        <div class="dashboard-card-desc">发布首页公告</div>
    </a>
    <a href="/admin/contests" class="dashboard-card dashboard-card-admin">
        <div class="dashboard-card-icon">🏗</div>
        <div class="dashboard-card-title">比赛管理</div>
        <div class="dashboard-card-desc">创建/管理比赛</div>
    </a>
    <a href="/admin/submissions" class="dashboard-card dashboard-card-admin">
        <div class="dashboard-card-icon">📊</div>
        <div class="dashboard-card-title">提交总览</div>
        <div class="dashboard-card-desc">所有用户提交</div>
    </a>
</div>
{% endif %}

<!-- 排行榜速览 -->
{% if top_users %}
<div class="card">
    <div class="flex-between mb-20">
        <h2>🏅 排行榜 TOP 5</h2>
        <a href="/ranking" class="btn btn-secondary btn-sm">查看完整排行 →</a>
    </div>
    <table>
        <thead>
            <tr>
                <th>排名</th>
                <th>用户</th>
                <th>AC 数量</th>
                <th>提交次数</th>
            </tr>
        </thead>
        <tbody>
            {% for u in top_users %}
            <tr>
                <td><strong>#{{ loop.index }}</strong></td>
                <td>{{ u.nickname }}</td>
                <td><span style="color: #27ae60; font-weight: bold;">{{ u.ac_count }}</span></td>
                <td>{{ u.submit_count }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endif %}

<!-- 题目列表 -->
<div class="card">
    <h2>题目列表</h2>
    {% if problems %}
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>标题</th>
                <th>难度</th>
                <th>时间限制</th>
                <th>内存限制</th>
                <th>通过率</th>
            </tr>
        </thead>
        <tbody>
            {% for p in problems %}
            <tr>
                <td>{{ p.id }}</td>
                <td>
                    <a href="/problem/{{ p.id }}">{{ p.title }}</a>
                    {% if not p.is_visible %}<span class="text-muted">[隐藏]</span>{% endif %}
                </td>
                <td>
                    <span class="difficulty 
                        {% if p.difficulty == 1 %}difficulty-easy
                        {% elif p.difficulty == 2 %}difficulty-medium
                        {% else %}difficulty-hard{% endif %}">
                        {{ '★' * p.difficulty }}{{ '☆' * (3 - p.difficulty) }}
                    </span>
                </td>
                <td>{{ p.time_limit }}ms</td>
                <td>{{ (p.memory_limit / 1024) | round(1) }}MB</td>
                <td>
                    {% if p.submission_count > 0 %}
                        {{ ((p.accepted_count / p.submission_count) * 100) | round(1) }}%
                    {% else %}0%{% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p class="text-muted text-center" style="padding: 40px;">暂无题目</p>
    {% endif %}
</div>

<style>
    .dashboard-card {
        display: block;
        background: white;
        border-radius: 8px;
        padding: 24px 16px;
        text-align: center;
        text-decoration: none;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        transition: transform 0.15s, box-shadow 0.15s;
        color: #333;
    }
    .dashboard-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }
    .dashboard-card-icon {
        font-size: 32px;
        margin-bottom: 8px;
    }
    .dashboard-card-title {
        font-weight: 600;
        font-size: 15px;
        margin-bottom: 4px;
        color: #1a1a2e;
    }
    .dashboard-card-desc {
        font-size: 12px;
        color: #888;
    }
    .dashboard-card-admin {
        border-top: 3px solid #e94560;
    }
    @media (max-width: 700px) {
        .dashboard-card-container {
            grid-template-columns: repeat(2, 1fr) !important;
        }
    }
</style>

{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add data/templates/base.html data/templates/index.html
git commit -m "feat: add nav links, homepage dashboard cards with admin panel"
```

---

### Task 9: Templates — Contest Pages (contests.html, contest_detail.html, contest_ranking.html)

**Files:**
- Create: `data/templates/contests.html`
- Create: `data/templates/contest_detail.html`
- Create: `data/templates/contest_ranking.html`

- [ ] **Step 1: Create contests.html — contest list with status badges**

```html
{% extends "base.html" %}
{% block title %}比赛列表 - LiteJudge{% endblock %}
{% block content %}

<div class="card">
    <h2>🏆 比赛列表</h2>

    {% if contests %}
    <div style="display: grid; gap: 16px; margin-top: 16px;">
        {% for c in contests %}
        <a href="/contest/{{ c.id }}" style="display: block; background: #fafafa; border-radius: 8px; padding: 20px; text-decoration: none; color: #333; border: 1px solid #eee; transition: box-shadow 0.15s;">
            <div class="flex-between" style="align-items: flex-start;">
                <div>
                    <strong style="font-size: 18px; color: #1a1a2e;">{{ c.title }}</strong>
                    {% if not c.is_visible %}<span class="text-muted">[隐藏]</span>{% endif %}
                    <p class="text-muted" style="margin-top: 6px;">
                        {{ c.description[:100] }}{% if c.description|length > 100 %}...{% endif %}
                    </p>
                </div>
                <div style="text-align: right; flex-shrink: 0; margin-left: 16px;">
                    {% set now = now if now else '' %}
                    {% if c.start_time > now %}
                        <span style="display: inline-block; background: #e2e3e5; color: #383d41; padding: 4px 12px; border-radius: 12px; font-size: 13px;">未开始</span>
                    {% elif c.end_time < now %}
                        <span style="display: inline-block; background: #d4edda; color: #155724; padding: 4px 12px; border-radius: 12px; font-size: 13px;">已结束</span>
                    {% else %}
                        <span style="display: inline-block; background: #fff3cd; color: #856404; padding: 4px 12px; border-radius: 12px; font-size: 13px;">进行中</span>
                    {% endif %}
                    <p class="text-muted" style="margin-top: 8px; font-size: 12px;">
                        开始: {{ c.start_time[:16] }}<br>
                        结束: {{ c.end_time[:16] }}
                    </p>
                </div>
            </div>
        </a>
        {% endfor %}
    </div>
    {% else %}
    <p class="text-muted text-center" style="padding: 40px;">暂无比赛</p>
    {% endif %}
</div>

{% endblock %}
```

Wait — Jinja2 doesn't have a `now` variable by default. I need to handle the time comparison in Python (in app.py) and pass `is_ongoing`/`is_ended` to the template for each contest. Let me update the approach: in `contest_list` route, compute status for each contest before passing to template.

Actually, let me update the `contest_list` route (Task 5 Step 2) to add status flags. I'll handle this in the template more carefully.

Better approach: pass `now` from the route. Let me update the route:

In `data/app.py`, the `contest_list` route should compute status for each contest:

```python
@app.route('/contests')
def contest_list():
    is_admin = session.get('role') == 'admin'
    contests = get_all_contests(is_admin=is_admin)
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    for c in contests:
        if c['start_time'] > now:
            c['status'] = 'upcoming'
        elif c['end_time'] < now:
            c['status'] = 'ended'
        else:
            c['status'] = 'ongoing'
    return render_template('contests.html',
                           contests=contests,
                           user=session)
```

OK let me rewrite these template tasks more carefully. I'll just write the final version directly.

- [ ] **Step 1: Create contests.html**

```html
{% extends "base.html" %}
{% block title %}比赛列表 - LiteJudge{% endblock %}
{% block content %}

<div class="card">
    <h2>🏆 比赛列表</h2>

    {% if contests %}
    <div style="display: grid; gap: 12px; margin-top: 12px;">
        {% for c in contests %}
        <a href="/contest/{{ c.id }}" style="display: block; background: #fafafa; border-radius: 8px; padding: 20px; text-decoration: none; color: #333; border: 1px solid #eee; transition: box-shadow 0.15s;">
            <div class="flex-between" style="align-items: flex-start;">
                <div style="flex: 1;">
                    <strong style="font-size: 18px; color: #1a1a2e;">{{ c.title }}</strong>
                    {% if not c.is_visible %}<span class="text-muted">[隐藏]</span>{% endif %}
                    {% if c.description %}
                    <p class="text-muted" style="margin-top: 4px;">{{ c.description[:120] }}{% if c.description|length > 120 %}...{% endif %}</p>
                    {% endif %}
                </div>
                <div style="text-align: right; flex-shrink: 0; margin-left: 16px;">
                    {% if c.status == 'upcoming' %}
                        <span style="display: inline-block; background: #e2e3e5; color: #383d41; padding: 4px 12px; border-radius: 12px; font-size: 13px;">未开始</span>
                    {% elif c.status == 'ended' %}
                        <span style="display: inline-block; background: #d4edda; color: #155724; padding: 4px 12px; border-radius: 12px; font-size: 13px;">已结束</span>
                    {% else %}
                        <span style="display: inline-block; background: #fff3cd; color: #856404; padding: 4px 12px; border-radius: 12px; font-size: 13px;">进行中</span>
                    {% endif %}
                    <p class="text-muted" style="margin-top: 8px; font-size: 12px;">
                        {{ c.start_time[:16] }} ~ {{ c.end_time[:16] }}
                    </p>
                    <p class="text-muted" style="font-size: 11px;">创建者: {{ c.creator_name }}</p>
                </div>
            </div>
        </a>
        {% endfor %}
    </div>
    {% else %}
    <p class="text-muted text-center" style="padding: 40px;">暂无比赛</p>
    {% endif %}
</div>

{% endblock %}
```

- [ ] **Step 2: Create contest_detail.html**

```html
{% extends "base.html" %}
{% block title %}{{ contest.title }} - 比赛详情 - LiteJudge{% endblock %}
{% block content %}

<div class="card">
    <div class="flex-between mb-20">
        <h2>🏆 {{ contest.title }}</h2>
        <div>
            {% if is_ongoing %}
                <span style="display: inline-block; background: #fff3cd; color: #856404; padding: 6px 16px; border-radius: 12px; font-size: 14px; font-weight: 600;">● 进行中</span>
            {% elif is_ended %}
                <span style="display: inline-block; background: #d4edda; color: #155724; padding: 6px 16px; border-radius: 12px; font-size: 14px; font-weight: 600;">✓ 已结束</span>
            {% else %}
                <span style="display: inline-block; background: #e2e3e5; color: #383d41; padding: 6px 16px; border-radius: 12px; font-size: 14px; font-weight: 600;">○ 未开始</span>
            {% endif %}
        </div>
    </div>

    <p class="text-muted mb-20">
        比赛时间: {{ contest.start_time[:16] }} ~ {{ contest.end_time[:16] }}
        &nbsp;|&nbsp; 创建者: {{ contest.creator_name }}
    </p>

    {% if contest.description %}
    <div class="mb-20" style="line-height: 1.8;">
        {{ contest.description }}
    </div>
    {% endif %}

    {% if user and user.role == 'admin' %}
    <div class="mb-20">
        <a href="/admin/edit_contest/{{ contest.id }}" class="btn btn-secondary btn-sm">编辑比赛</a>
        <form method="post" action="/admin/delete_contest/{{ contest.id }}" style="display:inline;" onsubmit="confirmDelete(this); return false;">
            <button type="submit" class="btn btn-danger btn-sm">删除比赛</button>
        </form>
    </div>
    {% endif %}
</div>

<!-- 题目列表 -->
<div class="card">
    <h3>📝 比赛题目</h3>
    {% if contest.problems %}
    <table class="mt-20">
        <thead>
            <tr>
                <th>#</th>
                <th>标题</th>
                <th>难度</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody>
            {% for p in contest.problems %}
            <tr>
                <td>{{ loop.index }}</td>
                <td>
                    <a href="/problem/{{ p.id }}?contest_id={{ contest.id }}">{{ p.title }}</a>
                </td>
                <td>
                    <span class="difficulty
                        {% if p.difficulty == 1 %}difficulty-easy
                        {% elif p.difficulty == 2 %}difficulty-medium
                        {% else %}difficulty-hard{% endif %}">
                        {{ '★' * p.difficulty }}{{ '☆' * (3 - p.difficulty) }}
                    </span>
                </td>
                <td>
                    {% if is_ongoing and user and user.user_id %}
                        <a href="/problem/{{ p.id }}/submit?contest_id={{ contest.id }}" class="btn btn-primary btn-sm">提交</a>
                    {% elif not user or not user.user_id %}
                        <a href="/login" class="btn btn-secondary btn-sm">登录后提交</a>
                    {% else %}
                        <span class="text-muted">—</span>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p class="text-muted text-center" style="padding: 30px;">暂无题目</p>
    {% endif %}
</div>

<!-- 排行榜速览 -->
{% if ranking %}
<div class="card">
    <div class="flex-between mb-20">
        <h3>🏅 排行榜</h3>
        <a href="/contest/{{ contest.id }}/ranking" class="btn btn-secondary btn-sm">查看完整排行 →</a>
    </div>
    <table>
        <thead>
            <tr>
                <th>排名</th>
                <th>用户</th>
                <th>AC 数</th>
                <th>罚时(分)</th>
            </tr>
        </thead>
        <tbody>
            {% for u in ranking %}
            <tr>
                <td><strong>#{{ u.rank }}</strong></td>
                <td>{{ u.nickname }}</td>
                <td><span style="color: #27ae60; font-weight: bold;">{{ u.ac_count }}</span></td>
                <td>{{ (u.total_penalty or 0) | round(1) }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 3: Create contest_ranking.html — full contest leaderboard**

```html
{% extends "base.html" %}
{% block title %}{{ contest.title }} - 排行榜 - LiteJudge{% endblock %}
{% block content %}

<div class="card">
    <div class="flex-between mb-20">
        <h2>🏅 {{ contest.title }} — 排行榜</h2>
        <a href="/contest/{{ contest.id }}" class="btn btn-secondary btn-sm">← 返回比赛</a>
    </div>

    <p class="text-muted mb-20">
        规则: ACM-ICPC 赛制 — 按 AC 数降序排列，罚时 = 解题时间 + WA/TLE 次数 × 20 分钟
    </p>

    {% if ranking %}
    <table>
        <thead>
            <tr>
                <th>排名</th>
                <th>用户</th>
                <th>AC 数</th>
                <th>罚时(分)</th>
            </tr>
        </thead>
        <tbody>
            {% for u in ranking %}
            <tr>
                <td>
                    {% if u.rank == 1 %}🥇
                    {% elif u.rank == 2 %}🥈
                    {% elif u.rank == 3 %}🥉
                    {% else %}#{{ u.rank }}{% endif %}
                </td>
                <td><strong>{{ u.nickname }}</strong></td>
                <td><span style="color: #27ae60; font-weight: bold;">{{ u.ac_count }}</span></td>
                <td>{{ (u.total_penalty or 0) | round(1) }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p class="text-muted text-center" style="padding: 40px;">暂无排行数据</p>
    {% endif %}
</div>

{% endblock %}
```

- [ ] **Step 4: Commit**

```bash
git add data/templates/contests.html data/templates/contest_detail.html data/templates/contest_ranking.html
git commit -m "feat: add contest list, detail, and ranking templates"
```

---

### Task 10: Templates — Global Ranking + Admin Contest Pages

**Files:**
- Create: `data/templates/ranking.html`
- Create: `data/templates/admin/contests.html`
- Create: `data/templates/admin/create_contest.html`

- [ ] **Step 1: Create ranking.html — global leaderboard**

```html
{% extends "base.html" %}
{% block title %}排行榜 - LiteJudge{% endblock %}
{% block content %}

<div class="card">
    <h2>🏅 全站排行榜</h2>
    <p class="text-muted mb-20">统计所有练习提交的 AC 数量（不含比赛提交）</p>

    {% if ranking %}
    <table>
        <thead>
            <tr>
                <th>排名</th>
                <th>用户</th>
                <th>AC 数</th>
                <th>提交次数</th>
            </tr>
        </thead>
        <tbody>
            {% for u in ranking %}
            <tr>
                <td>
                    {% if loop.index == 1 %}🥇
                    {% elif loop.index == 2 %}🥈
                    {% elif loop.index == 3 %}🥉
                    {% else %}#{{ loop.index }}{% endif %}
                </td>
                <td><strong>{{ u.nickname }}</strong></td>
                <td><span style="color: #27ae60; font-weight: bold;">{{ u.ac_count }}</span></td>
                <td>{{ u.submit_count }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p class="text-muted text-center" style="padding: 40px;">暂无排行数据，快去刷题吧！</p>
    {% endif %}
</div>

{% endblock %}
```

- [ ] **Step 2: Create admin/contests.html — admin contest management list**

```html
{% extends "base.html" %}
{% block title %}比赛管理 - LiteJudge{% endblock %}
{% block content %}

<div class="card">
    <div class="flex-between mb-20">
        <h2>🏗 比赛管理</h2>
        <a href="/admin/create_contest" class="btn btn-primary">创建比赛</a>
    </div>

    {% if contests %}
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>标题</th>
                <th>开始时间</th>
                <th>结束时间</th>
                <th>可见</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody>
            {% for c in contests %}
            <tr>
                <td>{{ c.id }}</td>
                <td><a href="/contest/{{ c.id }}">{{ c.title }}</a></td>
                <td>{{ c.start_time[:16] }}</td>
                <td>{{ c.end_time[:16] }}</td>
                <td>{{ '是' if c.is_visible else '否' }}</td>
                <td>
                    <a href="/admin/edit_contest/{{ c.id }}" class="btn btn-secondary btn-sm">编辑</a>
                    <form method="post" action="/admin/delete_contest/{{ c.id }}" style="display:inline;" onsubmit="confirmDelete(this); return false;">
                        <button type="submit" class="btn btn-danger btn-sm">删除</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p class="text-muted text-center" style="padding: 40px;">暂无比赛</p>
    {% endif %}
</div>

{% endblock %}
```

- [ ] **Step 3: Create admin/create_contest.html — create/edit contest form**

```html
{% extends "base.html" %}
{% block title %}{% if contest %}编辑比赛{% else %}创建比赛{% endif %} - LiteJudge{% endblock %}
{% block content %}

<div class="card">
    <h2>{% if contest %}编辑比赛{% else %}🏗 创建比赛{% endif %}</h2>

    {% if error %}<div class="alert alert-error">{{ error }}</div>{% endif %}

    <form method="post">
        <div class="form-group">
            <label>比赛标题</label>
            <input type="text" name="title" value="{{ contest.title if contest else '' }}" required>
        </div>

        <div class="form-group">
            <label>比赛描述</label>
            <textarea name="description" rows="4">{{ contest.description if contest else '' }}</textarea>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
            <div class="form-group">
                <label>开始时间</label>
                <input type="datetime-local" name="start_time"
                       value="{{ contest.start_time[:16] if contest else '' }}" required>
                <span class="text-muted">格式: YYYY-MM-DD HH:MM</span>
            </div>
            <div class="form-group">
                <label>结束时间</label>
                <input type="datetime-local" name="end_time"
                       value="{{ contest.end_time[:16] if contest else '' }}" required>
            </div>
        </div>

        <div class="form-group">
            <label>可见性</label>
            <select name="is_visible">
                <option value="1" {% if not contest or contest.is_visible %}selected{% endif %}>可见</option>
                <option value="0" {% if contest and not contest.is_visible %}selected{% endif %}>隐藏</option>
            </select>
        </div>

        <div class="form-group">
            <label>题目列表（用英文逗号分隔的题目 ID）</label>
            <input type="text" name="problem_ids" placeholder="例如: 1,2,3,5"
                   value="{% if contest %}{% for p in contest.problems %}{{ p.id }}{% if not loop.last %},{% endif %}{% endfor %}{% endif %}">
            <span class="text-muted">输入题目 ID，用逗号分隔</span>
        </div>

        {% if problems %}
        <div class="form-group" style="background: #fafafa; padding: 12px; border-radius: 6px;">
            <label>现有题目参考：</label>
            <div style="font-size: 13px; color: #666;">
                {% for p in problems %}
                    <span style="display: inline-block; margin: 2px;">#{{ p.id }}-{{ p.title }}{% if not loop.last %},{% endif %}</span>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <div class="mt-20">
            <button type="submit" class="btn btn-primary">
                {% if contest %}保存修改{% else %}创建比赛{% endif %}
            </button>
            <a href="/admin/contests" class="btn btn-secondary">返回</a>
        </div>
    </form>
</div>

{% endblock %}
```

- [ ] **Step 4: Commit**

```bash
git add data/templates/ranking.html data/templates/admin/contests.html data/templates/admin/create_contest.html
git commit -m "feat: add global ranking template and admin contest management templates"
```

---

### Task 11: Templates — Monaco Editor in submit.html

**Files:**
- Modify: `data/templates/submit.html`

- [ ] **Step 1: Rewrite submit.html with Monaco Editor**

Replace the entire content of `data/templates/submit.html`:

```html
{% extends "base.html" %}
{% block title %}提交代码 - {{ problem.title }} - LiteJudge{% endblock %}
{% block content %}

{% if contest %}
<div class="card" style="background: #fffbe6; border-left: 4px solid #f39c12;">
    <strong>🏆 比赛模式</strong> — {{ contest.title }}
    <span class="text-muted" style="margin-left: 8px;">
        比赛结束后提交将不再计入成绩
    </span>
    <a href="/contest/{{ contest.id }}" style="float: right; font-size: 13px;">← 返回比赛</a>
</div>
{% endif %}

<div class="card">
    <h2>提交代码: {{ problem.title }}</h2>

    <p class="text-muted mb-20">
        时间限制: {{ problem.time_limit }}ms |
        内存限制: {{ (problem.memory_limit / 1024) | round(1) }}MB
    </p>

    {% if error %}<div class="alert alert-error">{{ error }}</div>{% endif %}

    <form method="post" id="submit-form">
        {% if contest_id %}
        <input type="hidden" name="contest_id" value="{{ contest_id }}">
        {% endif %}

        <div class="form-group">
            <label>编程语言</label>
            <select name="language" id="language-select">
                <option value="cpp">C++</option>
                <option value="python">Python</option>
            </select>
        </div>

        <div class="form-group">
            <label>代码</label>
            <div id="editor-container" style="height: 450px; border: 1px solid #333; border-radius: 6px;"></div>
            <textarea name="code" id="code-textarea" style="display: none;"></textarea>
        </div>

        <button type="submit" class="btn btn-primary" onclick="syncCode()">提交评测</button>
        {% if contest_id %}
            <a href="/contest/{{ contest_id }}" class="btn btn-secondary">返回比赛</a>
        {% else %}
            <a href="/problem/{{ problem.id }}" class="btn btn-secondary">返回题目</a>
        {% endif %}
    </form>
</div>

<!-- Monaco Editor -->
<script src="https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs/loader.js"></script>
<script>
    require.config({
        paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs' }
    });

    require(['vs/editor/editor.main'], function () {
        window.editor = monaco.editor.create(
            document.getElementById('editor-container'),
            {
                value: "",
                language: "cpp",
                theme: "vs-dark",
                fontSize: 14,
                minimap: { enabled: false },
                automaticLayout: true,
                scrollBeyondLastLine: false,
                lineNumbers: "on",
                tabSize: 4,
                renderLineHighlight: "all",
                bracketPairColorization: { enabled: true },
            }
        );

        // Language switch
        document.getElementById('language-select').addEventListener('change', function () {
            var lang = this.value === 'cpp' ? 'cpp' : 'python';
            monaco.editor.setModelLanguage(window.editor.getModel(), lang);
        });
    });

    function syncCode() {
        document.getElementById('code-textarea').value = window.editor.getValue();
    }
</script>

{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add data/templates/submit.html
git commit -m "feat: integrate Monaco Editor in submit page with language switching"
```

---

### Task 12: Templates — highlight.js in submission_detail.html + Contest-aware problem_detail.html

**Files:**
- Modify: `data/templates/submission_detail.html`
- Modify: `data/templates/problem_detail.html`

- [ ] **Step 1: Add syntax highlighting to submission_detail.html**

Replace the code display section in `data/templates/submission_detail.html` (lines 25-28). The `<pre>` block becomes:

```html
{% extends "base.html" %}
{% block title %}提交 #{{ submission.id }} - LiteJudge{% endblock %}
{% block content %}

<!-- highlight.js -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/vs2015.min.css">
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/languages/cpp.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/languages/python.min.js"></script>

<div class="card">
    <h2>提交详情 #{{ submission.id }}</h2>
    <table class="mb-20">
        <tr><td width="100"><strong>题目</strong></td><td><a href="/problem/{{ submission.problem_id }}">{{ submission.problem_title }}</a></td></tr>
        <tr><td><strong>用户</strong></td><td>{{ submission.username }}</td></tr>
        <tr><td><strong>状态</strong></td><td><span class="status status-{{ submission.status }}">{{ submission.status }}</span></td></tr>
        <tr><td><strong>得分</strong></td><td>{{ submission.score }}</td></tr>
        <tr><td><strong>语言</strong></td><td>{{ submission.language }}</td></tr>
        <tr><td><strong>运行时间</strong></td><td>{{ submission.time_used }}ms</td></tr>
        <tr><td><strong>运行内存</strong></td><td>{{ submission.memory_used }}KB ({{ (submission.memory_used / 1024) | round(2) }}MB)</td></tr>
        <tr><td><strong>提交时间</strong></td><td>{{ submission.created_at }}</td></tr>
    </table>
</div>

{% if submission.compiler_output %}
<div class="card">
    <h3>编译输出</h3>
    <pre style="background:#1e1e1e; color:#f44747; padding:12px; border-radius:6px; overflow-x:auto; font-size:13px;">{{ submission.compiler_output }}</pre>
</div>
{% endif %}

<div class="card">
    <h3>源代码</h3>
    <pre><code class="language-{{ 'cpp' if submission.language == 'cpp' else 'python' }}">{{ submission.code }}</code></pre>
</div>

<script>hljs.highlightAll();</script>

{% endblock %}
```

- [ ] **Step 2: Add contest-aware "back to contest" link to problem_detail.html**

In `data/templates/problem_detail.html`, add a contest banner at the top of the content block (after the opening `{% block content %}` line):

```html
{% extends "base.html" %}
{% block title %}{{ problem.title }} - LiteJudge{% endblock %}
{% block content %}

{% if contest_id %}
<div class="card" style="background: #fffbe6; border-left: 4px solid #f39c12;">
    <strong>🏆 来自比赛</strong>
    <a href="/contest/{{ contest_id }}" style="margin-left: 12px;">← 返回比赛</a>
</div>
{% endif %}

<div class="card">
    <h2>{{ problem.title }}</h2>
    <!-- ... rest stays exactly the same ... -->
```

And update the "提交代码" link (line 24) to carry contest_id:

```html
    {% if user and user.user_id %}
        <a href="/problem/{{ problem.id }}/submit{% if contest_id %}?contest_id={{ contest_id }}{% endif %}" class="btn btn-primary">提交代码</a>
    {% else %}
        <a href="/login" class="btn btn-primary">登录后提交</a>
    {% endif %}
```

- [ ] **Step 3: Commit**

```bash
git add data/templates/submission_detail.html data/templates/problem_detail.html
git commit -m "feat: add highlight.js syntax highlighting, contest-aware problem detail"
```

---

### Task 13: Back-populate contest_list route status + Final Integration

**Files:**
- Modify: `data/app.py` (contest_list route)

- [ ] **Step 1: Update contest_list route to compute status**

In `data/app.py`, update the `contest_list` function (from Task 5) to add status computation. This is critical because the `contests.html` template uses `c.status`:

```python
@app.route('/contests')
def contest_list():
    is_admin = session.get('role') == 'admin'
    contests = get_all_contests(is_admin=is_admin)
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    for c in contests:
        if c['start_time'] > now:
            c['status'] = 'upcoming'
        elif c['end_time'] < now:
            c['status'] = 'ended'
        else:
            c['status'] = 'ongoing'
    return render_template('contests.html',
                           contests=contests,
                           user=session)
```

- [ ] **Step 2: Verify the `migrate_add_contest_id` import**

In `data/app.py`, verify that after line 11 (`init_db()`), we have:

```python
init_db()
migrate_add_contest_id()  # Add contest_id column to existing databases
```

Since `from database import *` is used, `migrate_add_contest_id` is already available.

- [ ] **Step 3: Test run the app**

```bash
cd data && python app.py
```

Visit `http://localhost:5000/` and verify:
- Homepage dashboard cards render
- `/contests` shows empty state (no contests yet)
- `/ranking` shows empty or existing rankings
- Navigation has "比赛" and "排行榜" links

- [ ] **Step 4: Create a test contest via admin**

Login as admin, go to `/admin/create_contest`, create a contest with:
- Title: "测试比赛"
- Start/end times covering now
- Problem IDs: 1 (if problem #1 exists)
- Then verify `/contests` shows it, `/contest/1` shows problems, submit flow works

- [ ] **Step 5: Commit**

```bash
git add data/app.py
git commit -m "fix: backfill contest status computation and migration call"
```

---

### Task 14: Push to Remote & Docker Rebuild

**Files:** None (infrastructure)

- [ ] **Step 1: Push branch**

```bash
git push origin Luyan
```

- [ ] **Step 2: Deploy to server**

```bash
# On server:
cd /path/to/Better-OpenJudge
git pull origin Luyan
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

- [ ] **Step 3: Verify deployment**

Visit the deployed URL, check:
- Homepage loads with dashboard
- Monaco Editor renders on submit page
- Contest routes work
- Rankings load

---

## Complete File Change Summary

| File | Action | Tasks |
|------|--------|-------|
| `data/database.py` | Modify | T1, T2, T3, T4 |
| `data/app.py` | Modify | T1, T5, T6, T7, T13 |
| `web/bridge.py` | Modify | T4 |
| `data/templates/base.html` | Modify | T8 |
| `data/templates/index.html` | Modify | T8 |
| `data/templates/submit.html` | Modify | T11 |
| `data/templates/submission_detail.html` | Modify | T12 |
| `data/templates/problem_detail.html` | Modify | T12 |
| `data/templates/contests.html` | Create | T9 |
| `data/templates/contest_detail.html` | Create | T9 |
| `data/templates/contest_ranking.html` | Create | T9 |
| `data/templates/ranking.html` | Create | T10 |
| `data/templates/admin/contests.html` | Create | T10 |
| `data/templates/admin/create_contest.html` | Create | T10 |
