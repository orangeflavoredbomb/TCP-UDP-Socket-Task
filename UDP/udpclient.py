import socket 											#导入socket模块
import struct
import sys
import time

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

# ============================ 主函数 ============================================

def main():
    # 模拟命令行参数 (IP, Port)
    server_ip = '127.0.0.1'
    server_port = 8000

    # 创建 UDP Socket
    clientsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 	#创建客户机socket
   
    # 超时时间为 300ms
    TIMEOUT_SEC = 0.3
    clientsocket.settimeout(TIMEOUT_SEC)

    while True:
        print("-> 正在发送数据...")
        start_time = time.time()
        # 发送给服务器
        clientsocket.sendto(pack_udp_handshake(2624), (server_ip, server_port))

        try:
            # 乖乖等待 300ms
            response, server_addr = clientsocket.recvfrom(1024)
            end_time = time.time()
            
            # 成功收到，计算 RTT (转化为毫秒)
            rtt_ms = (end_time - start_time) * 1000
            print(f"<- [成功] 收到服务器响应！本次 RTT: {rtt_ms:.2f} ms")
            break  # 收到确认，跳出重传循环，去发下一个包！
            
        except socket.timeout:
            # 300ms 到了还没收到
            print(f"[-] [超时] 300ms 内未收到响应，判定丢包，准备重发...")
            # 循环会再次回到顶部，重新 sendto
    
    clientsocket.close() #关闭客户机socket


if __name__ == '__main__':
    main()

