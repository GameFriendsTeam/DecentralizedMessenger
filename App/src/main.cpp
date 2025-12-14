#include "ConfigManager.h"
#include "NetworkManager.h"
#include "CommandHandler.h"
#include <iostream>
#include <memory>
#include <string>
#include <cstring>

void print_help() {
    std::cout << "P2P Mesh System v1.0.0\n\n";
    std::cout << "Использование:\n";
    std::cout << "  p2pmesh [опции]\n\n";
    std::cout << "Опции:\n";
    std::cout << "  --server              Запуск в режиме сервера\n";
    std::cout << "  --client              Запуск в режиме клиента\n";
    std::cout << "  --mac=<адрес>         Использовать указанный MAC-адрес\n";
    std::cout << "  --config=<файл>       Использовать указанный конфигурационный файл\n";
    std::cout << "  --help                Показать эту справку\n";
    std::cout << "  --version             Показать версию\n";
    std::cout << "\nПримеры:\n";
    std::cout << "  p2pmesh --server --mac=00:11:22:33:44:55\n";
    std::cout << "  p2pmesh --client --config=client.ini\n";
}

void print_version() {
    std::cout << "P2P Mesh System v1.0.0\n";
    std::cout << "Распределенная P2P система обмена сообщениями\n";
}

int main(int argc, char* argv[]) {
    setlocale(LC_ALL, "ru_RU.UTF-8");
    bool run_as_server = false;
    bool run_as_client = false;
    std::string mac_address = "";
    std::string config_file = "config.ini";
    
    // Парсинг аргументов командной строки
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        
        if (arg == "--server") {
            run_as_server = true;
        } else if (arg == "--client") {
            run_as_client = true;
        } else if (arg == "--help" || arg == "-h") {
            print_help();
            return 0;
        } else if (arg == "--version" || arg == "-v") {
            print_version();
            return 0;
        } else if (arg.find("--mac=") == 0) {
            mac_address = arg.substr(6);
        } else if (arg.find("--config=") == 0) {
            config_file = arg.substr(9);
        } else {
            std::cerr << "Неизвестный аргумент: " << arg << std::endl;
            print_help();
            return 1;
        }
    }
    
    // Если не указан режим, спросим пользователя
    if (!run_as_server && !run_as_client) {
        std::cout << "Выберите режим работы:\n";
        std::cout << "1. Сервер\n";
        std::cout << "2. Клиент\n";
        std::cout << "3. Выйти\n";
        std::cout << "Ваш выбор (1-3): ";
        
        int choice;
        std::cin >> choice;
        
        switch (choice) {
            case 1:
                run_as_server = true;
                break;
            case 2:
                run_as_client = true;
                break;
            case 3:
                return 0;
            default:
                std::cerr << "Неверный выбор\n";
                return 1;
        }
    }
    
    try {
        // Загрузка конфигурации
        std::shared_ptr<ConfigManager> config_manager = std::make_shared<ConfigManager>(config_file);
        if (!config_manager->load_config()) {
            std::cout << "Создана новая конфигурация\n";
        }
        
        // Создание сетевого менеджера
        std::shared_ptr<NetworkManager> network_manager = std::make_shared<NetworkManager>();
        
        // Инициализация
        if (run_as_server) {
            std::cout << "Запуск в режиме сервера...\n";
            
            ServerConfig server_config = config_manager->get_server_config();
            if (mac_address.empty() && server_config.mac_address.empty()) {
                // Генерация MAC-адреса
                mac_address = "00:";
                for (int i = 0; i < 5; i++) {
                    char hex[3];
                    snprintf(hex, sizeof(hex), "%02X", rand() % 256);
                    mac_address += hex;
                    if (i < 4) mac_address += ":";
                }
                server_config.mac_address = mac_address;
                config_manager->set_server_config(server_config);
            } else if (!mac_address.empty()) {
                server_config.mac_address = mac_address;
                config_manager->set_server_config(server_config);
            }
            
            if (!network_manager->start_server(server_config.mac_address)) {
                std::cerr << "Не удалось запустить сервер\n";
                return 1;
            }
            
            std::cout << "Сервер запущен с MAC: " << server_config.mac_address << std::endl;
            
        } else if (run_as_client) {
            std::cout << "Запуск в режиме клиента...\n";
            
            ClientConfig client_config = config_manager->get_client_config();
            if (mac_address.empty() && client_config.mac_address.empty()) {
                // Генерация MAC-адреса
                mac_address = "AA:";
                for (int i = 0; i < 5; i++) {
                    char hex[3];
                    snprintf(hex, sizeof(hex), "%02X", rand() % 256);
                    mac_address += hex;
                    if (i < 4) mac_address += ":";
                }
                client_config.mac_address = mac_address;
                config_manager->set_client_config(client_config);
            } else if (!mac_address.empty()) {
                client_config.mac_address = mac_address;
                config_manager->set_client_config(client_config);
            }
            
            if (!network_manager->start_client(client_config.mac_address)) {
                std::cerr << "Не удалось запустить клиент\n";
                return 1;
            }
            
            std::cout << "Клиент запущен с MAC: " << client_config.mac_address << std::endl;
            
            // Подключение к известным серверам
            for (const auto& server_addr : client_config.known_servers) {
                std::cout << "Подключение к серверу " << server_addr << "...\n";
                network_manager->connect_to_server(server_addr);
            }
        }
        
        // Сохранение конфигурации
        config_manager->save_config();
        
        // Запуск обработчика команд
        CommandHandler command_handler(network_manager);
        command_handler.register_commands();
        
        if (run_as_client) {
            std::cout << "\n=== P2P Mesh Client ===\n";
            std::cout << "Используйте 'help' для списка команд\n";
            std::cout << "Используйте 'exit' для выхода\n\n";
            command_handler.run_interactive();
        } else {
            std::cout << "\n=== P2P Mesh Server ===\n";
            std::cout << "Сервер запущен. Нажмите Ctrl+C для остановки.\n";
            
            // Ожидание завершения
            while (true) {
                std::this_thread::sleep_for(std::chrono::seconds(1));
                network_manager->print_stats();
            }
        }
        
        // Остановка
        network_manager->shutdown();
        
    } catch (const std::exception& e) {
        std::cerr << "Ошибка: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}