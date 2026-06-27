"""initial_schema

Revision ID: 534185f5601f
Revises:
Create Date: 2026-06-28 00:45:38.463024

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '534185f5601f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables with the current schema."""
    # Users
    op.execute("""
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
    """)

    # Problems
    op.execute("""
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
    """)

    # Test cases
    op.execute("""
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
    """)

    # Submissions
    op.execute("""
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
    """)

    # Announcements
    op.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            is_pinned BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tags
    op.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    # Problem_tags
    op.execute("""
        CREATE TABLE IF NOT EXISTS problem_tags (
            problem_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (problem_id, tag_id),
            FOREIGN KEY (problem_id) REFERENCES problems(id),
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        )
    """)

    # Contests
    op.execute("""
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
    """)

    # Contest_problems
    op.execute("""
        CREATE TABLE IF NOT EXISTS contest_problems (
            contest_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            problem_order INTEGER DEFAULT 1,
            score INTEGER DEFAULT 100,
            PRIMARY KEY (contest_id, problem_id),
            FOREIGN KEY (contest_id) REFERENCES contests(id),
            FOREIGN KEY (problem_id) REFERENCES problems(id)
        )
    """)

    # Contest_registrations
    op.execute("""
        CREATE TABLE IF NOT EXISTS contest_registrations (
            contest_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (contest_id, user_id),
            FOREIGN KEY (contest_id) REFERENCES contests(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # API tokens
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Enable WAL mode
    op.execute("PRAGMA journal_mode=WAL;")
    op.execute("PRAGMA busy_timeout=5000;")


def downgrade() -> None:
    """Drop all tables."""
    op.execute("DROP TABLE IF EXISTS contest_registrations")
    op.execute("DROP TABLE IF EXISTS contest_problems")
    op.execute("DROP TABLE IF EXISTS contests")
    op.execute("DROP TABLE IF EXISTS api_tokens")
    op.execute("DROP TABLE IF EXISTS problem_tags")
    op.execute("DROP TABLE IF EXISTS tags")
    op.execute("DROP TABLE IF EXISTS announcements")
    op.execute("DROP TABLE IF EXISTS submissions")
    op.execute("DROP TABLE IF EXISTS test_cases")
    op.execute("DROP TABLE IF EXISTS problems")
    op.execute("DROP TABLE IF EXISTS users")