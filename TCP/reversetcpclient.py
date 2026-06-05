import socket                     				#导入socket模块
import struct
import random
import os

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
# 因为客户端要接收 Type 2 和 Type 4，我们可以写一个通用的接收解析器
def receive_packet(sock):
    # 先严格读取 2 字节，解析出 Type
    type_bytes = sock.recv(2)
    if not type_bytes:
        return None, None
    msg_type, = struct.unpack('!H', type_bytes)
    
    if msg_type == 2:
        # agree 报文没有后续内容
        return msg_type, None
        
    elif msg_type == 4:
        # reverseAnswer 报文，接下来还有 4 字节的长度
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
    # 1. 设定随机数种子，保证每次测试分块结果一致（极其重要！）
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
    
    # 3. 核心切片逻辑（完全按照你的思路）
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



# ============================ 核心主流程 ===========================================
def main():
    # 模拟命令行参数 (为了方便你现在测试，先写死，之后再换成 sys.argv)
    server_ip = '127.0.0.1'
    server_port = 8000
    file_path = 'test.txt'  # 你需要在同级目录下建一个纯英文的 test.txt
    l_min = 50
    l_max = 100
    seed_val = 42

    print("[1] 正在读取并计算文件分块...")
    file_content, chunk_sizes, n_blocks = prepare_file_chunks(file_path, l_min, l_max, seed_val)

    if file_content is None:
        print(f"[-] 错误：由于无法读取文件 '{file_path}'，客户端被迫终止。")
        return 
    
    print(f"文件总大小: {len(file_content)} Bytes, 将分为 {n_blocks} 块发送。")

    print("[2] 正在连接服务器...")
    clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #创建客户机socket
    clientsocket.connect((server_ip, server_port)) #连接到服务器

    # 第一步：发送 Init 报文 (Type=1)
    clientsocket.send(pack_init_packet(n_blocks))
    print(f"-> 发送 Initialization 报文, N={n_blocks}")

    # 第二步：接收 agree 报文 (Type=2)
    msg_type, _ = receive_packet(clientsocket)
    if msg_type != 2:
        print("Error: 握手失败，未收到 agree 报文！")
        clientsocket.close()
        return
    print("<- 收到 agree 报文，允许发送。\n")

    # 第三步：循环发送 request (Type=3) 并接收 answer (Type=4)
    # # 伪代码演示如何根据切片大小提取真实文本
    # current_index = 0
    # for i, size in enumerate(chunk_sizes):
    #     # 利用 Python 的切片语法截取对应长度的文本
    #     chunk_text = file_content[current_index : current_index + size]

    #     # 打包并发送 (用到我们之前写的 struct 函数)
    #     packet = pack_request_packet(chunk_text)
    #     clientsocket.send(packet)

    #     # 游标向前推进
    #     current_index += size

    current_index = 0
    final_reversed_text = ""

    for i, size in enumerate(chunk_sizes):
        # 截取这一块的文本：切片
        chunk_text = file_content[current_index : current_index + size]
        
        # 发送
        clientsocket.send(pack_request_packet(chunk_text))
        print(f"-> 发送第 {i+1} 块数据 ({size} 字节)")

        # 接收
        recv_type, reversed_data = receive_packet(clientsocket)
        if recv_type == 4:
            # 严格按照老师文档的要求打印终端输出
            print(f"第 {i+1} 块: reverse的文本: {reversed_data}")
            final_reversed_text += reversed_data
        
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

