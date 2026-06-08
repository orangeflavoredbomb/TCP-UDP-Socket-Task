import socket                     				#导入socket模块
import struct
import random
import os
import datetime
import sys

# ============================ 报文头部封装/解封装============================================
# 1. 封装 Initialization 报文 (Type 1)
def pack_init_packet(n_blocks):
    return struct.pack('!HI', 1, n_blocks)

# 2. 封装 reverseRequest 报文 (Type 3)
def pack_request_packet(text_str):
    encoded_text = text_str.encode('ascii')
    data_length = len(encoded_text)
    header = struct.pack('!HI', 3, data_length)
    return header + encoded_text

# 3. 解析接收到的报文（通用的解析逻辑）
def receive_packet(sock):
    # 先读取 2 字节，解析出 Type
    type_bytes = sock.recv(2)
    if not type_bytes:
        return None, None
    msg_type, = struct.unpack('!H', type_bytes)
    
    if msg_type == 2:
        # Type1(agree报文): 没有后续内容
        return msg_type, None
        
    elif msg_type == 4:
        # Type3(reverseAnswer报文): 接下来还有 4 字节的长度
        len_bytes = sock.recv(4)
        data_len, = struct.unpack('!I', len_bytes)
        # 根据长度，读取对应大小的真实数据
        data_bytes = sock.recv(data_len)
        return msg_type, data_bytes.decode('ascii')
        
    return msg_type, None

# ============================ 文件随机分块 ============================================
def prepare_file_chunks(file_path, l_min, l_max, seed_val):
    """
    读取文件，并根据指定的 Lmin, Lmax 和 seed 进行随机分块
    返回：完整的文件内容(字符串), 每一块的大小列表, 块数 N
    """
    # 1. 设定随机数种子，保证每次测试分块结果一致
    random.seed(seed_val)
    
    # 2. 读取 ASCII 文件内容
    if not os.path.exists(file_path):
        print(f"文件 {file_path} 不存在！")
        return None, None, 0
        
    with open(file_path, 'r', encoding='ascii') as f:
        file_content = f.read()
        
    total_size = len(file_content)
    chunk_sizes = []
    current_sum = 0
    
    # 3. 核心切片逻辑
    while current_sum < total_size:
        remaining_size = total_size - current_sum
        
        # 随机生成一个切片大小
        step = random.randint(l_min, l_max)
        
        if remaining_size <= step:
            # 剩余大小不够或刚好等于 step，这就是最后一块
            chunk_sizes.append(remaining_size)
            break # 累加结束
        else:
            # 正常分块
            chunk_sizes.append(step)
            current_sum += step
            
    # 4. 计算 N（就是切片数组的长度）
    n_blocks = len(chunk_sizes)
    
    return file_content, chunk_sizes, n_blocks

# =========================== 日志记录工具 ==================================
def log_event(action, msg_type, detail=""):
    """
    action: "Send" 或 "Receive"
    msg_type: 报文的 Type (1, 2, 3, 4)
    detail: 附加信息（比如块数、长度等）
    """
    now = datetime.datetime.now()
    # %f 会输出 6 位微秒，我们用 [:-3] 截取前 3 位变成毫秒，与 Wireshark 更好对齐
    time_str = now.strftime('%H:%M:%S.%f')[:-1] # 3位太少了，改成5位
    
    log_line = f"[{time_str}] {action} | Type: {msg_type} | {detail}\n"
    
    # 用追加模式 ('a') 写入文件
    with open('run_log.txt', 'a', encoding='utf-8') as f:
        f.write(log_line)

