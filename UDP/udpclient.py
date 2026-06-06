import socket 											#导入socket模块
import struct
import sys
import time
import threading
import os
import random

# ============================ 报文头部封装/解封装 ============================================
def pack_udp_handshake(student_id): # 封装握手报文
    # 异或运算
    encrypted_id = student_id ^ 0x5A3C
    # 打包 Type 1 报文: 2个 unsigned short (共 4 Bytes)
    # ! 代表网络字节序，H 代表 2 字节无符号整数
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

# ============================ GBN 核心状态与锁 ============================================
send_base = 1
next_seq_num = 1
window_size = 5          # 400字节窗口 / 80字节单包 = 5个包
total_packets = 0        # 总包数
TIMEOUT_SEC = 0.3        # 300ms 超时

timer_start_time = 0     # 定时器启动时间
timer_running = False    # 定时器状态
lock = threading.Lock()  # 线程锁

# 存储已发送但未确认的包 (用于超时重传)
# 格式: {seq_num: 封装好的完整二进制报文}
sndpkt = {}
packet_info = {} # 存储每个包的发送时间和数据范围(开始-结束)，格式: {seq_num: {'send_time': float, 'start': int, 'end': int}}

# ============================ 接收子线程 ============================================
def receive_acks(clientsocket):
    global send_base, timer_running, timer_start_time
    
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
                            start_b = packet_info[i]['start']
                            end_b = packet_info[i]['end']
                            print(f"<- [ACK 收到] 第 {i} 个（第 {start_b}~{end_b} 共 {end_b - start_b + 1} 字节）server 端已经收到，RTT 是 {rtt_ms:.2f} ms")

                        #print(f"<- [ACK 收到] 累计确认 Seq={ack_num}，窗口向前滑动")
                        send_base = ack_num + 1
                        
                        # 收到确认后，判断定时器去留
                        if send_base == next_seq_num: # 窗口中全部收到确认
                            timer_running = False  # 关停定时器
                        else:
                            timer_start_time = time.time() # 还有没确认的，重启定时器
        except socket.timeout:
            # 为了防止死锁即可
            continue

# ============================ 主函数 ============================================

def main():
    global send_base, next_seq_num, total_packets, timer_running, \
        timer_start_time, TIMEOUT_SEC, sndpkt

    # 模拟命令行参数 (IP, Port)
    server_ip = '127.0.0.1'
    server_port = 8000
    file_path = 'test.txt'  # 待发送的文本文件路径

    # 读取文件并切块（每块 80 字节）
    if not os.path.exists(file_path):
        print(f"Error: 找不到文件 {file_path}")
        return
    with open(file_path, 'r', encoding='ascii') as f:
        file_content = f.read()
        
    chunk_size = 80
    # 将字符串按 80 字节切块
    chunks = [file_content[i:i+chunk_size] for i in range(0, len(file_content), chunk_size)]
    total_packets = len(chunks)
    print(f"[*] 文件读取完毕，总大小 {len(file_content)} 字节，分为 {total_packets} 个包。")
    
    # 创建 UDP Socket
    clientsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 	#创建客户机socket
   
    # 超时时间为 300ms
    clientsocket.settimeout(TIMEOUT_SEC)

    # ============ 1) 握手阶段 ============
    while True:
        print("-> 正在发送握手请求...")
        clientsocket.sendto(pack_udp_handshake(2624), (server_ip, server_port))

        try:
            # 乖乖等待 300ms
            response, _ = clientsocket.recvfrom(1024)
            msg_type, _ = parse_incoming_udp_packet(response)
            if msg_type == 2:
                print("[+] 握手成功！准备进入 GBN 传输阶段。\n")
                break
        except socket.timeout:
            print("[-] 握手超时，重试中...")
            
    # ============ 2) GBN 传输阶段 ============
    # 更改 socket 超时时间。设短一点（如0.05秒），这样 recv_thread 可以频繁检查循环条件
    clientsocket.settimeout(0.05) 
    
    # 启动专门负责接收 ACK 的子线程
    recv_thread = threading.Thread(target=receive_acks, args=(clientsocket,))
    recv_thread.start()

    # 发送流水线主循环
    while send_base <= total_packets:
        with lock:
            # 1. 检查窗口是否有空余，且还有数据没发完
            while next_seq_num < send_base + window_size and next_seq_num <= total_packets:
                # 获取真实文本块 (注意数组下标从0开始，而序号从1开始)
                chunk_data = chunks[next_seq_num - 1]
                
                # 计算这个包的字节边界 x 和 y
                start_byte = (next_seq_num - 1) * chunk_size + 1
                end_byte = start_byte + len(chunk_data) - 1
                
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
                #print(f"-> [发送新包] Seq={next_seq_num}, DataLen={len(chunk_data)}")
                print(f"-> [发送新包] 第 {next_seq_num} 个（第 {start_byte}~{end_byte} 共 {len(chunk_data)} 字节）client 端已经发送")

                # 如果是窗口中的第一个包，启动定时器
                if send_base == next_seq_num:
                    timer_start_time = time.time()
                    timer_running = True
                
                next_seq_num += 1

            # 2. 检查定时器是否超时
            if timer_running and (time.time() - timer_start_time) >= TIMEOUT_SEC:
                print(f"\n[!!!] 触发超时！等待 {TIMEOUT_SEC}s 未收到 ACK {send_base}，开始 Go-Back-N 重传")
                # 重新启动定时器
                timer_start_time = time.time()
                # 暴力回退：将 send_base 到 next_seq_num-1 的所有包全部重发
                for i in range(send_base, next_seq_num):
                    packet_info[i]['send_time'] = time.time() # 更新发送时间
                    clientsocket.sendto(sndpkt[i], (server_ip, server_port))
                    #print(f"-> [重发] Seq={i}")
                    start_b = packet_info[i]['start']
                    end_b = packet_info[i]['end']
                    print(f"-> [重发] 重传第 {i} 个（第 {start_b}~{end_b} 字节）数据包")

                print() # 打印空行方便观察
        
        # 释放锁，稍微睡一会儿，把 CPU 执行权让给接收线程
        time.sleep(0.01)

    # 3) 传输完成，等待接收线程结束
    # 等待接收线程自然结束（当 send_base > total_packets 时，子线程循环会退出）
    recv_thread.join()
    print("\n[+] 所有文件数据均已成功发送并获得 ACK 确认！客户端关闭。")

    clientsocket.close() #关闭客户机socket


if __name__ == '__main__':
    main()

