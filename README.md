# TCP & UDP Socket Programming

这是一个基于 Python 原生 Socket API 实现的计算机网络传输层与应用层协议设计项目。

本项目由两个独立的子任务构成，分别针对**面向连接的 TCP 协议**与**无连接的 UDP 协议**进行了深度的应用层协议封装与可靠性机制改造。

## 📂 项目结构

```text
├── Task1_TCP/               # 任务一：基于 TCP 的多线程文本逆序传输系统
│   ├── reversetcpserver.py  # TCP 服务端 (支持多线程高并发)
│   ├── reversetcpclient.py  # TCP 客户端 (TLV 长度前缀法防粘包)
│   ├── test.txt             # 任务一专属测试数据源
│   ├── run_log.txt          # 任务一运行日志示例 (带微秒级时间戳)
│   └── readme.txt           # ➡️ 任务一详细配置与运行指南
│
├── Task2_UDP_GBN/           # 任务二：基于 UDP 的可靠数据传输与拥塞控制 (GBN)
│   ├── udpserver.py         # UDP 服务端 (内置丢包与网络延迟模拟器)
│   ├── udpclient.py         # UDP 客户端 (滑动窗口、EWMA RTT 估算、快速重传)
│   ├── test.txt             # 任务二专属测试数据源
│   ├── run_log.txt          # 任务二运行日志示例 (带毫秒级时间戳与拥塞统计)
│   └── readme.txt           # ➡️ 任务二详细配置与运行指南
│
└── test.txt                 # 根目录全局测试文本数据源
