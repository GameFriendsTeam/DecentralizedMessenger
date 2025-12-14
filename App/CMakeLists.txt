# Основное приложение
set(APP_SOURCES
    src/main.cpp
    src/ConfigManager.cpp
    src/NetworkManager.cpp
    src/CommandHandler.cpp
)

set(APP_HEADERS
    include/ConfigManager.h
    include/NetworkManager.h
    include/CommandHandler.h
)

add_executable(DM-App ${APP_SOURCES})

# Подключаем библиотеки
target_link_libraries(DM-App
    Client
    Server
    Threads::Threads  # Используем Threads вместо pthread
)

# Устанавливаем пути для include файлов
target_include_directories(DM-App
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${CMAKE_CURRENT_SOURCE_DIR}/../Client/include
        ${CMAKE_CURRENT_SOURCE_DIR}/../Server/include
)

# Для Windows
if(WIN32)
    target_compile_definitions(DM-App PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()

# Устанавливаем свойства
set_target_properties(DM-App PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF
    OUTPUT_NAME "dm"
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    DEBUG_POSTFIX "_d"
    RELEASE_POSTFIX ""
)

# Установочные пути
install(TARGETS DM-App
    RUNTIME DESTINATION bin
    COMPONENT applications
)