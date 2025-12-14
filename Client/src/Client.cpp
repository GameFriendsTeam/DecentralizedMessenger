#include "Client.h"
#include "Server.h"
#include <iostream>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <algorithm>
#include <random>
#include <cstring>

Client::Client(const std::string& mac_addr) 
    : mac_address(mac_addr), self_id(-1) {
    std::cout << "Client created with MAC: " << mac_address << std::endl;
}

Client::~Client() {
    std::cout << "Client " << self_id << " destroyed" << std::endl;
}

bool Client::set_self_id() {
    // Генерация ID на основе MAC-адреса
    int base_id = generate_id_from_mac(mac_address);
    
    // Проверка доступности ID через серверы
    std::vector<int> visited_servers;
    int candidate_id = base_id;
    int attempts = 0;
    
    while (attempts < 1000) {
        bool available = true;
        
        // Проверяем через все известные серверы
        for (const auto& server : known_servers) {
            if (server && server->get_by_id(candidate_id, visited_servers) != nullptr) {
                available = false;
                break;
            }
        }
        
        if (available) {
            self_id = candidate_id;
            std::cout << "Client " << mac_address << " получил ID: " << self_id << std::endl;
            return true;
        }
        
        // Генерируем новый кандидат
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dist(1, 1000);
        candidate_id = base_id + dist(gen);
        attempts++;
        
        visited_servers.clear();
    }
    
    std::cerr << "Не удалось получить уникальный ID для клиента " << mac_address << std::endl;
    return false;
}

int Client::generate_id_from_mac(const std::string& mac_addr) {
    // Простая хеш-функция для MAC-адреса
    std::hash<std::string> hasher;
    size_t hash = hasher(mac_addr);
    return static_cast<int>(hash & 0x7FFFFFFF); // Положительное число
}

bool Client::is_id_available(int id, std::vector<int>& visited_servers) {
    for (const auto& server : known_servers) {
        if (server && server->get_by_id(id, visited_servers) != nullptr) {
            return false;
        }
    }
    return true;
}

void Client::send_message(int target_id, const std::string& content) {
    if (self_id == -1) {
        std::cerr << "Клиент не инициализирован. Сначала вызовите set_self_id()" << std::endl;
        return;
    }
    
    if (target_id == self_id) {
        std::cerr << "Нельзя отправить сообщение самому себе" << std::endl;
        return;
    }
    
    // Поиск целевого клиента через серверы
    std::vector<int> visited_servers;
    std::shared_ptr<Client> target_client = nullptr;
    
    for (const auto& server : known_servers) {
        if (server) {
            target_client = server->get_by_id(target_id, visited_servers);
            if (target_client) break;
        }
    }
    
    if (!target_client) {
        std::cerr << "Клиент с ID " << target_id << " не найден" << std::endl;
        return;
    }
    
    // Создание сообщения
    Message msg;
    msg.from_id = self_id;
    msg.to_id = target_id;
    msg.content = content;
    
    auto now = std::chrono::system_clock::now();
    auto now_time = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&now_time), "%Y-%m-%d %H:%M:%S");
    msg.timestamp = ss.str();
    
    // Отправка сообщения
    target_client->receive_message(self_id, content);
    
    // Сохранение в истории
    add_to_chat_history(target_id, msg);
    
    std::cout << "[SEND] " << self_id << " -> " << target_id << ": " << content << std::endl;
}

void Client::receive_message(int from_id, const std::string& content) {
    Message msg;
    msg.from_id = from_id;
    msg.to_id = self_id;
    msg.content = content;
    
    auto now = std::chrono::system_clock::now();
    auto now_time = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&now_time), "%Y-%m-%d %H:%M:%S");
    msg.timestamp = ss.str();
    
    add_to_chat_history(from_id, msg);
    
    std::cout << "[RECV] " << from_id << " -> " << self_id << ": " << content << std::endl;
    
    if (message_callback) {
        message_callback(from_id, content);
    }
}

std::vector<Message> Client::get_chat_by_id(int other_id) const {
    std::lock_guard<std::mutex> lock(const_cast<std::mutex&>(history_mutex));
    auto it = chat_history.find(other_id);
    if (it != chat_history.end()) {
        return it->second;
    }
    return {};
}

void Client::set_chat_by_id(int other_id, const std::vector<Message>& history) {
    std::lock_guard<std::mutex> lock(history_mutex);
    chat_history[other_id] = history;
}

void Client::add_to_chat_history(int other_id, const Message& msg) {
    std::lock_guard<std::mutex> lock(history_mutex);
    chat_history[other_id].push_back(msg);
}

void Client::connect_to_server(const std::shared_ptr<Server>& server) {
    if (server) {
        known_servers.push_back(server);
        server->register_client(shared_from_this());
        std::cout << "Client " << self_id << " подключен к серверу" << std::endl;
    }
}

void Client::disconnect_from_server(const std::shared_ptr<Server>& server) {
    auto it = std::find(known_servers.begin(), known_servers.end(), server);
    if (it != known_servers.end()) {
        known_servers.erase(it);
        if (server) {
            server->unregister_client(self_id);
        }
        std::cout << "Client " << self_id << " отключен от сервера" << std::endl;
    }
}

void Client::set_message_callback(const std::function<void(int, const std::string&)>& callback) {
    message_callback = callback;
}

void Client::print_status() const {
    std::cout << "\n=== Статус Client ===" << std::endl;
    std::cout << "ID: " << self_id << std::endl;
    std::cout << "MAC: " << mac_address << std::endl;
    std::cout << "Известных серверов: " << known_servers.size() << std::endl;
    std::cout << "Историй чатов: " << chat_history.size() << std::endl;
    
    for (const auto& [id, messages] : chat_history) {
        std::cout << "  Чат с " << id << ": " << messages.size() << " сообщений" << std::endl;
    }
}