import os
import shutil
import subprocess
import tempfile
#import uuid
class Checker:
    @staticmethod
    def check(user_out_path:str,ans_out_path:str,input_path:str=None,spj_path:str=None)->bool:
        status,_=Checker.check_with_status(user_out_path,ans_out_path,input_path,spj_path)
        return status=="AC"

    @staticmethod
    def check_with_status(user_out_path:str,ans_out_path:str,input_path:str=None,spj_path:str=None):
        if spj_path:
            return Checker._check_by_spj(spj_path,input_path,user_out_path,ans_out_path)

        try:
            with open(user_out_path,'r',encoding='utf-8',errors='replace') as f1,\
                 open(ans_out_path,'r',encoding='utf-8',errors='replace') as f2:
                user_lines=[line.rstrip() for line in f1.readlines() if line.strip()]
                ans_lines=[line.rstrip() for line in f2.readlines() if line.strip()]

            return ("AC","Accepted") if user_lines==ans_lines else ("WA","Wrong Answer")
        except Exception as e:
            return "SE",str(e)

    @staticmethod
    def _check_by_spj(spj_path:str,input_path:str,user_out_path:str,ans_out_path:str):
        if not input_path:
            return "SE","SPJ requires input file path"
        if not os.path.exists(spj_path):
            return "SE","SPJ file not found"
        if not shutil.which("docker"):
            return "SE","Docker is not available for SPJ"

        try:
            with tempfile.TemporaryDirectory(prefix="judge_spj_") as tmp:
                workdir=os.path.abspath(tmp)

                spj_name=os.path.basename(spj_path)
                shutil.copyfile(spj_path,os.path.join(workdir,spj_name))
                shutil.copyfile(input_path,os.path.join(workdir,"input.txt"))
                shutil.copyfile(user_out_path,os.path.join(workdir,"user_output.txt"))
                shutil.copyfile(ans_out_path,os.path.join(workdir,"answer.txt"))
                #container_name=f"spj_{uuid.uuid4().hex}"
                cmd=[
                    "docker","run","--rm",
                    #"--name",container_name,
                    "--network","none",
                    "--memory","128m",
                    "--memory-swap","128m",
                    "--pids-limit","32",
                    "--cpus","0.5",
                    "--read-only",
                    "--tmpfs","/tmp:rw,noexec,nosuid,size=32m",
                    "--security-opt","no-new-privileges",
                    "--cap-drop","ALL",
                    "-e","PYTHONDONTWRITEBYTECODE=1",
                    "-v",f"{workdir}:/work:ro",
                    "-w","/work",
                    "python:3.11-slim",
                    "python",
                    f"/work/{spj_name}",
                    "/work/input.txt",
                    "/work/user_output.txt",
                    "/work/answer.txt"
                ]

                res=subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=4,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )

        except subprocess.TimeoutExpired:
            return "SE","SPJ timeout"
        # except subprocess.TimeoutExpired:
        #     subprocess.run(
        #         ["docker","kill",container_name],
        #         stdout=subprocess.DEVNULL,
        #         stderr=subprocess.DEVNULL
        #     )
        #     return "SE","SPJ timeout"
        except Exception as e:
            return "SE",str(e)

        message=(res.stdout or res.stderr or "").strip()

        if res.returncode==0:
            return "AC",message or "Accepted"
        if res.returncode==1:
            return "WA",message or "Wrong Answer"
        if res.returncode in (137,-9):
            return "SE","SPJ memory limit exceeded"

        return "SE",message or "SPJ runtime error"