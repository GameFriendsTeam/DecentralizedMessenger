#ifndef CONFIGMANAGER_H
#define CONFIGMANAGER_H

#include <string>
#include <map>
#include <vector>
#include <memory>

struct ServerConfig {
    std::string address;
    int port;
    std::string mac_address;
    std::vector<std::string> peer_servers;
};

struct ClientConfig {
    std::string mac_address;
    std::vector<std::string> known_servers;
};

class ConfigManager {
private:
    std::map<std::string, std::string> config_;
    ServerConfig server_config_;
    ClientConfig client_config_;
    std::string config_file_;
    
public:
    ConfigManager(const std::string& config_file = "config.ini");
    
    bool load_config();
    bool save_config();
    
    // Серверные настройки
    ServerConfig get_server_config() const { return server_config_; }
    void set_server_config(const ServerConfig& config) { server_config_ = config; }
    
    // Клиентские настройки
    ClientConfig get_client_config() const { return client_config_; }
    void set_client_config(const ClientConfig& config) { client_config_ = config; }
    
    // Общие настройки
    std::string get_value(const std::string& key, const std::string& default_val = "") const;
    void set_value(const std::string& key, const std::string& value);
    
private:
    void parse_ini_file();
    void generate_mac_address();
    std::string read_mac_address() const;
};

#endif // CONFIGMANAGER_H