#include "Server.h"
#ifdef _WIN32
  #define WIN32_LEAN_AND_MEAN
  #include <windows.h>
  #include <winsock2.h>
  #include <ws2tcpip.h>
  #pragma comment(lib, "ws2_32.lib")
  #define close_socket(s) closesocket(s)
  #define SHUT_RDWR SD_BOTH
#else
  #include <unistd.h>
  #include <sys/socket.h>
  #include <netinet/in.h>
  #include <arpa/inet.h>
  #include <cstring>
  #define SOCKET int
  #define INVALID_SOCKET (-1)
  #define SOCKET_ERROR (-1)
  #define close_socket(s) close(s)
#endif

#include <iostream>
#include <string>
#include <stdexcept>

Server::Server(int port) {
    std::cout << "Tryng starting server...\n";
    try {
        initialize();

        SOCKET server_fd = socket(AF_INET, SOCK_STREAM, 0);
        if (server_fd == INVALID_SOCKET) {
            throw std::runtime_error("Socket creation failed");
        }

        sockaddr_in address;
        address.sin_family = AF_INET;
        address.sin_addr.s_addr = INADDR_ANY;
        address.sin_port = htons(port);

        if (bind(server_fd, (struct sockaddr*)&address, sizeof(address)) == SOCKET_ERROR) {
            throw std::runtime_error("Bind failed");
        }

        if (listen(server_fd, 3) == SOCKET_ERROR) {
            throw std::runtime_error("Listen failed");
        }

        std::cout << "Server listening on port " << port << std::endl;

        sockaddr_in client_addr;
        socklen_t addr_len = sizeof(client_addr);
        SOCKET client_fd = accept(server_fd, (struct sockaddr*)&client_addr, &addr_len);

        if (client_fd == INVALID_SOCKET) {
            throw std::runtime_error("Accept failed");
        }

        char client_ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, INET_ADDRSTRLEN);
        std::cout << "Client connected: " << client_ip << std::endl;

        while (client_fd != NULL) {
            char buffer[1024];
            int bytes_read = recv(client_fd, buffer, 1024 - 1, 0);

            if (bytes_read > 0) {
                buffer[bytes_read] = '\0';
                std::cout << "Received: " << buffer << std::endl;

                const char* response = "Hello from server!";
                send(client_fd, response, strlen(response), 0);
            }
        }

        shutdown(client_fd, SHUT_RDWR);
        close_socket(client_fd);
        close_socket(server_fd);

        cleanup();
    }
    catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        cleanup();
    }
}

void Server::initialize() {
    #ifdef _WIN32
        WSADATA wsaData;
        if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
            throw std::runtime_error("WSAStartup failed");
        }
    #endif
}

void Server::cleanup() {
    #ifdef _WIN32
        WSACleanup();
    #endif
}