import subprocess
import time
import os
import shutil
import uuid
from typing import Dict, Any

class Runner:
    def __init__(self,exe_path:str,lang:str):
        self.exe_path=exe_path
        self.lang=lang

    def _docker_target(self):
        workspace=os.path.dirname(os.path.abspath(self.exe_path))
        filename=os.path.basename(self.exe_path)

        if self.lang.lower() in ["python","python3"]:
            return workspace,["python",f"/work/{filename}"],"python:3.11-slim"

        return workspace,[f"/work/{filename}"],"gcc:13-bookworm"

    def run_single_case(self,input_file:str,output_file:str,time_limit:float,memory_limit:int)->Dict[str,Any]:
        """
        运行单个测试点。默认使用 Docker 沙箱。
        """
        if not shutil.which("docker"):
            return {
                "status":"SE",
                "time":0,
                "memory":0,
                "message":"Docker is not available"
            }

        workspace,inner_cmd,image=self._docker_target()
        container_name=f"judge_{uuid.uuid4().hex}"
        memory_arg=f"{memory_limit}m"

        cmd=[
            "docker","run","--rm",
            "--name",container_name,
            "--network","none",
            "--memory",memory_arg,
            "--memory-swap",memory_arg,
            "--pids-limit","64",
            "--cpus","1.0",
            "--read-only",
            "--tmpfs","/tmp:rw,noexec,nosuid,size=64m",
            "--security-opt","no-new-privileges",
            "--cap-drop","ALL",
            "-e","PYTHONDONTWRITEBYTECODE=1",
            "-v",f"{workspace}:/work:ro",
            "-w","/work",
            image
        ]+inner_cmd

        start_time=time.time()

        try:
            with open(input_file,"r",encoding="utf-8",errors="replace") as infile:
                res=subprocess.run(
                    cmd,
                    stdin=infile,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=time_limit+1,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )

            with open(output_file,"w",encoding="utf-8") as outfile:
                outfile.write(res.stdout)

            time_used=(time.time()-start_time)*1000

            if res.returncode in (137,-9):
                return {
                    "status":"MLE",
                    "time":time_used,
                    "memory":memory_limit,
                    "message":"Memory Limit Exceeded"
                }

            if res.returncode!=0:
                return {
                    "status":"RE",
                    "time":time_used,
                    "memory":0,
                    "message":res.stderr
                }

            return {
                "status":"SUCCESS",
                "time":time_used,
                "memory":0
            }

        except subprocess.TimeoutExpired:
            subprocess.run(
                ["docker","kill",container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return {
                "status":"TLE",
                "time":time_limit*1000,
                "memory":0
            }

        except Exception as e:
            return {
                "status":"SE",
                "time":0,
                "memory":0,
                "message":str(e)
            }