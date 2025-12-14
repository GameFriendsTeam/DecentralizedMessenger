#include "NetworkManager.h"
#include "Client.h"
#include "Server.h"
#include <iostream>
#include <chrono>
#include <sstream>
#include <iomanip>
#include <random>

NetworkManager::NetworkManager() 
    : running_(false) {
}

NetworkManager::~NetworkManager() {
    shutdown();
}

bool NetworkManager::initialize(bool as_server, const std::string& mac_address) {
    if (running_) {
        return false;
    }
    
    if (as_server) {
        return start_server(mac_address);
    } else {
        return start_client(mac_address);
    }
}

void NetworkManager::shutdown() {
    running_ = false;
    
    if (server_thread_.joinable()) {
        server_thread_.join();
    }
    
    if (client_thread_.joinable()) {
        client_thread_.join();
    }
    
    server_.reset();
    client_.reset();
}

bool NetworkManager::start_server(const std::string& mac_address) {
    try {
        server_ = std::make_shared<Server>(mac_address);
        if (!server_->set_self_id()) {
            return false;
        }
        
        running_ = true;
        server_thread_ = std::thread(&NetworkManager::server_worker, this);
        
        std::cout << "Сервер запущен с MAC: " << mac_address 
                  << ", ID: " << server_->get_id() << std::endl;
        
        return true;
    } catch (const std::exception& e) {
        std::cerr << "Ошибка запуска сервера: " << e.what() << std::endl;
        return false;
    }
}

bool NetworkManager::start_client(const std::string& mac_address) {
    try {
        client_ = std::make_shared<Client>(mac_address);
        if (!client_->set_self_id()) {
            return false;
        }
        
        // Устанавливаем callback для сообщений
        client_->set_message_callback([this](int from_id, const std::string& content) {
            this->on_client_message_received(from_id, content);
        });
        
        running_ = true;
        client_thread_ = std::thread(&NetworkManager::client_worker, this);
        
        std::cout << "Клиент запущен с MAC: " << mac_address 
                  << ", ID: " << client_->get_id() << std::endl;
        
        return true;
    } catch (const std::exception& e) {
        std::cerr << "Ошибка запуска клиента: " << e.what() << std::endl;
        return false;
    }
}

bool NetworkManager::connect_to_server(const std::string& server_address) {
    // В реальной реализации здесь было бы подключение к сетевому серверу
    // В данном примере это заглушка для демонстрации
    std::cout << "[NetworkManager] Подключение к серверу " << server_address << std::endl;
    stats_.connections++;
    
    // Генерируем случайный ID для "сервера" (в реальности это был бы другой клиент)
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dist(1000, 9999);
    int server_id = dist(gen);
    
    std::cout << "[NetworkManager] Установлено соединение с сервером ID: " << server_id << std::endl;
    
    return true;
}

void NetworkManager::send_message(int target_id, const std::string& content) {
    if (!client_) {
        std::cerr << "Клиент не инициализирован\n";
        return;
    }
    
    client_->send_message(target_id, content);
    stats_.messages_sent++;
}

bool NetworkManager::receive_message(int& from_id, std::string& content, int timeout_ms) {
    std::unique_lock<std::mutex> lock(message_mutex_);
    
    if (message_cv_.wait_for(lock, std::chrono::milliseconds(timeout_ms), 
                            [this]() { return !message_queue_.empty(); })) {
        auto msg = message_queue_.front();
        message_queue_.pop();
        
        from_id = msg.first;
        content = msg.second;
        stats_.messages_received++;
        
        return true;
    }
    
    return false;
}

void NetworkManager::server_worker() {
    while (running_) {
        // В реальной реализации здесь был бы сетевой код для приема соединений
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}

void NetworkManager::client_worker() {
    while (running_) {
        // В реальной реализации здесь была бы обработка входящих сетевых сообщений
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

void NetworkManager::on_client_message_received(int from_id, const std::string& content) {
    // Добавляем сообщение в очередь для обработки
    {
        std::lock_guard<std::mutex> lock(message_mutex_);
        message_queue_.push({from_id, content});
    }
    message_cv_.notify_one();
    
    // Вызываем пользовательский callback, если установлен
    if (message_callback_) {
        message_callback_(from_id, content);
    }
}

void NetworkManager::print_stats() const {
    std::cout << "\n=== Статистика NetworkManager ===\n";
    std::cout << "Отправлено сообщений: " << stats_.messages_sent << std::endl;
    std::cout << "Получено сообщений: " << stats_.messages_received << std::endl;
    std::cout << "Установлено соединений: " << stats_.connections << std::endl;
    
    if (server_) {
        std::cout << "Сервер ID: " << server_->get_id() 
                  << " (MAC: " << server_->get_mac() << ")\n";
    }
    
    if (client_) {
        std::cout << "Клиент ID: " << client_->get_id() 
                  << " (MAC: " << client_->get_mac() << ")\n";
    }
    
    std::cout << "===================================\n";
}

void NetworkManager::reset_stats() {
    stats_ = {};
}

void NetworkManager::set_message_callback(std::function<void(int, const std::string&)> callback) {
    message_callback_ = callback;
}