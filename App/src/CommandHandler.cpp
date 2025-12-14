#include "CommandHandler.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <thread>
#include <chrono>
#include <iomanip>

CommandHandler::CommandHandler(std::shared_ptr<NetworkManager> network_manager)
    : network_manager_(network_manager), exit_requested_(false) {
}

void CommandHandler::register_commands() {
    commands_["help"] = [this](const std::vector<std::string>& args) { cmd_help(args); };
    commands_["send"] = [this](const std::vector<std::string>& args) { cmd_send(args); };
    commands_["list"] = [this](const std::vector<std::string>& args) { cmd_list(args); };
    commands_["connect"] = [this](const std::vector<std::string>& args) { cmd_connect(args); };
    commands_["disconnect"] = [this](const std::vector<std::string>& args) { cmd_disconnect(args); };
    commands_["status"] = [this](const std::vector<std::string>& args) { cmd_status(args); };
    commands_["history"] = [this](const std::vector<std::string>& args) { cmd_history(args); };
    commands_["clear"] = [this](const std::vector<std::string>& args) { cmd_clear(args); };
    commands_["exit"] = [this](const std::vector<std::string>& args) { cmd_exit(args); };
    commands_["quit"] = [this](const std::vector<std::string>& args) { cmd_exit(args); };
}

void CommandHandler::process_command(const std::string& command_line) {
    std::vector<std::string> args = split_command(command_line);
    if (args.empty()) {
        return;
    }
    
    std::string cmd = args[0];
    std::transform(cmd.begin(), cmd.end(), cmd.begin(), ::tolower);
    
    auto it = commands_.find(cmd);
    if (it != commands_.end()) {
        try {
            it->second(args);
        } catch (const std::exception& e) {
            std::cerr << "Ошибка выполнения команды: " << e.what() << std::endl;
        }
    } else {
        std::cout << "Неизвестная команда: " << cmd << std::endl;
        std::cout << "Используйте 'help' для списка команд\n";
    }
}

void CommandHandler::run_interactive() {
    print_banner();
    
    std::string line;
    while (!exit_requested_) {
        std::cout << "p2pmesh> ";
        std::getline(std::cin, line);
        
        if (line.empty()) {
            continue;
        }
        
        process_command(line);
    }
}

void CommandHandler::run_script(const std::string& script_file) {
    std::ifstream file(script_file);
    if (!file.is_open()) {
        std::cerr << "Не удалось открыть файл скрипта: " << script_file << std::endl;
        return;
    }
    
    std::string line;
    while (std::getline(file, line) && !exit_requested_) {
        std::cout << "p2pmesh> " << line << std::endl;
        process_command(line);
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

std::vector<std::string> CommandHandler::split_command(const std::string& command_line) const {
    std::vector<std::string> args;
    std::istringstream iss(command_line);
    std::string arg;
    
    while (iss >> std::quoted(arg)) {
        args.push_back(arg);
    }
    
    return args;
}

void CommandHandler::print_banner() const {
    std::cout << "========================================\n";
    std::cout << "       P2P MESH SYSTEM v1.0.0\n";
    std::cout << "========================================\n";
}

void CommandHandler::cmd_help(const std::vector<std::string>& /*args*/) {
    std::cout << "\nДоступные команды:\n";
    std::cout << "  help                  - Показать эту справку\n";
    std::cout << "  send <id> <сообщение> - Отправить сообщение клиенту с указанным ID\n";
    std::cout << "  list                  - Список известных клиентов\n";
    std::cout << "  connect <адрес>       - Подключиться к серверу\n";
    std::cout << "  disconnect <адрес>    - Отключиться от сервера\n";
    std::cout << "  status                - Показать статус системы\n";
    std::cout << "  history <id>          - Показать историю чата с клиентом\n";
    std::cout << "  clear                 - Очистить экран\n";
    std::cout << "  exit | quit           - Выйти из программы\n";
    std::cout << std::endl;
}

void CommandHandler::cmd_send(const std::vector<std::string>& args) {
    if (args.size() < 3) {
        std::cout << "Использование: send <id> <сообщение>\n";
        return;
    }
    
    try {
        int target_id = std::stoi(args[1]);
        
        // Объединяем оставшиеся аргументы в сообщение
        std::string message;
        for (size_t i = 2; i < args.size(); i++) {
            if (i > 2) message += " ";
            message += args[i];
        }
        
        if (network_manager_) {
            network_manager_->send_message(target_id, message);
            std::cout << "Сообщение отправлено клиенту " << target_id << std::endl;
        } else {
            std::cerr << "Ошибка: NetworkManager не инициализирован\n";
        }
        
    } catch (const std::exception& e) {
        std::cerr << "Ошибка: " << e.what() << std::endl;
    }
}

void CommandHandler::cmd_list(const std::vector<std::string>& /*args*/) {
    std::cout << "\nСписок команд будет доступен после реализации сетевого поиска\n";
    std::cout << "В текущей версии используйте прямые ID для отправки сообщений\n";
}

void CommandHandler::cmd_connect(const std::vector<std::string>& args) {
    if (args.size() < 2) {
        std::cout << "Использование: connect <адрес_сервера>\n";
        return;
    }
    
    if (network_manager_) {
        if (network_manager_->connect_to_server(args[1])) {
            std::cout << "Подключение установлено\n";
        } else {
            std::cout << "Не удалось подключиться\n";
        }
    } else {
        std::cerr << "Ошибка: NetworkManager не инициализирован\n";
    }
}

void CommandHandler::cmd_disconnect(const std::vector<std::string>& /*args*/) {
    std::cout << "Команда disconnect не реализована в данной версии\n";
}

void CommandHandler::cmd_status(const std::vector<std::string>& /*args*/) {
    if (network_manager_) {
        network_manager_->print_stats();
    } else {
        std::cerr << "Ошибка: NetworkManager не инициализирован\n";
    }
}

void CommandHandler::cmd_history(const std::vector<std::string>& /*args*/) {
    std::cout << "Просмотр истории будет доступен после реализации хранилища сообщений\n";
}

void CommandHandler::cmd_clear(const std::vector<std::string>& /*args*/) {
    #ifdef _WIN32
        system("cls");
    #else
        system("clear");
    #endif
}

void CommandHandler::cmd_exit(const std::vector<std::string>& /*args*/) {
    std::cout << "Завершение работы...\n";
    exit_requested_ = true;
}

void CommandHandler::print_usage() const {
    std::cout << "\nИспользование команд:\n";
    std::cout << "  send <id> \"сообщение\"  - Отправить сообщение клиенту с указанным ID\n";
    std::cout << "  status                 - Показать статистику работы\n";
    std::cout << "  exit                   - Выйти из программы\n";
}