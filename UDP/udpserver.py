import socket 											#导入socket模块	
import struct

# ============================ 报文头部封装/解封装 ============================================
def pack_udp_agree(): # 封装服务器同意连接的报文
    return struct.pack('!H', 2)

def parse_incoming_udp_packet(data): # 解封装服务器响应报文
    if len(data) < 2:
        return None, None
    msg_type, = struct.unpack('!H', data[:2])
    
    if msg_type == 1 and len(data) == 4:
        # 解包 Type 1 报文，提取出加密的 ID
        _, encrypted_id = struct.unpack('!HH', data)
        return msg_type, encrypted_id
        
    return msg_type, None

# ============================ 主函数 ============================================

def main():
    # 1. 创建服务器 Socket
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #创建服务器socket
    serversocket.bind(('127.0.0.1', 8000)) #绑定到IP地址和端口号
    
    print("=======================================")
    print("  UDP GBN Server 已启动，等待握手...  ")
    print("=======================================")

    while True:
        # 2. 接收客户端数据
        data, address = serversocket.recvfrom(1024) #接收数据，返回数据和客户机地址
        
        msg_type, encrypted_id = parse_incoming_udp_packet(data)

        if msg_type == 1:
            # 老师要求的验证逻辑：再次异或
            decrypted_id = encrypted_id ^ 0x5A3C
            if 0 <= decrypted_id <= 9999:
                print(f"[+] 验证通过！合法学号后四位: {decrypted_id:04d}")
                serversocket.sendto(pack_udp_agree(), address)
            else:
                print(f"[-] 非法连接！解密结果: {decrypted_id}")

if __name__ == '__main__':
    main()


