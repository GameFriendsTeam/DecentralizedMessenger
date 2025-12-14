# Тестовое приложение
add_executable(DM-Test
    src/main.cpp
)

# Подключаем библиотеки
target_link_libraries(DM-Test
    Client
    Server
)

# Устанавливаем пути для include файлов
target_include_directories(DM-Test
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${CMAKE_CURRENT_SOURCE_DIR}/../Client/include
        ${CMAKE_CURRENT_SOURCE_DIR}/../Server/include
)

# Оптимизация для релиза
set_target_properties(DM-Test PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON
)


# Set default compile flags for GCC
if(CMAKE_COMPILER_IS_GNUCXX)
    message(STATUS "GCC detected, adding compile flags")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++98 -pedantic -Wall -Wextra")
endif(CMAKE_COMPILER_IS_GNUCXX)