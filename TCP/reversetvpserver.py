import socket                   		#导入socket模块
import threading                	#导入threading模块

serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
								#创建服务器socket（IPv4、TCP套接字）

#允许端口复用
serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

serversocket.bind(('127.0.0.1', 8000)) 	#绑定到IP地址和端口号
serversocket.listen(5)             			#开始侦听，队列长度为5
print("服务器已启动，等待连接...")

def get_bot_response(msg):
    if "name" in msg or "what is your name" in msg or "what's your name" in msg:
        return "Sally"
    elif "old" in msg or "age"in msg or "how old are you" in msg:
        return "24"
    elif "how are you" in msg:
        return "Fine, thank you."
    elif "work" in msg or "where do you work" in msg:
        return "University"
    elif "hello" in msg or "hi" in msg:
        return "Hello!"
    else:
        return "Sorry"
    
#让服务器能同时处理多个客户端（并行，多线程）
def handle_client(clientsocket, clientaddress):
    print(f'Connected by {clientaddress}')
    # 处理单个客户端的循环
    while True:
        data = clientsocket.recv(1024)
        print(f"Received message: {data.decode()}")
        if not data: break
        # ... 处理消息 ...
        response = get_bot_response(data.decode())
        clientsocket.send(response.encode())

    clientsocket.close()
    print(f'Closed connection to {clientaddress}')


#--------------主函数-----------------#
serversocket.settimeout(1.0)  # 设置1秒超时

try:
    #让服务器能处理多个客户端（串行，一次一个）
    while True:
        try:
            clientsocket, clientaddress = serversocket.accept() 	#使用阻塞方法accept以等待客户机连接请求
            
            # 为每个客户端创建一个新线程
            client_thread = threading.Thread(target=handle_client, args=(clientsocket, clientaddress))
            client_thread.start()
        except socket.timeout:
            continue  # 超时后继续循环，这时可以响应 Ctrl+C
except KeyboardInterrupt:
    print("\n[信号] 检测到中断，服务器正在关闭...")
finally:
    serversocket.close()
    print("服务器已关闭")