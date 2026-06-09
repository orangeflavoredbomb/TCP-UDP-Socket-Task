import socket 											#导入socket模块
import struct
import sys
import time
import threading
import os
import random
import datetime
import pandas as pd

# ============================ 报文头部封装/解封装 ============================================

def pack_udp_handshake(student_id): # 封装握手报文
    # 异或运算
    encrypted_id = student_id ^ 0x5A3C
    # 打包 Type 1 报文: 2个 unsigned short (共 4 Bytes)
    return struct.pack('!HH', 1, encrypted_id)

def parse_incoming_udp_packet(data): # 解封装服务器响应报文
    if len(data) < 2:
        return None, None
    
    msg_type, = struct.unpack('!H', data[:2])
    
    if msg_type == 2: 
        return msg_type, None
        
    elif msg_type == 4:
        # 解包 Type 4 (6字节)
        _, ack_num = struct.unpack('!HI', data[:6])
        return msg_type, ack_num
    
    return None, None

def pack_sequence_packet(seq_num, text_str): # 封装数据报文
    encoded_data = text_str.encode('ascii')
    length_of_data = len(encoded_data)
    # 打包 10 字节的头部
    header = struct.pack("!HII", 3, seq_num, length_of_data)
    # 拼接真实数据并返回
    return header + encoded_data

