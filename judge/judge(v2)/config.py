import os

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DATA_DIR=os.path.join(BASE_DIR,"data")       #test data storage location
RUN_DIR=os.path.join(BASE_DIR,"run_tmp")     #temporary sandbox directory

os.makedirs(RUN_DIR, exist_ok=True)

class JudgeStatus:
    AC="Accepted"
    WA="Wrong Answer"
    TLE="Time Limit Exceeded"
    MLE="Memory Limit Exceeded"
    RE="Runtime Error"
    CE="Compile Error"
    SE="System Error"