#ifndef NETWORKMANAGER_H
#define NETWORKMANAGER_H

#include <memory>
#include <thread>
#include <atomic>
#include <mutex>
#include <queue>
#include <condition_variable>
#include <string>
#include <functional>

// Предварительные объявления
class Client;
class Server;

class NetworkManager {
private:
    std::shared_ptr<Server> server_;
    std::shared_ptr<Client> client_;
    std::atomic<bool> running_;
    std::thread server_thread_;
    std::thread client_thread_;
    std::mutex message_mutex_;
    std::condition_variable message_cv_;
    std::queue<std::pair<int, std::string>> message_queue_;
    
    // Callback для сообщений
    std::function<void(int, const std::string&)> message_callback_;
    
    // Статистика
    struct {
        int messages_sent = 0;
        int messages_received = 0;
        int connections = 0;
    } stats_;
    
public:
    NetworkManager();
    ~NetworkManager();
    
    bool initialize(bool as_server, const std::string& mac_address = "");
    void shutdown();
    
    // Работа с сообщениями
    void send_message(int target_id, const std::string& content);
    bool receive_message(int& from_id, std::string& content, int timeout_ms = 100);
    
    // Серверные функции
    bool start_server(const std::string& mac_address);
    bool connect_to_server(const std::string& server_address);
    
    // Клиентские функции
    bool start_client(const std::string& mac_address);
    
    // Статистика
    void print_stats() const;
    void reset_stats();
    
    // Callback management
    void set_message_callback(std::function<void(int, const std::string&)> callback);
    
private:
    void server_worker();
    void client_worker();
    void process_message_queue();
    
    // Вспомогательные методы
    void on_client_message_received(int from_id, const std::string& content);
};

#endif // NETWORKMANAGER_H