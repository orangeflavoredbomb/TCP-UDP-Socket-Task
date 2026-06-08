======================================================================
Task 1: TCP Reverse Client & Server (TCP 文本反转传输程序)
======================================================================

【1. 运行环境说明】
- 操作系统：Windows / macOS / Linux 均可
- 解释器：Python 3.x (推荐 3.6 及以上版本)
- 依赖库：仅使用 Python 标准库 (socket, struct, threading, random, os, datetime, sys)，无需安装任何第三方库。

【2. 文件结构】
- reversetcpserver.py : 服务器端代码，支持多线程并发处理多个客户端请求。
- reversetcpclient.py : 客户端代码，负责读取文件、随机分块、打包发送及拼装反转结果。
- test.txt            : 待发送的原始文本文件（需用户自行创建，要求为纯英文 ASCII 编码）。
- reversed_test.txt   : 运行结束后，由客户端自动生成的整体反转后的结果文件。
- run_log.txt         : 运行结束后，由客户端自动生成的带微秒级时间戳的报文收发日志（用于与 Wireshark 对齐）。

【3. 配置选项】
本程序的 Server 与 Client 均严格支持通过命令行动态传入核心网络参数。
在未提供命令行参数时，将启用以下默认安全测试值：
- Server 默认监听 : IP = 127.0.0.1, Port = 8000     
- Client 默认连接 : IP = 127.0.0.1, Port = 8000     
- Client 默认分块 : Lmin = 50, Lmax = 100           
变量名与对应默认值如下：
- server_ip   = '127.0.0.1'  # 服务器 IP 地址（默认本地环回）
- server_port = 8000         # 默认服务器监听端口，可选[1024-49151]
- l_min       = 50           # 默认随机分块最小字节
- l_max       = 100          # 默认随机分块最大字节
- file_path   = 'test.txt'   # 待读取的目标文件路径 (源码内固定)
- seed_val    = 42           # 随机数种子 (源码内固定以保证可复现性)

【4. 详细运行步骤】
步骤一：环境准备
请确保当前目录下存在名为 `test.txt` 的纯英文文本文件。如没有，请新建一个并随意输入一段英文文本（例如一段歌词或文章）。

步骤二：启动服务器
打开命令行终端，进入当前代码目录，运行以下命令启动 Server：
> python reversetcpserver.py <ListenIP> <ListenPort>
 （macOS端请输入：python3 reversetcpserver.py <ListenIP> <ListenPort>）
示例：
> python3 reversetcpserver.py 127.0.0.1 8000
(注：若不加参数，直接回车即可使用默认配置启动)
成功启动后，控制台会输出：“TCP Reverse Server 已启动，等待连接...”

步骤三：启动客户端
另开一个新的命令行终端，进入当前代码目录，按以下完整格式启动 Client：
> python reversetcpclient.py <ServerIP> <ServerPort> <Lmin> <Lmax>
  (macOS端请输入：python3 reversetcpclient.py <ServerIP> <ServerPort> <Lmin> <Lmax>)
示例：
> python3 reversetcpclient.py 127.0.0.1 8000 50 100
(注：若不加参数，直接回车即可使用默认配置启动)
成功连接后，客户端控制台会实时打印出握手进度、动态分块信息、发送与接收的交互过程。

步骤四：查看结果
1. 客户端显示“所有数据处理完毕”后，会自动退出。此时可在当前目录下找到 `reversed_test.txt` 文件，里面即为逆序拼接好的最终文本。
2. 打开 `run_log.txt`，可查看带精确时间戳的四种 Type 报文交互记录。

【5. 高阶拓展：跨电脑（局域网真实的双机）通信】
如果您希望她人的电脑作为 Client 连接到您的 Server，请按以下步骤操作：

1. Server 换地址：
   在您的电脑上启动 Server 时，将监听 IP 设置为 `0.0.0.0`（代表监听所有网卡，允许局域网内的设备连入）：
   > python3 reversetcpserver.py 0.0.0.0 8000

2. 查您的局域网 IP：
   保持您的电脑连接在校园网/同一 WiFi 下。打开新终端，输入 `ipconfig` (Windows) 或 `ifconfig` (macOS/Linux)，查到您的真实局域网 IP（例如 192.168.1.100）。

3. 她的 Client 发起连接：
   让她在电脑上敲入命令，将目的地 IP 替换为您查到的 IP：
   > python3 reversetcpclient.py 192.168.1.100 8000 <Lmin> <Lmax>

此时，数据块将真正地跨越物理无线网络/网线，在两台真实的计算机之间完成协议握手与并发的反转传输！
======================================================================