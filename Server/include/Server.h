#ifndef SERVER_H
#define SERVER_H

#include <memory>
#include <vector>
#include <map>
#include <mutex>
#include <string>

// Предварительное объявление
class Client;

class Server : public std::enable_shared_from_this<Server> {
private:
    int server_id;
    std::string mac_address;
    std::map<int, std::weak_ptr<Client>> registered_clients;
    std::vector<std::weak_ptr<Server>> connected_servers;
    std::mutex clients_mutex;
    std::mutex servers_mutex;

public:
    explicit Server(const std::string& mac_addr);

    // Основные методы
    bool set_self_id();
    std::shared_ptr<Client> get_by_id(int id, std::vector<int>& visited_servers);

    // Регистрация клиентов
    void register_client(const std::shared_ptr<Client>& client);
    void unregister_client(int client_id);

    // Связи между серверами
    void connect_to_server(const std::shared_ptr<Server>& other_server);
    void disconnect_from_server(const std::shared_ptr<Server>& other_server);

    // Геттеры
    int get_id() const { return server_id; }
    const std::string& get_mac() const { return mac_address; }

    // Вспомогательные методы
    static int generate_id_from_mac(const std::string& mac_addr);
    size_t get_client_count() const;
    size_t get_server_count() const;

    // Для отладки
    void print_status() const;

private:
    bool has_visited(int srv_id, const std::vector<int>& visited_servers) const;
};

#endif // SERVER_H