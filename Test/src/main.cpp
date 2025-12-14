#include "Client.h"
#include "Server.h"
#include <iostream>
#include <memory>
#include <thread>
#include <chrono>
#include <vector>

// Пример callback-функции для получения сообщений
void on_message_received(int from_id, const std::string& content) {
    std::cout << "\n[Callback] Получено сообщение от " << from_id 
              << ": " << content << std::endl;
}

int main() {
    std::cout << "=== Демонстрация P2P Mesh системы ===\n" << std::endl;
    
    // Создание серверов
    auto server1 = std::make_shared<Server>("00:1A:2B:3C:4D:5E");
    auto server2 = std::make_shared<Server>("00:1A:2B:3C:4D:5F");
    auto server3 = std::make_shared<Server>("00:1A:2B:3C:4D:60");
    
    // Установка ID серверов
    server1->set_self_id();
    server2->set_self_id();
    server3->set_self_id();
    
    // Соединение серверов в mesh
    server1->connect_to_server(server2);
    server2->connect_to_server(server3);
    server1->connect_to_server(server3);
    
    // Создание клиентов
    auto client1 = std::make_shared<Client>("AA:BB:CC:DD:EE:01");
    auto client2 = std::make_shared<Client>("AA:BB:CC:DD:EE:02");
    auto client3 = std::make_shared<Client>("AA:BB:CC:DD:EE:03");
    auto client4 = std::make_shared<Client>("AA:BB:CC:DD:EE:04");
    
    // Установка callback для получения сообщений
    client1->set_message_callback(on_message_received);
    client2->set_message_callback(on_message_received);
    client3->set_message_callback(on_message_received);
    client4->set_message_callback(on_message_received);
    
    // Подключение клиентов к серверам
    client1->connect_to_server(server1);
    client2->connect_to_server(server2);
    client3->connect_to_server(server3);
    client4->connect_to_server(server1); // Еще один клиент на сервере 1
    
    // Установка ID клиентов (с проверкой коллизий)
    std::cout << "\n=== Установка ID клиентов ===" << std::endl;
    client1->set_self_id();
    client2->set_self_id();
    client3->set_self_id();
    client4->set_self_id();
    
    std::this_thread::sleep_for(std::chrono::seconds(1));
    
    // Демонстрация отправки сообщений
    std::cout << "\n=== Отправка сообщений ===" << std::endl;
    
    // Клиент 1 отправляет сообщение клиенту 2
    client1->send_message(client2->get_id(), "Привет от клиента 1!");
    
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
    // Клиент 2 отправляет ответ
    client2->send_message(client1->get_id(), "Привет! Как дела?");
    
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
    // Клиент 3 отправляет сообщение клиенту 1 (через mesh сеть)
    client3->send_message(client1->get_id(), "Всем привет от клиента 3!");
    
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
    // Клиент 4 отправляет сообщение клиенту 3
    client4->send_message(client3->get_id(), "Привет от нового клиента 4!");
    
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
    // Демонстрация получения истории чата
    std::cout << "\n=== История чата клиента 1 с клиентом 2 ===" << std::endl;
    auto history = client1->get_chat_by_id(client2->get_id());
    for (const auto& msg : history) {
        std::cout << "[" << msg.timestamp << "] " 
                  << msg.from_id << " -> " << msg.to_id 
                  << ": " << msg.content << std::endl;
    }
    
    // Демонстрация сохранения и загрузки истории чата
    std::cout << "\n=== Тест сохранения/загрузки истории ===" << std::endl;
    
    // Сохраняем историю
    auto saved_history = client1->get_chat_by_id(client2->get_id());
    
    // Очищаем локальную историю (имитация)
    std::vector<Message> empty_history;
    client1->set_chat_by_id(client2->get_id(), empty_history);
    
    std::cout << "История очищена. Сообщений: " 
              << client1->get_chat_by_id(client2->get_id()).size() << std::endl;
    
    // Восстанавливаем историю
    client1->set_chat_by_id(client2->get_id(), saved_history);
    
    std::cout << "История восстановлена. Сообщений: " 
              << client1->get_chat_by_id(client2->get_id()).size() << std::endl;
    
    // Тест поиска несуществующего клиента
    std::cout << "\n=== Тест поиска несуществующего клиента ===" << std::endl;
    client1->send_message(999999, "Сообщение несуществующему клиенту");
    
    // Отображение статуса
    std::cout << "\n=== Статус системы ===" << std::endl;
    server1->print_status();
    server2->print_status();
    server3->print_status();
    client1->print_status();
    client2->print_status();
    
    // Тест переподключения
    std::cout << "\n=== Тест переподключения ===" << std::endl;
    client1->disconnect_from_server(server1);
    client1->connect_to_server(server2);
    
    // Отправка сообщения после переподключения
    client1->send_message(client2->get_id(), "Сообщение после переподключения");
    
    std::cout << "\n=== Демонстрация завершена ===" << std::endl;
    
    return 0;
}