import socket


def main(host='localhost',port=9090):
    serversocket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,True)
    serversocket.bind((host,port))
    serversocket.listen(5)

    while True:
        clientsocket, (client_address, client_port) = serversocket.accept()
        print(f"New client {client_address}:{client_port}")

        while True:
            try:
                data = clientsocket.recv(1024)
                print(f"Recieved :{data}")

            except OSError:break

            if len(data)==0:
                break

            sent_data = data
            while True:
                sent_len = clientsocket.send(data)
                if sent_len==len(data):
                    break
                sent_data = sent_data[sent_len:]
            print(f"Send: {data}")

        clientsocket.close()
        print(f"Bye-bye: {client_address}:{client_port}")


if __name__ == '__main__':
    main()