import os
import shutil
import subprocess

class Compiler:
    @staticmethod
    def compile(lang:str,src_path:str,output_dir:str)->str:
        if lang.lower() in ["python","python3"]:
            return src_path

        elif lang.lower() in ["c++", "cpp"]:
            exe_path=os.path.join(output_dir,"main")

            if shutil.which("docker"):
                cmd=[
                    "docker","run","--rm",
                    "-v",f"{os.path.abspath(output_dir)}:/work",
                    "-w","/work",
                    "gcc:13-bookworm",
                    "g++",
                    os.path.basename(src_path),
                    "-o","main",
                    "-O2",
                    "-std=c++17"
                ]
            else:
                # only for local no-docker test
                exe_path=os.path.join(output_dir,"main.exe" if os.name=="nt" else "main")
                cmd=["g++",src_path,"-o",exe_path,"-O2","-std=c++17"]

            res=subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            if res.returncode!=0:
                raise Exception(f"Compile Error: {res.stderr}")

            return exe_path

        else:
            raise NotImplementedError(f"Unsupported language:{lang}")