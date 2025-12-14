#include "ConfigManager.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <random>
#include <iomanip>
#include <algorithm>

ConfigManager::ConfigManager(const std::string& config_file) 
    : config_file_(config_file) {
}

bool ConfigManager::load_config() {
    std::ifstream file(config_file_);
    if (!file.is_open()) {
        // Файл не существует, создадим дефолтную конфигурацию
        return false;
    }
    
    parse_ini_file();
    
    // Загрузка серверной конфигурации
    server_config_.mac_address = get_value("server.mac", "");
    server_config_.address = get_value("server.address", "0.0.0.0");
    server_config_.port = std::stoi(get_value("server.port", "8080"));
    
    std::string peers = get_value("server.peers", "");
    std::istringstream peer_stream(peers);
    std::string peer;
    while (std::getline(peer_stream, peer, ',')) {
        if (!peer.empty()) {
            server_config_.peer_servers.push_back(peer);
        }
    }
    
    // Загрузка клиентской конфигурации
    client_config_.mac_address = get_value("client.mac", "");
    
    std::string servers = get_value("client.servers", "");
    std::istringstream server_stream(servers);
    std::string server;
    while (std::getline(server_stream, server, ',')) {
        if (!server.empty()) {
            client_config_.known_servers.push_back(server);
        }
    }
    
    return true;
}

bool ConfigManager::save_config() {
    std::ofstream file(config_file_);
    if (!file.is_open()) {
        std::cerr << "Не удалось открыть файл конфигурации: " << config_file_ << std::endl;
        return false;
    }
    
    file << "# P2P Mesh System Configuration\n\n";
    
    // Серверная секция
    file << "[server]\n";
    file << "mac = " << server_config_.mac_address << "\n";
    file << "address = " << server_config_.address << "\n";
    file << "port = " << server_config_.port << "\n";
    file << "peers = ";
    for (size_t i = 0; i < server_config_.peer_servers.size(); i++) {
        file << server_config_.peer_servers[i];
        if (i < server_config_.peer_servers.size() - 1) {
            file << ",";
        }
    }
    file << "\n\n";
    
    // Клиентская секция
    file << "[client]\n";
    file << "mac = " << client_config_.mac_address << "\n";
    file << "servers = ";
    for (size_t i = 0; i < client_config_.known_servers.size(); i++) {
        file << client_config_.known_servers[i];
        if (i < client_config_.known_servers.size() - 1) {
            file << ",";
        }
    }
    file << "\n\n";
    
    // Общие настройки
    file << "[general]\n";
    file << "log_level = info\n";
    file << "max_connections = 100\n";
    file << "message_timeout = 30\n";
    
    return true;
}

void ConfigManager::parse_ini_file() {
    std::ifstream file(config_file_);
    if (!file.is_open()) return;
    
    std::string line;
    std::string current_section;
    
    while (std::getline(file, line)) {
        // Убираем пробелы в начале и конце
        line.erase(0, line.find_first_not_of(" \t"));
        line.erase(line.find_last_not_of(" \t") + 1);
        
        // Пропускаем пустые строки и комментарии
        if (line.empty() || line[0] == '#' || line[0] == ';') {
            continue;
        }
        
        // Секция
        if (line[0] == '[' && line.back() == ']') {
            current_section = line.substr(1, line.length() - 2);
            continue;
        }
        
        // Ключ-значение
        size_t equals_pos = line.find('=');
        if (equals_pos != std::string::npos) {
            std::string key = line.substr(0, equals_pos);
            std::string value = line.substr(equals_pos + 1);
            
            // Убираем пробелы
            key.erase(0, key.find_first_not_of(" \t"));
            key.erase(key.find_last_not_of(" \t") + 1);
            value.erase(0, value.find_first_not_of(" \t"));
            value.erase(value.find_last_not_of(" \t") + 1);
            
            std::string full_key = current_section + "." + key;
            config_[full_key] = value;
        }
    }
}

std::string ConfigManager::get_value(const std::string& key, const std::string& default_val) const {
    auto it = config_.find(key);
    if (it != config_.end()) {
        return it->second;
    }
    return default_val;
}

void ConfigManager::set_value(const std::string& key, const std::string& value) {
    config_[key] = value;
}