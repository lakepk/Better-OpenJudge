import os
import subprocess
import sys
import threading
import time
from typing import Any, Dict


IS_LINUX = sys.platform.startswith('linux')
if IS_LINUX:
    import resource


def _set_child_limits(memory_limit_mb: int):
    """preexec_fn: set RLIMIT_AS before exec (simple syscall, thread-safe)."""
    limit_bytes = memory_limit_mb * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    except (ValueError, OSError):
        pass


class Runner:
    def __init__(self, exe_path: str, lang: str):
        self.exe_path = exe_path
        self.lang = lang

    def run_single_case(
        self, input_file: str, output_file: str,
        time_limit: float, memory_limit: int,
    ) -> Dict[str, Any]:
        cmd = (
            ['python', self.exe_path]
            if self.lang.lower() in ('python', 'python3')
            else [self.exe_path]
        )

        t_start = time.time()

        try:
            with open(input_file, 'r') as infile, \
                 open(output_file, 'w') as outfile:
                kwargs = dict(stdin=infile, stdout=outfile, stderr=subprocess.PIPE)
                if IS_LINUX:
                    kwargs['preexec_fn'] = lambda: _set_child_limits(memory_limit)
                proc = subprocess.Popen(cmd, **kwargs)
        except Exception as exc:
            return {'status': 'SE', 'time': 0, 'memory': 0,
                    'message': str(exc)}

        timed_out = threading.Event()

        def _kill_on_timeout():
            if not timed_out.wait(timeout=time_limit):
                try:
                    proc.kill()
                except OSError:
                    pass

        timer = threading.Thread(target=_kill_on_timeout, daemon=True)
        timer.start()

        max_rss_kb = 0

        if IS_LINUX:
            def _read_vmhwm():
                nonlocal max_rss_kb
                try:
                    with open(f'/proc/{proc.pid}/status', 'r') as f:
                        for line in f:
                            if line.startswith('VmHWM:'):
                                parts = line.split()
                                if len(parts) >= 2:
                                    hwm_kb = int(parts[1])
                                    if hwm_kb > max_rss_kb:
                                        max_rss_kb = hwm_kb
                                return
                except (FileNotFoundError, ProcessLookupError):
                    pass

            time.sleep(0.001)
            _read_vmhwm()

            while proc.poll() is None:
                _read_vmhwm()
                time.sleep(0.005)
        else:
            proc.wait()

        timed_out.set()
        timer.join(timeout=1)

        wall_ms = int((time.time() - t_start) * 1000)
        exit_code = proc.returncode

        stderr_output = ''
        try:
            if proc.stderr:
                stderr_output = proc.stderr.read()
        except Exception:
            pass

        if exit_code is None:
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            return {'status': 'TLE', 'time': int(time_limit * 1000),
                    'memory': max_rss_kb}

        if exit_code is not None and exit_code < 0:
            near_limit = max_rss_kb > 0 and max_rss_kb >= memory_limit * 1024 * 0.8
            if exit_code == -9 or exit_code == -15:
                if near_limit:
                    return {'status': 'MLE', 'time': wall_ms,
                            'memory': max_rss_kb,
                            'message': f'Memory limit exceeded ({memory_limit} MB)'}
                return {'status': 'TLE' if exit_code == -9 else 'RE',
                        'time': int(time_limit * 1000),
                        'memory': max_rss_kb,
                        'message': f'Killed by signal {abs(exit_code)}'}
            if near_limit:
                return {'status': 'MLE', 'time': wall_ms,
                        'memory': max_rss_kb,
                        'message': f'Memory limit exceeded ({memory_limit} MB)'}
            return {'status': 'RE', 'time': wall_ms,
                    'memory': max_rss_kb,
                    'message': f'Runtime Error (signal {abs(exit_code)})'}

        if exit_code != 0:
            return {'status': 'RE', 'time': wall_ms,
                    'memory': max_rss_kb, 'message': stderr_output}

        return {'status': 'SUCCESS', 'time': wall_ms,
                'memory': max_rss_kb}
