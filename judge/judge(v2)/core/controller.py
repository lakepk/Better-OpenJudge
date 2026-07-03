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
        self.time_limit=task_data["time_limit"]     # assumption:input in s
        self.memory_limit=task_data["memory_limit"] # assumption:input in MB
        self.spj_path=task_data.get("spj_path") or task_data.get("special_judge_path")
        # temporary working directory
        self.workspace=os.path.join(RUN_DIR,f"sub_{self.task_id}")
        os.makedirs(self.workspace,exist_ok=True)

    def start(self, test_cases:list)->Dict[str,Any]:
        """
        start:
        test_cases: format:[{"in": "1.in", "out": "1.out"}, ...]
        """
        # write code in a temporary file
        ext=".py" if "python" in self.lang.lower() else ".cpp"
        src_path=os.path.join(self.workspace,f"solution{ext}")
        with open(src_path,"w",encoding="utf-8") as f:
            f.write(self.code)

        # compile
        try:
            exe_path=Compiler.compile(self.lang,src_path,self.workspace)
        except Exception as e:
            self._cleanup()
            return {"status":JudgeStatus.CE,"message":str(e),"cases":[]}

        # circuit run test point
        runner=Runner(exe_path,self.lang)
        final_status=JudgeStatus.AC
        max_time=0
        max_memory=0
        cases_results=[]
        
        for idx,case in enumerate(test_cases):
            user_out = os.path.join(self.workspace,f"user_{idx}.out")
            message=''
            # running current test point
            run_res=runner.run_single_case(case["in"],user_out,self.time_limit,self.memory_limit)
            
            # update max_time,memory
            max_time=max(max_time,run_res["time"])
            max_memory=max(max_memory,run_res["memory"])

            # result judge
            if run_res["status"]=="SUCCESS":
                #compilation successful,compare results
                status,message=Checker.check_with_status(user_out,case["out"],case["in"],self.spj_path)
                case_status=getattr(JudgeStatus,status,JudgeStatus.RE)
            else:
                case_status=getattr(JudgeStatus,run_res["status"],JudgeStatus.RE)

            cases_results.append({
                "case_num":idx+1,
                "status":case_status,
                "time":run_res["time"],
                "memory":run_res["memory"],
                "message":message if run_res["status"]=="SUCCESS" else run_res.get("message","")
            })

            if case_status!=JudgeStatus.AC and final_status==JudgeStatus.AC:
                final_status=case_status
                break  # record the first failed status as the overall status

        self._cleanup()

        return {
            "submission_id":self.task_id,
            "status":final_status,
            "time_used":max_time,
            "memory_used":max_memory,
            "test_cases":cases_results
        }

    def _cleanup(self):
        """clean temporary working space"""
        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace)