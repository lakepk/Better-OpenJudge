import subprocess
import os

class Compiler:
    @staticmethod
    def compile(lang:str,src_path:str,output_dir:str)->str:
        """
        编译用户代码
        返回：编译后的可执行文件路径/执行命令路径。如果不需要编译（如Python），直接返回原路径。
        Raises: CompileError
        """
        if lang.lower() in ["python","python3"]:
            return src_path
            
        elif lang.lower() in ["c++", "cpp"]:
            exe_path=os.path.join(output_dir,"main.exe" if os.name=='nt' else "main")
            #g++ main.cpp -o main
            cmd=["g++",src_path,"-o",exe_path,"-O2"]
            res=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            if res.returncode!=0:
                raise Exception(f"Compile Error: {res.stderr}")
            return exe_path
            
        else:
            raise NotImplementedError(f"Unsupported language:{lang}")