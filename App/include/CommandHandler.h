#ifndef COMMANDHANDLER_H
#define COMMANDHANDLER_H

#include <string>
#include <vector>
#include <map>
#include <functional>
#include <memory>
#include <atomic>

// Вместо предварительного объявления, подключаем полный заголовок
#include "NetworkManager.h"

class CommandHandler {
private:
    std::shared_ptr<NetworkManager> network_manager_;
    std::map<std::string, std::function<void(const std::vector<std::string>&)>> commands_;
    std::atomic<bool> exit_requested_;
    
public:
    CommandHandler(std::shared_ptr<NetworkManager> network_manager);
    
    void register_commands();
    void process_command(const std::string& command_line);
    void run_interactive();
    void run_script(const std::string& script_file);
    
    bool is_exit_requested() const { return exit_requested_; }
    
private:
    // Команды
    void cmd_help(const std::vector<std::string>& args);
    void cmd_send(const std::vector<std::string>& args);
    void cmd_list(const std::vector<std::string>& args);
    void cmd_connect(const std::vector<std::string>& args);
    void cmd_disconnect(const std::vector<std::string>& args);
    void cmd_status(const std::vector<std::string>& args);
    void cmd_history(const std::vector<std::string>& args);
    void cmd_clear(const std::vector<std::string>& args);
    void cmd_exit(const std::vector<std::string>& args);
    
    // Вспомогательные методы
    void print_usage() const;
    void print_banner() const;
    std::vector<std::string> split_command(const std::string& command_line) const;
};

#endif // COMMANDHANDLER_H