"""
Bridge between Flask (data/) and Judge (judge/).

Patches database.create_submission so every code submission
automatically triggers a background judge thread.
"""
import json
import logging
import os
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor


# ── Path setup ──────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DATA_DIR = os.path.join(_PROJECT_ROOT, 'data')
if _DATA_DIR not in sys.path:
    sys.path.insert(0, _DATA_DIR)

# ── Override database path (env var, for Docker) ────────────
from data import database as db_module

if os.environ.get('DATABASE_PATH'):
    db_module.DATABASE = os.environ['DATABASE_PATH']

# CRITICAL: app.py does  from database import *  which creates a SEPARATE
# module instance.  Force both names to point to the SAME module so the
# DATABASE override above actually takes effect.
sys.modules['database'] = db_module

# ── Logging ──────────────────────────────────────────────────
LOG_FORMAT = '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt='%Y-%m-%dT%H:%M:%S',
    stream=sys.stdout,
)
logger = logging.getLogger('bridge')

# ── Judge concurrency control ─────────────────────────────────
_JUDGE_POOL = ThreadPoolExecutor(
    max_workers=int(os.environ.get('JUDGE_MAX_WORKERS', '4')),
    thread_name_prefix='judge',
)
logger.info("Judge pool initialized: max_workers=%d", _JUDGE_POOL._max_workers)

# Re-import from the (possibly reconfigured) database module
from data.database import (
    get_submission_detail,
    get_problem_by_id,
    get_test_cases,
    update_submission_result,
    update_problem_stats,
)

# ── Judge imports ───────────────────────────────────────────
from judge.config import JudgeStatus
from judge.core.controller import JudgeController

# ── Status mapping: JudgeStatus strings → DB short codes ────
_STATUS_MAP = {
    "Accepted":              "AC",
    "Wrong Answer":          "WA",
    "Time Limit Exceeded":   "TLE",
    "Memory Limit Exceeded": "MLE",
    "Runtime Error":         "RE",
    "Compile Error":         "CE",
    "System Error":          "SE",
}


# ═══════════════════════════════════════════════════════════════
#  Background judge worker
# ═══════════════════════════════════════════════════════════════

