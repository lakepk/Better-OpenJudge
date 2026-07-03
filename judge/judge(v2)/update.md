# Judge 改动综述与使用注意事项

## 完成情况

本次 `judge` 部分已基本完成TODO中的核心项：

- **代码沙箱**：`runner.py` 已从直接运行用户程序改为 Docker 沙箱运行
- **跨平台兼容**：`compiler.py` 在有 Docker 时使用 `gcc:13-bookworm` 编译 C++，Windows 本地和 Linux 服务器可统一走 Linux Docker 环境
- **Special Judge**：`checker.py` 已支持普通文本比对和 SPJ 两种模式
- **控制流程接入**：`controller.py` 已从 `task_data` 读取 `spj_path` / `special_judge_path`，并把用户输出写入 `user_out` 后再判题
- **重复旧包清理**：`judge/judge/` 旧目录当前不存在
- **编码状态**：核心文件当前可按 UTF-8 读取

## 核心流程

text
JudgeController.start()
  -> 写入用户源码到 run_tmp/sub_xxx/solution.py 或 solution.cpp
  -> Compiler.compile()
      -> Python：直接返回源码路径
      -> C++：优先使用 Docker gcc:13-bookworm 编译为 main
  -> Runner.run_single_case()
      -> 使用 Docker 沙箱运行 solution.py 或 main
      -> 禁止网络，限制内存、CPU、进程数
      -> 用户输出写入 user_x.out
  -> Checker.check_with_status()
      -> 无 spj_path：普通文本比对
      -> 有 spj_path：运行 SPJ 脚本判定 AC / WA / SE

### Docker 沙箱说明
runner.py 当前使用的关键限制包括：
--network none
--memory <memory_limit>m
--memory-swap <memory_limit>m
--pids-limit 64
--cpus 1.0
--read-only
--tmpfs /tmp:rw,noexec,nosuid,size=64m
--security-opt no-new-privileges
--cap-drop ALL
这些限制覆盖了待办中的主要安全要求：禁网、限内存、限制 CPU/时间、限制进程数、减少容器权限。

### SPJ 使用约定
SPJ 脚本调用格式：
python spj.py input.txt user_output.txt answer.txt
返回码约定：
0 = AC
1 = WA
其他 = SE
data/web 侧需要在提交给 judge 的 task_data 中加入：
"spj_path": "/path/to/spj.py"
没有 SPJ 的题目可以不传，或传 None。
使用注意事项
正式运行必须安装 Docker
runner.py 现在没有 Docker 会返回 System Error。Windows 本地需要 Docker Desktop，Linux 服务器需要 Docker Engine。

C++ 编译和运行都应走 Docker
当前 C++ 在 Docker 中编译为 Linux 可执行文件 main，随后也在 Docker 中运行。不要在 Windows 本地编译 main.exe 后放进 Linux 容器运行。

首次运行需要拉取镜像
需要提前准备：
gcc:13-bookworm
python:3.11-slim

checker.py 里的 SPJ Docker 没有设置 --name，所以如果 SPJ 超时，当前代码只会让 subprocess.run() 超时返回，但不一定能稳定清理 Docker 容器
我在checker中进行了基于uuid的优化,不过我本地没有这个库,将相关代码均打了注释
