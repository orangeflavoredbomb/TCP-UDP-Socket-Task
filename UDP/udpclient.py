import socket 											#导入socket模块
import struct
import sys

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
    # 预留给后续的 ACK 报文解析
    return msg_type, None

# ============================ 主函数 ============================================

def main():
    # 模拟命令行参数 (IP, Port)
    server_ip = '127.0.0.1'
    server_port = 8000

    # 1. 创建 UDP Socket
    clientsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 	#创建客户机socket
   
    # 2. 发送给服务器
    clientsocket.sendto(pack_udp_handshake(2624), (server_ip, server_port))
    
    # 3. 设置超时，等待服务器响应 (老师要求如果没收到可以重试或断开，这里先设2秒)
    clientsocket.settimeout(2.0)
    try:
        data, server_addr = clientsocket.recvfrom(1024) #接收服务器的回送数据
        msg_type, = struct.unpack('!H', data[:2])
        if msg_type == 2: # 假设我们沿用 Task 1 的 Type 2 代表 agree
            print("[+] 握手成功！服务器同意连接。")
        else:
            print("[-] 握手失败：服务器拒绝或返回异常。")
    except socket.timeout:
        print("[-] 握手超时：服务器无响应。")
    finally:
        clientsocket.close() #关闭客户机socket


if __name__ == '__main__':
    main()

