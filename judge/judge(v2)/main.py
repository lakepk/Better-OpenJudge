from core.controller import JudgeController
import os

if __name__=="__main__":
    # 1. simulate task data sent from the web client
    mock_task={
        "submission_id":9999,
        "problem_id":1001,
        "language":"python3",
        "source_code":"import sys\nfor line in sys.stdin:\n    print(int(line) * 2)",
        "time_limit":1.0,
        "memory_limit":128
    }

    # ensure that simulated input and output have been created
    mock_in = "mock_1.in"
    mock_out = "mock_1.out"
    with open(mock_in, "w") as f: f.write("10\n5\n")
    with open(mock_out, "w") as f: f.write("20\n10\n")

    test_cases = [
        {"in": mock_in, "out": mock_out}
    ]

    # 3. compile and run
    print("start testing...")
    controller = JudgeController(mock_task)
    result = controller.start(test_cases)
    
    print("\nreturn result JSON:")
    print(result)

    # 清理外部模拟文件
    os.remove(mock_in)
    os.remove(mock_out)