def log_print(msg): # 打印函数：既在终端输出，又带上毫秒时间戳写入 run_log.txt
    now = datetime.datetime.now()
    time_str = now.strftime('%H:%M:%S.%f')[:-3] # 保留3位小数
    print(msg)
    with open('run_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"[{time_str}] {msg}\n")

# ============================ GBN 核心状态与锁 ============================================
server_ip = '127.0.0.1'
server_port = 8000

send_base = 1
next_seq_num = 1
window_size = 400        # 400 Bytes
total_packets = 0        # 总包数
TIMEOUT_SEC = 0.3        # 300ms 超时

# 动态计算超时时间
estimated_rtt_ms = None
dev_rtt_ms = None

timer_start_time = 0     # 定时器启动时间
timer_running = False    # 定时器状态
lock = threading.Lock()  # 线程锁

# 快速重传
last_ack_received = 0
dup_ack_count = 0

sndpkt = {} # 存储已发送但未确认的包 (用于超时重传)，格式: {seq_num: 封装好的完整二进制报文}
packet_info = {} # 存储每个包的发送时间和数据范围(开始-结束)，格式: {seq_num: {'send_time': float, 'start': int, 'end': int}}

# Pandas统计
actual_sent_packets = 0  # 实际发送的 UDP 数据包数量
rtt_list = []            # 记录每一次成功 ACK 的 RTT 列表

# ============================ 接收子线程 ============================================

def receive_acks(clientsocket):
    global send_base, timer_running, timer_start_time, packet_info, rtt_list, actual_sent_packets
    global TIMEOUT_SEC, estimated_rtt_ms, dev_rtt_ms # 动态超时时间
    global last_ack_received, dup_ack_count # 快速重传

    while send_base <= total_packets:
        try:
            data, _ = clientsocket.recvfrom(1024)
            msg_type, ack_num = parse_incoming_udp_packet(data)
            
            if msg_type == 4:
                with lock:
                    # 累积确认：只有当 ACK 的序号大于等于当前 base 时才有效
                    if ack_num >= send_base:
                        for i in range(send_base, ack_num + 1):
                            # 计算单包 RTT
                            rtt_ms = (time.time() - packet_info[i]['send_time']) * 1000
                            rtt_list.append(rtt_ms) # pd统计

                            start_b = packet_info[i]['start']
                            end_b = packet_info[i]['end']
                            log_print(f"<- [ACK 收到] 第 {i} 个（第 {start_b}~{end_b} 共 {end_b - start_b + 1} 字节）server 端已经收到，RTT 是 {rtt_ms:.2f} ms")

                            # 快速重传
                            last_ack_received = ack_num
                            dup_ack_count = 0 # 无冗余ACK

                            # ================== 动态超时时间 ==================
                            if estimated_rtt_ms is None: # 第一次算
                                estimated_rtt_ms = rtt_ms
                                dev_rtt_ms = rtt_ms / 2.0 # TCP官方标准文档 RFC 6298 规定
                            else:
                                alpha = 0.125
                                beta = 0.25
                                estimated_rtt_ms = (1 - alpha) * estimated_rtt_ms + alpha * rtt_ms
                                dev_rtt_ms = (1 - beta) * dev_rtt_ms + beta * abs(rtt_ms - estimated_rtt_ms)

                            # 算出新的超时时间 (ms)
                            new_timeout_ms = estimated_rtt_ms + 4 * dev_rtt_ms
                            # 转换为秒更新给全局变量，为了防止网络极好时算出接近0的超时导致无限重传，设置一个 0.05s (50ms) 的下限
                            TIMEOUT_SEC = max(0.05, new_timeout_ms / 1000.0)

                        log_print(f"      [*] 动态更新 Timeout: 变为 {TIMEOUT_SEC*1000:.2f} ms (EstRTT={estimated_rtt_ms:.2f}, DevRTT={dev_rtt_ms:.2f})")
                        # =================================================

                        #print(f"<- [ACK 收到] 累计确认 Seq={ack_num}，窗口向前滑动")
                        send_base = ack_num + 1
                        
                        # 收到确认后，判断定时器去留
                        if send_base == next_seq_num: # 窗口中全部收到确认
                            timer_running = False  # 关停定时器
                        else:
                            timer_start_time = time.time() # 还有没确认的，重启定时器

                    # ==========================================================
                    # 【快速重传策略开关】
                    # 默认启用 策略A（单包重传）。如需测试全窗口重传的拥塞崩溃现象，
                    # 可注释掉策略A，并解除 策略B 的注释。(ctrl+l)
                    # ==========================================================

                    # --- 策略 A：单包快速重传 (当前启用) ---
                    elif ack_num == send_base - 1:
                        # 收到冗余ACK
                        dup_ack_count += 1
                        log_print(f"      [*] 收到冗余 ACK {ack_num}，当前计数: {dup_ack_count}")
                        
                        if dup_ack_count == 3:
                            log_print(f"[快速重传] 连续3次收到 ACK {ack_num}，瞬间重传 Seq={send_base} ！")
                            # 重置发送时间
                            packet_info[send_base]['send_time'] = time.time()
                            # 瞬间单发这一个包
                            clientsocket.sendto(sndpkt[send_base], (server_ip, server_port))
                            actual_sent_packets += 1 
                            # 快速重传后清零防止重复触发
                            dup_ack_count = 0

                    # # --- 策略 B：全窗口快速重传 (备用/对比测试) ---
                    # elif ack_num == send_base - 1:
                    #     # 收到冗余ACK
                    #     dup_ack_count += 1
                    #     log_print(f"      [*] 收到冗余 ACK {ack_num}，当前计数: {dup_ack_count}")
                        
                    #     if dup_ack_count == 3:
                    #         log_print(f"\n[快速重传] 连续3次收到 ACK {ack_num}，瞬间重传整个窗口 (Seq={send_base} 到 {next_seq_num-1}) ！")
                            
                    #         # 遍历当前在途的所有包，全部重新发射
                    #         for i in range(send_base, next_seq_num):
                    #             # 重置发送时间，防止下一次收到 ACK 时 RTT 计算异常
                    #             packet_info[i]['send_time'] = time.time()
                    #             clientsocket.sendto(sndpkt[i], (server_ip, server_port))
                                
                    #             actual_sent_packets += 1 
                                
                    #             start_b = packet_info[i]['start']
                    #             end_b = packet_info[i]['end']
                    #             log_print(f"-> [快速重传] 重传第 {i} 个（第 {start_b}~{end_b} 字节）数据包")

                    #         # 快速重传后清零防止重复触发
                    #         dup_ack_count = 0
                    #         log_print("") # 打印空行方便观察
                    # ==========================================================

        except socket.timeout:
            # 为了防止死锁
            continue

# ============================ 主函数 ============================================

def main():
    global send_base, next_seq_num, total_packets, timer_running, timer_start_time
    global TIMEOUT_SEC, sndpkt, packet_info, actual_sent_packets
    global server_ip, server_port

    # --- 默认配置 ---
    server_ip = '127.0.0.1'
    server_port = 8000

    # ==================== 命令行参数解析 =====================
    # 期望格式: python udpclient.py <ServerIP> <ServerPort>
    if len(sys.argv) == 3:
        server_ip = sys.argv[1]
        try: 
            server_port = int(sys.argv[2])
        except ValueError:
            print("[-] 错误：端口必须是整数！")
            return
    elif len(sys.argv) > 1:
        print("[-] 命令行参数数量错误！")
        print("[-] 用法: python3 udpclient.py <ServerIP> <ServerPort>")
        return
    else:
        print("[*] 提示: 未指定参数，采用默认连接 127.0.0.1:8000")
    # ========================================================

    # 每次运行前清空旧日志
    with open('run_log.txt', 'w', encoding='utf-8') as f:
        f.write("=== UDP GBN Client Run Log ===\n")

    # ============ 0) 读取文件并动态随机切块 ============ 
    file_path = 'test.txt'
    if not os.path.exists(file_path):
        print(f"Error: 找不到文件 {file_path}")
        return
    with open(file_path, 'r', encoding='ascii') as f:
        file_content = f.read()
    
    random.seed(42)

    chunks = []
    current_index = 0
    file_len = len(file_content)
    
    # 存储每个包的真实字节边界，格式: {seq_num: (start, end)} (int: tuple(int,int))
    packet_bounds = {} 
    pkt_id = 1

    while current_index < file_len:
        # 随机决定当前块的大小
        current_chunk_size = random.randint(40, 80)
        chunk_data = file_content[current_index : current_index + current_chunk_size]
        
        chunks.append(chunk_data)
        
        # 计算并记录当前包的绝对字节流边界 (1-based)
        start_byte = current_index + 1
        end_byte = current_index + len(chunk_data)
        packet_bounds[pkt_id] = (start_byte, end_byte)
        
        current_index += len(chunk_data)
        pkt_id += 1

    total_packets = len(chunks)
    log_print(f"[*] 文件读取完毕，总大小 {file_len} 字节。")
    log_print(f"[*] 采用[40,80]字节动态随机切片，共分为 {total_packets} 个数据包。")


    # 创建 UDP Socket
    clientsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 	#创建客户机socket
   
    # 初始超时时间为 300ms
    clientsocket.settimeout(TIMEOUT_SEC)

    # ============ 1) 握手阶段 ============
    max_retries = 5  # 设置最大重试次数
    retry_count = 0  # 当前重试计数

    while retry_count < max_retries:
        log_print(f"-> 正在发送握手请求 (尝试 {retry_count + 1}/{max_retries}) ...")
        clientsocket.sendto(pack_udp_handshake(2624), (server_ip, server_port))

        try:
            # 乖乖等待 300ms
            response, _ = clientsocket.recvfrom(1024)
            msg_type, _ = parse_incoming_udp_packet(response)
            if msg_type == 2:
                log_print("[+] 握手成功！准备进入 GBN 传输阶段。\n")
                break
        except socket.timeout:
            retry_count += 1
            log_print("[-] 握手超时，重试中...")

    # 退出循环后，检查是否是因为重试耗尽而退出
    if retry_count >= max_retries:
        log_print("[!] 致命错误：连续握手失败，服务器无响应。客户端已自动退出。")
        clientsocket.close()
        return # 直接结束程序，不进入后续逻辑
            
    # ============ 2) GBN 传输阶段 ============
    # 开始传输的绝对时间戳
    transfer_start_time = time.time()

    # 启动专门负责接收 ACK 的子线程
    recv_thread = threading.Thread(target=receive_acks, args=(clientsocket,))
    recv_thread.start()

    # 发送流水线主循环
    while send_base <= total_packets:
        with lock:
            # 1. [发送新包] 检查窗口是否有空余，且还有数据没发完
            while next_seq_num <= total_packets:
                # 【新增】动态计算当前窗口里“正在飞 (未被 ACK)”的字节总数
                bytes_in_flight = 0
                for i in range(send_base, next_seq_num):
                    bytes_in_flight += (packet_bounds[i][1] - packet_bounds[i][0] + 1)
                
                # 看看如果强行加上准备发的下一个包，会不会撑爆400字节的物理窗口？
                next_chunk_size = len(chunks[next_seq_num - 1])
                if bytes_in_flight + next_chunk_size > window_size:
                    break  # 窗口满了！强行刹车跳出循环，等收到 ACK 腾出空间再发

                # 获取真实文本块 (注意数组下标从0开始，而序号从1开始)
                chunk_data = chunks[next_seq_num - 1]
                
                # 计算这个包的字节边界 x 和 y
                start_byte, end_byte = packet_bounds[next_seq_num]
                
                # 记录到字典中
                packet_info[next_seq_num] = {
                    'start': start_byte, 
                    'end': end_byte, 
                    'send_time': time.time()
                }

                # 封装并缓存
                packet = pack_sequence_packet(next_seq_num, chunk_data)
                sndpkt[next_seq_num] = packet
                
                # 发送
                clientsocket.sendto(packet, (server_ip, server_port))
                actual_sent_packets += 1

                #print(f"-> [发送新包] Seq={next_seq_num}, DataLen={len(chunk_data)}")
                log_print(f"-> [发送新包] 第 {next_seq_num} 个（第 {start_byte}~{end_byte} 共 {len(chunk_data)} 字节）client 端已经发送")

                # 如果是窗口中的第一个包，启动定时器
                if send_base == next_seq_num:
                    timer_start_time = time.time()
                    timer_running = True
                
                next_seq_num += 1

            # 2. [超时重传] 检查定时器是否超时
            if timer_running and (time.time() - timer_start_time) >= TIMEOUT_SEC:
                log_print(f"\n[!!!] 触发超时！等待 {TIMEOUT_SEC:.2f}s 未收到 ACK {send_base}，开始 Go-Back-N 重传")
                
                timer_start_time = time.time() # 重新启动定时器

                # 暴力回退：将 send_base 到 next_seq_num-1 的所有包全部重发
                for i in range(send_base, next_seq_num):
                    packet_info[i]['send_time'] = time.time() # 更新发送时间
                    clientsocket.sendto(sndpkt[i], (server_ip, server_port))
                    actual_sent_packets += 1

                    #print(f"-> [重发] Seq={i}")
                    start_b, end_b = packet_bounds[i]
                    log_print(f"-> [重发] 重传第 {i} 个（第 {start_b}~{end_b} 字节）数据包")

                log_print("") # 打印空行方便观察
        
        # 释放锁，稍微睡一会儿，把 CPU 执行权让给接收线程
        time.sleep(0.01)

    # ============ 3) 收尾与Pandas统计 ============ 
    # 等待接收线程自然结束（当 send_base > total_packets 时，子线程循环会退出）
    recv_thread.join()
    total_transfer_time = time.time() - transfer_start_time # 传输总用时
    log_print("\n[+] 所有文件数据均已成功发送并获得 ACK 确认！客户端关闭。")

    log_print("\n================= 【传输汇总】 =================")
    log_print(f"传输总用时: {total_transfer_time:.3f} 秒")

    # 吞吐量 = 文件总字节数 / 总用时 (单位: 字节/秒，或者 KB/s)
    throughput = (file_len / total_transfer_time) / 1024.0 if total_transfer_time > 0 else 0
    log_print(f"有效网络吞吐量: {throughput:.2f} KB/s")

    # 丢包率 (1 - 原定发包数/实际发包总数)
    loss_rate = (1 - (total_packets / actual_sent_packets)) * 100 if actual_sent_packets > 0 else 0
    log_print(f"原定包数: {total_packets} | 实际发送包数 (含重传): {actual_sent_packets}")
    log_print(f"丢包率: {loss_rate:.2f}% ")
    
    # 计算统计量
    if rtt_list:
        df = pd.Series(rtt_list)
        log_print(f"最大RTT: {df.max():.2f} ms")
        log_print(f"最小RTT: {df.min():.2f} ms")
        log_print(f"平均RTT: {df.mean():.2f} ms")
        log_print(f"RTT的标准差: {df.std():.2f} ms")
    log_print("================================================\n")

    clientsocket.close() #关闭客户机socket


if __name__ == '__main__':
    main()

