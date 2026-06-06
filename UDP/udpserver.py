import socket 											#导入socket模块	
import struct
import random

# ============================ 报文头部封装/解封装 ============================================
def pack_udp_agree(): # 封装服务器同意连接的报文
    return struct.pack('!H', 2)

def parse_incoming_udp_packet(data): # 解封装服务器响应报文
    if len(data) < 2:
        return None, None, None
    
    msg_type, = struct.unpack('!H', data[:2])
    
    if msg_type == 1 and len(data) == 4:
        # 解包 Type 1 报文，提取出加密的 ID
        _, encrypted_id = struct.unpack('!HH', data)
        return msg_type, encrypted_id, None
        
    elif msg_type == 3:
        # 解包 Type 3 头部 (10字节)
        _, seq_num, data_len = struct.unpack('!HII', data[:10])
        # 截取真实文本数据
        text_data = data[10 : 10 + data_len].decode('ascii')
        return msg_type, seq_num, text_data
    
    return None, None, None

def pack_udp_ack(seq_num): # 封装 ACK 报文 
    return struct.pack("!HI", 4, seq_num)

# ============================ 主函数 ============================================

def main():
    # 1. 创建服务器 Socket
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #创建服务器socket
    serversocket.bind(('127.0.0.1', 8000)) #绑定到IP地址和端口号
    
    print("=======================================")
    print("  UDP GBN Server 已启动，等待握手...  ")
    print("=======================================")

    # 假设丢包率为 30%
    DROP_RATE = 0.3

    expected_seq_num = 1  # 期望的下一个序号，初始为1

    while True:
        # 2. 接收客户端数据
        data, address = serversocket.recvfrom(1024) #接收数据，返回数据和客户机地址

        msg_type, val1, val2 = parse_incoming_udp_packet(data)

        if msg_type == 1:
            # 再次异或验证
            encrypted_id = val1
            decrypted_id = encrypted_id ^ 0x5A3C
            if 0 <= decrypted_id <= 9999:
                print(f"[+] 验证通过！合法学号后四位: {decrypted_id:04d}")
                serversocket.sendto(pack_udp_agree(), address)
                expected_seq_num = 1  # 握手成功后，重置期望的序号
            else:
                print(f"[-] 非法连接！解密结果: {decrypted_id}")

        elif msg_type == 3:
            seq_num = val1
            text_data = val2

            # 模拟丢包：随机决定是否丢弃这个数据包
            if random.random() < DROP_RATE:
                print(f"[-] [模拟丢包] 假装没收到 {address} 的数据。")
                continue  # 直接进入下一次循环
            
            # GBN 核心接收逻辑：判断是不是我想要的那个包
            if seq_num == expected_seq_num:
                print(f"[+] 顺序正确！收到数据 Seq={seq_num}，内容片段: {text_data[:15]}...")
                # 收下，并回复对应序号的 ACK
                serversocket.sendto(pack_udp_ack(expected_seq_num), address)
                # 期待下一个！
                expected_seq_num += 1
            else:
                # 收到了包，但不是按顺序来的（乱序，或者前面的丢了）
                print(f"[*] 乱序/重复！期望 Seq={expected_seq_num}, 却收到 Seq={seq_num}。丢弃并重传上一 ACK。")
                # 无情丢弃该数据包，并再次发送上一成功包的 ACK（冗余 ACK）
                # 注意：如果连第 1 个包都没收到，预期是 1，那就回发 ACK 0
                serversocket.sendto(pack_udp_ack(expected_seq_num - 1), address)



if __name__ == '__main__':
    main()


