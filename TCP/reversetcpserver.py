import socket                   		#导入socket模块
import threading                	#导入threading模块
import struct

# ============================ 报文头部封装/解封装 ============================================
# 1. 封装 agree 报文 (Type 2)
def pack_agree_packet():
    return struct.pack('!H', 2)

# 2. 封装 reverseAnswer 报文 (Type 4)
def pack_answer_packet(reversed_str):
    encoded_text = reversed_str.encode('ascii')
    data_length = len(encoded_text)
    header = struct.pack('!HI', 4, data_length)
    return header + encoded_text

# 3. 服务器端的接收与解析逻辑
def parse_incoming_packet(clientsocket):
    # 先读 2 字节判定类型
    type_bytes = clientsocket.recv(2)
    if not type_bytes:
        return None, None
    msg_type, = struct.unpack('!H', type_bytes)
    
    if msg_type == 1:
        # Initialization 报文：后面还有 4 字节代表块数 N
        n_bytes = clientsocket.recv(4)
        n_blocks, = struct.unpack('!I', n_bytes)
        return msg_type, n_blocks
        
    elif msg_type == 3:
        # reverseRequest 报文：后面有 4 字节长度 + 变长数据
        len_bytes = clientsocket.recv(4)
        data_len, = struct.unpack('!I', len_bytes)
        data_bytes = clientsocket.recv(data_len)
        return msg_type, data_bytes.decode('ascii')
        
    return msg_type, None

# ============================ 核心函数 ============================================

#让服务器能同时处理多个客户端（并行，多线程）
def handle_client(clientsocket, clientaddress):
    print(f'\n[+] 客户端已连接: {clientaddress}')
    
    try:
        # ---------------- 第一步：等待握手 (Type 1) ----------------
        msg_type, n_blocks = parse_incoming_packet(clientsocket)
        if msg_type != 1:
            print(f"[-] {clientaddress} 握手失败，收到的不是 Init 报文 (Type={msg_type})")
            return  # 退出这个线程，断开该客户端连接
            
        print(f"[*] 收到 Initialization 报文，客户端准备发送 {n_blocks} 块数据。")

        # ---------------- 第二步：同意接收 (Type 2) ----------------
        clientsocket.send(pack_agree_packet())
        print(f"[*] 已回复 agree 报文。等待接收数据...")

        # ---------------- 第三步 & 第四步：循环接收与反转 ----------------
        # 循环n_blocks次即可
        for i in range(n_blocks):
            msg_type, data_text = parse_incoming_packet(clientsocket)
            
            if msg_type != 3:
                print(f"[-] 数据传输中断，期待 Type=3，实际收到 Type={msg_type}")
                break
                
            print(f" -> 收到第 {i+1}/{n_blocks} 块: {data_text}")
            
            # 核心要求：反转字符串 (Python切片语法)
            reversed_text = data_text[::-1]
            
            # 封装成 Type 4 发送回去
            clientsocket.send(pack_answer_packet(reversed_text))
            print(f" <- 发送反转结果: {reversed_text}")

        print(f"[*] 客户端 {clientaddress} 的 {n_blocks} 块数据处理完毕！")

    except Exception as e:
        print(f"[-] 与 {clientaddress} 通信时发生异常: {e}")

    finally:
        clientsocket.close()
        print(f'[-] 客户端连接已关闭: {clientaddress}\n')


# ============================ 服务器启动代码 ============================================

serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #创建服务器socket（IPv4、TCP套接字）
serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #允许端口复用

serversocket.bind(('127.0.0.1', 8000)) 
serversocket.listen(5)             			
print("=======================================")
print("  TCP Reverse Server 已启动，等待连接...  ")
print("=======================================")

serversocket.settimeout(1.0) # 设置1秒超时

try:
    while True:
        try:
            clientsocket, clientaddress = serversocket.accept()
            # 为每个客户端创建一个新线程
            client_thread = threading.Thread(target=handle_client, args=(clientsocket, clientaddress))
            # 设置为守护线程：主线程结束时，子线程也会跟着结束
            client_thread.daemon = True 
            client_thread.start()
        except socket.timeout: # 超时后继续循环，这时可以响应 Ctrl+C
            continue
except KeyboardInterrupt:
    print("\n[信号] 检测到中断，服务器正在关闭...")
finally:
    serversocket.close()
    print("服务器已关闭。")

