import os

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DATA_DIR=os.path.join(BASE_DIR,"data")       #测试数据存放地
RUN_DIR=os.path.join(BASE_DIR,"run_tmp")     #运行用户代码的临时沙箱目录

os.makedirs(RUN_DIR, exist_ok=True)

class JudgeStatus:
    AC="Accepted"
    WA="Wrong Answer"
    TLE="Time Limit Exceeded"
    MLE="Memory Limit Exceeded"
    RE="Runtime Error"
    CE="Compile Error"
    SE="System Error"