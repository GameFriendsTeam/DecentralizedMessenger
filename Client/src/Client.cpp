#include "Client.h"
#pragma once

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

Client::Client(char* server_ip, int port) {
    std::cout << "Tryng starting client...";
    try {
        initialize();

        SOCKET sock = socket(AF_INET, SOCK_STREAM, 0);
        if (sock == INVALID_SOCKET) {
            throw std::runtime_error("Socket creation failed");
        }

        sockaddr_in serv_addr;
        serv_addr.sin_family = AF_INET;
        serv_addr.sin_port = htons(port);
        inet_pton(AF_INET, server_ip, &serv_addr.sin_addr);

        if (connect(sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) == SOCKET_ERROR) {
            throw std::runtime_error("Connection failed");
        }

        const char* message = "Hello from client!";
        send(sock, message, strlen(message), 0);
        std::cout << "Message sent" << std::endl;

        char buffer[1024];
        int bytes_read = recv(sock, buffer, 1024 - 1, 0);
        if (bytes_read > 0) {
            buffer[bytes_read] = '\0';
            std::cout << "Server response: " << buffer << std::endl;
        }

        shutdown(sock, SHUT_RDWR);
        close_socket(sock);

        cleanup();
    }
    catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        cleanup();
    }
}

void Client::initialize() {
#ifdef _WIN32
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        throw std::runtime_error("WSAStartup failed");
    }
#endif
}

void Client::cleanup() {
#ifdef _WIN32
    WSACleanup();
#endif
}
