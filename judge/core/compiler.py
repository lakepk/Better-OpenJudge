import os
import subprocess

COMPILE_TIMEOUT = 30


class Compiler:
    @staticmethod
    def compile(lang: str, src_path: str, output_dir: str) -> str:
        if lang.lower() in ('python', 'python3'):
            return src_path

        elif lang.lower() in ('c++', 'cpp'):
            exe_path = os.path.join(output_dir,
                                    'main.exe' if os.name == 'nt' else 'main')
            cmd = ['g++', src_path, '-o', exe_path, '-O2', '-Wall',
                   '-fmax-errors=10']

            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True,
                                     timeout=COMPILE_TIMEOUT)
            except subprocess.TimeoutExpired:
                raise RuntimeError(
                    f'Compile Error: compilation timed out '
                    f'({COMPILE_TIMEOUT}s limit exceeded)')

            if res.returncode != 0:
                short = os.path.basename(src_path)
                safe = res.stderr.replace(src_path, short)
                raise RuntimeError(f'Compile Error:\n{safe}')

            return exe_path

        else:
            raise NotImplementedError(f'Unsupported language: {lang}')