# ============================ 核心主流程 ===========================================
def main():
    # --- 默认配置 ---
    server_ip = '127.0.0.1'
    server_port = 8000
    file_path = 'test.txt'  
    seed_val = 42
    l_min = 50
    l_max = 100

    # ==================== 命令行参数解析 ====================
    # 期望格式: python reversetcpclient.py <IP> <Port> <Lmin> <Lmax>
    if len(sys.argv) == 5:
        server_ip = sys.argv[1] # sys.argv[0] 是脚本名本身，sys.argv[1] 是第一个参数，以此类推
        try:
            server_port = int(sys.argv[2])
            l_min = int(sys.argv[3])
            l_max = int(sys.argv[4])
        except ValueError:
            print("[-] 错误：端口、Lmin 和 Lmax 必须是有效的整数！")
            print("示例: python3 reversetcpclient.py 127.0.0.1 8000 50 100")
            return
    elif len(sys.argv) > 1:
        # 如果带了参数但数量不对（比如只输了2个），给予提示并退出，防止误操作
        print("[-] 命令行参数数量错误！")
        print("用法: python3 reversetcpclient.py <ServerIP> <ServerPort> <Lmin> <Lmax>")
        print("示例: python3 reversetcpclient.py 127.0.0.1 8000 50 100")
        return
    else:
        # 一个参数都没带，静默使用默认值（方便你本地平时点击运行测试）
        print("[*] 用法提示: python3 reversetcpclient.py <ServerIP> <ServerPort> <Lmin> <Lmax>")
        print("[*] 未检测到命令行参数，采用默认配置: IP=127.0.0.1, Port=8000, Lmin=50, Lmax=100\n")
    # ========================================================
  
    print("[1] 正在读取并计算文件分块...")
    file_content, chunk_sizes, n_blocks = prepare_file_chunks(file_path, l_min, l_max, seed_val)

    if file_content is None:
        print(f"[-] 错误：由于无法读取文件 '{file_path}'，客户端被迫终止。")
        return 
    
    print(f"文件总大小: {len(file_content)} Bytes, 将分为 {n_blocks} 块发送。")

    print("[2] 正在连接服务器...")
    # 每次运行前，先清空/初始化日志文件
    with open('run_log.txt', 'w', encoding='utf-8') as f:
        f.write("=== TCP Reverse Client Run Log ===\n")
       
    clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #创建客户机socket
    clientsocket.connect((server_ip, server_port)) #连接到服务器

    # 第一步：发送 Init 报文 (Type=1)
    clientsocket.send(pack_init_packet(n_blocks))
    log_event("Send", 1, f"N={n_blocks}")
    print(f"-> 发送 Initialization 报文, N={n_blocks}")

    # 第二步：接收 agree 报文 (Type=2)
    msg_type, _ = receive_packet(clientsocket)
    log_event("Received", msg_type)
    if msg_type != 2:
        print("Error: 握手失败，未收到 agree 报文！")
        clientsocket.close()
        return
    print("<- 收到 agree 报文，允许发送。\n")

    # 第三步：循环发送 request (Type=3) 并接收 answer (Type=4)
    current_index = 0
    final_reversed_text = ""

    for i, size in enumerate(chunk_sizes):
        # 截取这一块的文本：切片
        chunk_text = file_content[current_index : current_index + size]
        
        # 发送
        clientsocket.send(pack_request_packet(chunk_text))
        log_event("Send", 3, f"Block {i+1}, Length: {size}")
        print(f"-> 发送第 {i+1} 块数据 ({size} 字节)")

        # 接收
        recv_type, reversed_data = receive_packet(clientsocket)
        log_event("Receive", recv_type, f"Block {i+1}")

        if recv_type == 4:
            print(f"第 {i+1} 块: 反转的文本: {reversed_data}")
            final_reversed_text = reversed_data + final_reversed_text # 整体全部反转
        
        # 游标向前推进
        current_index += size

    # 第四步：保存最终结果文件
    output_file = "reversed_" + file_path
    with open(output_file, 'w', encoding='ascii') as f:
        f.write(final_reversed_text)
    print(f"\n[4] 所有数据处理完毕！结果已保存至 {output_file}")

    # 关闭连接
    clientsocket.close() #关闭客户机socket

if __name__ == '__main__':
    main()

