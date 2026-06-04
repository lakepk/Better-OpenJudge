import subprocess
import time
from typing import Dict, Any

class Runner:
    def __init__(self,exe_path:str,lang:str):
        self.exe_path=exe_path
        self.lang=lang

    def run_single_case(self,input_file:str,output_file:str,time_limit:float,memory_limit:int)->Dict[str,Any]:
        """
        运行单个测试点
        - input_file: 标准输入文件路径
        - output_file: 用户输出写入的临时文件路径
        - time_limit: 时间限制(秒)
        - memory_limit: 内存限制(MB)
        """
        # 根据语言构建执行命令
        cmd=[]
        if self.lang.lower() in ["python","python3"]:
            cmd=["python",self.exe_path]
        else:
            cmd=[self.exe_path]
        start_time=time.time()    
        try:
            with open(input_file,'r') as infile,open(output_file,'w') as outfile:
                res=subprocess.run(
                    cmd,
                    stdin=infile,
                    stdout=outfile,
                    stderr=subprocess.PIPE,
                    timeout=time_limit, #基础限时防止死循环
                    text=True
                )
            time_used=(time.time()-start_time)*1000 #转为毫秒
            if res.returncode!=0:
                return {"status":"RE","time":time_used,"memory":0,"message":res.stderr}
            return {"status":"SUCCESS","time":time_used,"memory":0}
            
        except subprocess.TimeoutExpired:
            return {"status":"TLE","time":time_limit*1000,"memory":0}
        except Exception as e:
            return {"status":"SE","time":0,"memory":0,"message":str(e)}