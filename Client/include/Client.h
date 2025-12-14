#ifndef CLIENT_H
#define CLIENT_H

#include <string>
#include <vector>
#include <map>
#include <memory>
#include <mutex>
#include <functional>

// Предварительное объявление для избежания циклических зависимостей
class Server;

struct Message {
    int from_id;
    int to_id;
    std::string content;
    std::string timestamp;
    
    Message() : from_id(0), to_id(0) {}
    Message(int from, int to, const std::string& msg) 
        : from_id(from), to_id(to), content(msg) {}
};

class Client : public std::enable_shared_from_this<Client> {
private:
    int self_id;
    std::string mac_address;
    std::vector<std::shared_ptr<Server>> known_servers;
    std::map<int, std::vector<Message>> chat_history;
    std::mutex history_mutex;
    
    // Callback для получения входящих сообщений
    std::function<void(int, const std::string&)> message_callback;
    
public:
    explicit Client(const std::string& mac_addr);
    ~Client();
    
    // Основные методы
    bool set_self_id();
    void send_message(int target_id, const std::string& content);
    void receive_message(int from_id, const std::string& content);
    
    // Работа с чатами
    std::vector<Message> get_chat_by_id(int other_id) const;
    void set_chat_by_id(int other_id, const std::vector<Message>& history);
    void add_to_chat_history(int other_id, const Message& msg);
    
    // Сетевые методы
    void connect_to_server(const std::shared_ptr<Server>& server);
    void disconnect_from_server(const std::shared_ptr<Server>& server);
    
    // Геттеры
    int get_id() const { return self_id; }
    const std::string& get_mac() const { return mac_address; }
    
    // Callback management
    void set_message_callback(const std::function<void(int, const std::string&)>& callback);
    
    // Вспомогательные методы
    static int generate_id_from_mac(const std::string& mac_addr);
    bool is_id_available(int id, std::vector<int>& visited_servers);
    
    // Для отладки
    void print_status() const;
};

#endif // CLIENT_H