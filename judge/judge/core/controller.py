import os
import shutil
from typing import Dict, Any
from .compiler import Compiler
from .runner import Runner
from .checker import Checker
from config import RUN_DIR, JudgeStatus

class JudgeController:
    def __init__(self,task_data:Dict[str,Any]):
        self.task_id=task_data["submission_id"]
        self.problem_id=task_data["problem_id"]
        self.lang=task_data["language"]
        self.code=task_data["source_code"]
        self.time_limit=task_data["time_limit"]     # 假设传入的是秒
        self.memory_limit=task_data["memory_limit"] # 假设传入的是MB
        # 临时工作目录
        self.workspace=os.path.join(RUN_DIR,f"sub_{self.task_id}")
        os.makedirs(self.workspace,exist_ok=True)

    def start(self, test_cases:list)->Dict[str,Any]:
        """
        开始评测主流程
        test_cases: 格式如 [{"in": "1.in", "out": "1.out"}, ...]
        """
        # 将代码写入临时文件
        ext=".py" if "python" in self.lang.lower() else ".cpp"
        src_path=os.path.join(self.workspace,f"solution{ext}")
        with open(src_path,"w",encoding="utf-8") as f:
            f.write(self.code)

        # 编译
        try:
            exe_path=Compiler.compile(self.lang,src_path,self.workspace)
        except Exception as e:
            self._cleanup()
            return {"status":JudgeStatus.CE,"message":str(e),"cases":[]}

        # 循环跑测试点
        runner=Runner(exe_path,self.lang)
        final_status=JudgeStatus.AC
        max_time=0
        max_memory=0
        cases_results=[]

        for idx,case in enumerate(test_cases):
            user_out = os.path.join(self.workspace,f"user_{idx}.out")
            
            # 运行该测试点
            run_res=runner.run_single_case(case["in"],case["out"],self.time_limit,self.memory_limit)
            
            # 更新时空消耗最大值
            max_time=max(max_time,run_res["time"])
            max_memory=max(max_memory,run_res["memory"])

            # 结果判定
            if run_res["status"]=="SUCCESS":
                # 运行成功，比对输出
                is_correct=Checker.check(user_out,case["out"])
                case_status=JudgeStatus.AC if is_correct else JudgeStatus.WA
            else:
                case_status=getattr(JudgeStatus,run_res["status"],JudgeStatus.RE)

            cases_results.append({
                "case_num":idx+1,
                "status":case_status,
                "time":run_res["time"],
                "memory":run_res["memory"]
            })

            if case_status!=JudgeStatus.AC and final_status==JudgeStatus.AC:
                final_status=case_status
                break  # 记录第一个未通过的状态作为整体状态

        self._cleanup()

        return {
            "submission_id":self.task_id,
            "status":final_status,
            "time_used":max_time,
            "memory_used":max_memory,
            "test_cases":cases_results
        }

    def _cleanup(self):
        """清理临时工作空间"""
        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace)