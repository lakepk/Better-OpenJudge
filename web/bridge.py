"""
Bridge between Flask (data/) and Judge (judge/).

Patches database.create_submission so every code submission
automatically triggers a background judge thread.
"""
import json
import os
import shutil
import sys
import tempfile
import threading


# ── Path setup ──────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DATA_DIR = os.path.join(_PROJECT_ROOT, 'data')
if _DATA_DIR not in sys.path:
    sys.path.insert(0, _DATA_DIR)

_JUDGE_DIR = os.path.join(_PROJECT_ROOT, 'judge')
if _JUDGE_DIR not in sys.path:
    sys.path.insert(0, _JUDGE_DIR)

# ── Override database path (env var, for Docker) ────────────
from data import database as db_module

if os.environ.get('DATABASE_PATH'):
    db_module.DATABASE = os.environ['DATABASE_PATH']

# CRITICAL: app.py does  from database import *  which creates a SEPARATE
# module instance.  Force both names to point to the SAME module so the
# DATABASE override above actually takes effect.
sys.modules['database'] = db_module

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
from judge.core.runner import Runner

# ── Fix: runner.py hardcodes "memory":0 — monkey-patch real measurement ──
import resource

_original_run_single_case = Runner.run_single_case

def _patched_run_single_case(self, input_file, output_file, time_limit, memory_limit):
    """Wrapper that adds actual memory measurement via getrusage()."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = _original_run_single_case(self, input_file, output_file,
                                       time_limit, memory_limit)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    # ru_maxrss is in KB on Linux; convert to MB (the unit the DB expects)
    memory_kb = after.ru_maxrss - before.ru_maxrss
    if memory_kb > 0:
        result['memory'] = round(memory_kb / 1024, 2)
    return result

Runner.run_single_case = _patched_run_single_case

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
    # 1. Load from database
    submission = get_submission_detail(submission_id)
    if not submission:
        return

    problem = get_problem_by_id(submission['problem_id'])
    if not problem:
        update_submission_result(submission_id, status="SE",
                                 judge_detail="Problem not found")
        return

    test_cases = get_test_cases(submission['problem_id'])
    if not test_cases:
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

        update_submission_result(
            submission_id,
            status=db_status,
            score=_calc_score(result, test_cases),
            time_used=int(result.get('time_used', 0)),
            memory_used=int(result.get('memory_used', 0)),
            compiler_output=result.get('message', ''),
            judge_detail=detail_json,
        )

        # 6. Refresh problem statistics (total / AC counts)
        update_problem_stats(submission['problem_id'])

    except Exception as exc:
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
    """Fire-and-forget: spawn a daemon thread to judge this submission."""
    threading.Thread(
        target=_run_judge,
        args=(submission_id,),
        daemon=True,
        name=f"judge-{submission_id}",
    ).start()


# ── Monkey-patch ─────────────────────────────────────────────
_original_create = db_module.create_submission


def _patched_create(user_id, problem_id, code, language='cpp', contest_id=None):
    """Drop-in replacement that triggers the judge after insert."""
    submission_id = _original_create(user_id, problem_id, code, language, contest_id)
    judge_async(submission_id)
    return submission_id


def install():
    """Activate the bridge.  Call **once** before the Flask app starts.

    Replaces ``database.create_submission`` with a version that
    automatically launches a background judge thread.
    """
    db_module.create_submission = _patched_create
