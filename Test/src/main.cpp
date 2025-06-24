#include "Server.h"
#include "Client.h"
#include <iostream>
#include <string>

int main() {
    std::string mode;
    std::cout << "Select mode: ";
    std::cin >> mode;
    if (mode == "0") {
        std::cout << "Staring server...";
        Server socket = Server(1414);
    }
    else if (mode == "1") {
        std::cout << "Starting client...";
        Client socket = Client("127.0.0.1", 1414);
    }
    return 14;
}