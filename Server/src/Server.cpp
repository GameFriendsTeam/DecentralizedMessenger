#include "Server.h"
#include "Client.h"
#include <iostream>
#include <functional>
#include <algorithm>
#include <random>
#include <memory>

Server::Server(const std::string& mac_addr)
    : mac_address(mac_addr), server_id(-1) {
    std::cout << "Server created with MAC: " << mac_address << std::endl;
}

bool Server::set_self_id() {
    // Генерация уникального ID для сервера
    int base_id = generate_id_from_mac(mac_address);

    // Проверка коллизий с другими серверами
    std::vector<int> visited_servers;
    int candidate_id = base_id;
    int attempts = 0;

    while (attempts < 1000) {
        bool collision = false;

        // Проверяем через связанные серверы
        {
            std::lock_guard<std::mutex> lock(servers_mutex);
            for (const auto& weak_server : connected_servers) {
                if (auto server = weak_server.lock()) {
                    std::vector<int> temp_visited;
                    if (server->get_by_id(candidate_id, temp_visited) != nullptr) {
                        collision = true;
                        break;
                    }
                }
            }
        }

        if (!collision) {
            server_id = candidate_id;
            std::cout << "Server " << mac_address << " получил ID: " << server_id << std::endl;
            return true;
        }

        // Генерируем новый кандидат
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dist(1, 1000);
        candidate_id = base_id + dist(gen);
        attempts++;
    }

    std::cerr << "Не удалось получить уникальный ID для сервера " << mac_address << std::endl;
    return false;
}

std::shared_ptr<Client> Server::get_by_id(int id, std::vector<int>& visited_servers) {
    // Проверяем, не посещали ли уже этот сервер
    if (has_visited(server_id, visited_servers)) {
        return nullptr;
    }

    visited_servers.push_back(server_id);

    // Ищем локально
    {
        std::lock_guard<std::mutex> lock(clients_mutex);
        auto it = registered_clients.find(id);
        if (it != registered_clients.end()) {
            if (auto client = it->second.lock()) {
                return client;
            }
            else {
                // Удаляем недействительного клиента
                registered_clients.erase(it);
            }
        }
    }

    // Ищем на связанных серверах
    {
        std::lock_guard<std::mutex> lock(servers_mutex);
        for (const auto& weak_server : connected_servers) {
            if (auto server = weak_server.lock()) {
                // Проверяем, не посещали ли уже этот сервер
                if (!has_visited(server->get_id(), visited_servers)) {
                    auto client = server->get_by_id(id, visited_servers);
                    if (client) {
                        return client;
                    }
                }
            }
        }
    }

    return nullptr;
}

void Server::register_client(const std::shared_ptr<Client>& client) {
    if (!client) return;

    std::lock_guard<std::mutex> lock(clients_mutex);
    registered_clients[client->get_id()] = client;
    std::cout << "Клиент " << client->get_id() << " зарегистрирован на сервере " << server_id << std::endl;
}

void Server::unregister_client(int client_id) {
    std::lock_guard<std::mutex> lock(clients_mutex);
    auto it = registered_clients.find(client_id);
    if (it != registered_clients.end()) {
        registered_clients.erase(it);
        std::cout << "Клиент " << client_id << " удален с сервера " << server_id << std::endl;
    }
}

void Server::connect_to_server(const std::shared_ptr<Server>& other_server) {
    if (!other_server || other_server.get() == this) return;

    std::lock_guard<std::mutex> lock(servers_mutex);

    // Проверяем, не подключены ли уже
    for (const auto& weak_server : connected_servers) {
        if (auto server = weak_server.lock()) {
            if (server == other_server) {
                return;
            }
        }
    }

    connected_servers.push_back(other_server);

    // Двустороннее подключение
    other_server->connect_to_server(shared_from_this());

    std::cout << "Сервер " << server_id << " подключен к серверу " << other_server->get_id() << std::endl;
}

void Server::disconnect_from_server(const std::shared_ptr<Server>& other_server) {
    if (!other_server) return;

    std::lock_guard<std::mutex> lock(servers_mutex);

    auto it = std::remove_if(connected_servers.begin(), connected_servers.end(),
        [&](const std::weak_ptr<Server>& weak_server) {
            if (auto server = weak_server.lock()) {
                return server == other_server;
            }
            return false;
        });

    if (it != connected_servers.end()) {
        connected_servers.erase(it, connected_servers.end());
        other_server->disconnect_from_server(shared_from_this());
        std::cout << "Сервер " << server_id << " отключен от сервера " << other_server->get_id() << std::endl;
    }
}

int Server::generate_id_from_mac(const std::string& mac_addr) {
    // Отличающаяся хеш-функция для серверов
    std::hash<std::string> hasher;
    size_t hash = hasher("server_" + mac_addr);
    return static_cast<int>((hash & 0x7FFFFFFF) | 0x80000000); // Отрицательные числа для серверов
}

size_t Server::get_client_count() const {
    std::lock_guard<std::mutex> lock(const_cast<std::mutex&>(clients_mutex));
    return registered_clients.size();
}

size_t Server::get_server_count() const {
    std::lock_guard<std::mutex> lock(const_cast<std::mutex&>(servers_mutex));
    return connected_servers.size();
}

bool Server::has_visited(int srv_id, const std::vector<int>& visited_servers) const {
    return std::find(visited_servers.begin(), visited_servers.end(), srv_id) != visited_servers.end();
}

void Server::print_status() const {
    std::cout << "\n=== Статус Server ===" << std::endl;
    std::cout << "ID: " << server_id << std::endl;
    std::cout << "MAC: " << mac_address << std::endl;
    std::cout << "Зарегистрировано клиентов: " << get_client_count() << std::endl;
    std::cout << "Подключено серверов: " << get_server_count() << std::endl;
}