def _run_judge(submission_id: int) -> None:
    """Fetch data from DB, run the judge engine, write results back."""
    import time
    t_start = time.time()
    logger.info("Judge start: submission_id=%d", submission_id)

    # 1. Load from database
    submission = get_submission_detail(submission_id)
    if not submission:
        logger.error("Judge abort: submission_id=%d not found", submission_id)
        return

    problem = get_problem_by_id(submission['problem_id'])
    if not problem:
        logger.error("Judge abort: problem_id=%d not found for submission_id=%d",
                      submission['problem_id'], submission_id)
        update_submission_result(submission_id, status="SE",
                                 judge_detail="Problem not found")
        return

    test_cases = get_test_cases(submission['problem_id'])
    if not test_cases:
        logger.error("Judge abort: no test cases for problem_id=%d, submission_id=%d",
                      submission['problem_id'], submission_id)
        update_submission_result(submission_id, status="SE",
                                 judge_detail="No test cases configured")
        return

    # 2. Write test-case data from DB into temp files
    #    Judge expects:  [{"in": "/path/1.in", "out": "/path/1.out"}, …]
    tmpdir = tempfile.mkdtemp(prefix=f"tc_{submission_id}_")
    judge_cases = []

    try:
        for i, tc in enumerate(test_cases):
            in_path = os.path.join(tmpdir, f"{i + 1}.in")
            out_path = os.path.join(tmpdir, f"{i + 1}.out")
            with open(in_path, 'w', encoding='utf-8') as f:
                f.write(tc['input'])
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(tc['output'])
            judge_cases.append({"in": in_path, "out": out_path})

        # 3. Build task_data — note unit conversions
        #
        #    ┌──────────┬──────────────────┬──────────────────┐
        #    │ Field    │ DB               │ Judge            │
        #    ├──────────┼──────────────────┼──────────────────┤
        #    │ time     │ ms    (int)      │ seconds  (float) │
        #    │ memory   │ KB    (int)      │ MB       (int)   │
        #    └──────────┴──────────────────┴──────────────────┘
        task_data = {
            "submission_id": submission_id,
            "problem_id":    submission['problem_id'],
            "language":      submission['language'],
            "source_code":   submission['code'],
            "time_limit":    problem['time_limit'] / 1000.0,
            "memory_limit":  max(problem['memory_limit'] // 1024, 1),
        }

        # 4. Create controller  (this creates workspace dir)
        controller = JudgeController(task_data)

        # 4a. WORKAROUND for a bug in the judge runner:
        #     runner.run_single_case() writes stdout to case["out"],
        #     overwriting the expected-answer file.  Then checker
        #     compares the (empty) workspace/user_N.out with the
        #     now-overwritten case["out"] — so it would always WA.
        #
        #     Fix: pre-write expected answers into the workspace
        #     files that checker actually reads.  Runner will still
        #     trash case["out"], but checker now has the right data
        #     in workspace/user_N.out.
        for i, tc in enumerate(test_cases):
            user_out = os.path.join(controller.workspace, f"user_{i}.out")
            with open(user_out, 'w', encoding='utf-8') as f:
                f.write(tc['output'])

        # 4b. Run the judge pipeline  (compile → run → check)
        result = controller.start(judge_cases)

        # 5. Convert judge result → database fields
        db_status   = _STATUS_MAP.get(result['status'], 'SE')
        detail_json = json.dumps(result.get('test_cases', []),
                                 ensure_ascii=False)
        total_score = _calc_score(result, test_cases)

        update_submission_result(
            submission_id,
            status=db_status,
            score=total_score,
            time_used=int(result.get('time_used', 0)),
            memory_used=int(result.get('memory_used', 0)),
            compiler_output=result.get('message', ''),
            judge_detail=detail_json,
        )

        # 6. Refresh problem statistics (total / AC counts)
        update_problem_stats(submission['problem_id'])

        elapsed = round(time.time() - t_start, 2)
        logger.info(
            "Judge done: submission_id=%d, status=%s, score=%d, elapsed=%.2fs",
            submission_id, db_status, total_score, elapsed,
        )

    except Exception as exc:
        logger.exception(
            "Judge internal error: submission_id=%d", submission_id,
        )
        update_submission_result(
            submission_id,
            status="SE",
            judge_detail=f"Internal judge error: {exc}",
        )
    finally:
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)


def _calc_score(result: dict, test_cases: list) -> int:
    """Sum scores of every passed test case."""
    total = 0
    for tc_result in result.get('test_cases', []):
        if tc_result['status'] == 'Accepted':
            idx = tc_result['case_num'] - 1
            if 0 <= idx < len(test_cases):
                total += test_cases[idx].get('score', 0)
    return total


# ═══════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════

def judge_async(submission_id: int) -> None:
    """Enqueue a background judge task via the shared thread pool.

    The pool size is controlled by the JUDGE_MAX_WORKERS env var (default 4).
    Submissions beyond the pool capacity queue up as futures.
    """
    future = _JUDGE_POOL.submit(_run_judge, submission_id)
    pending = getattr(_JUDGE_POOL, '_work_queue', None)
    queue_len = pending.qsize() if pending else 0
    logger.info(
        "Judge task enqueued: submission_id=%d, pending_queue=%d",
        submission_id, queue_len,
    )
    # Attach a done callback for error surfacing
    future.add_done_callback(lambda f: (
        logger.error("Judge task failed: submission_id=%d, exception=%s",
                      submission_id, f.exception())
    ) if f.exception() else None)


# ── Monkey-patch ─────────────────────────────────────────────
_original_create = db_module.create_submission


def _patched_create(user_id, problem_id, code, language='cpp'):
    """Drop-in replacement that triggers the judge after insert."""
    submission_id = _original_create(user_id, problem_id, code, language)
    judge_async(submission_id)
    return submission_id


def install():
    """Activate the bridge.  Call **once** before the Flask app starts.

    Replaces ``database.create_submission`` with a version that
    automatically launches a background judge thread.
    """
    db_module.create_submission = _patched_create
