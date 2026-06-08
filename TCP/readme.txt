======================================================================
Task 1: TCP Reverse Client & Server (TCP 文本反转传输程序)
======================================================================

【1. 运行环境说明】
- 操作系统：Windows / macOS / Linux 均可
- 解释器：Python 3.x (推荐 3.6 及以上版本)
- 依赖库：仅使用 Python 标准库 (socket, struct, threading, random, os, datetime 等)，无需安装任何第三方库。

【2. 文件结构】
- reversetcpserver.py : 服务器端代码，支持多线程并发处理多个客户端请求。
- reversetcpclient.py : 客户端代码，负责读取文件、随机分块、打包发送及拼装反转结果。
- test.txt            : 待发送的原始文本文件（需用户自行创建，要求为纯英文 ASCII 编码）。
- reversed_test.txt   : 运行结束后，由客户端自动生成的整体反转后的结果文件。
- run_log.txt         : 运行结束后，由客户端自动生成的带微秒级时间戳的报文收发日志（用于与 Wireshark 对齐）。

【3. 配置选项（可在 reversetcpclient.py 源码 main 函数中修改）】
- server_ip   = '127.0.0.1'  # 服务器 IP 地址（默认本地环回）
- server_port = 8000         # 服务器监听端口，可选[1024-49151]
- file_path   = 'test.txt'   # 待读取的目标文件路径
- l_min       = 50           # 随机分块的最小字节数(命令行输入，默认50)
- l_max       = 100          # 随机分块的最大字节数(命令行输入，默认100)
- seed_val    = 42           # 随机数种子（固定种子以保证测试结果的可复现性）

【4. 详细运行步骤】
步骤一：环境准备
请确保当前目录下存在名为 `test.txt` 的纯英文文本文件。如没有，请新建一个并随意输入一段英文文本（例如一段歌词或文章）。

步骤二：启动服务器
打开命令行终端，进入当前代码目录，运行以下命令启动 Server：
> python reversetcpserver.py
macOS端请输入：
> python3 reversetcpserver.py
成功启动后，控制台会输出：“TCP Reverse Server 已启动，等待连接...”

步骤三：启动客户端
另开一个新的命令行终端，进入当前代码目录，运行以下命令启动 Client：
> python reversetcpclient.py <Lmin> <Lmax>
macOS端请输入：
> python3 reversetcpclient.py <Lmin> <Lmax>
示例: python3 reversetcpclient.py 50 100，若未检测到命令行参数，将采用默认值 Lmin=50, Lmax=100
成功连接后，客户端控制台会实时打印出握手进度、动态分块信息、发送与接收的交互过程。

步骤四：查看结果
1. 客户端显示“所有数据处理完毕”后，会自动退出。此时可在当前目录下找到 `reversed_test.txt` 文件，里面即为逆序拼接好的最终文本。
2. 打开 `run_log.txt`，可查看带精确时间戳的四种 Type 报文交互记录。

