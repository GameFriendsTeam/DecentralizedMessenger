cmake_minimum_required(VERSION 3.15)
project(DecentarlizedMessenger VERSION 1.0.0)

# Устанавливаем стандарт C++17
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Разные флаги для разных компиляторов
if(MSVC)
    # Флаги для Visual Studio
    add_compile_options(/W4 /WX)
    # Отключаем конкретные предупреждения MSVC
    add_compile_options(/wd4996)  # _CRT_SECURE_NO_WARNINGS
    add_compile_options(/wd4267)  # conversion from size_t to int
    add_compile_options(/wd4244)  # conversion from 'type1' to 'type2'
else()
    # Флаги для GCC/Clang
    add_compile_options(-Wall -Wextra -Wpedantic -Werror)
endif()

# Включаем поддержку многопоточности
find_package(Threads REQUIRED)

# Политика для новых версий CMake
if(POLICY CMP0077)
    cmake_policy(SET CMP0077 NEW)
endif()

# Настройки для сборки
option(BUILD_TESTS "Build tests" OFF)
option(BUILD_SERVER "Build server executable" ON)
option(BUILD_CLIENT "Build client executable" ON)

# Поддиректории
add_subdirectory(Client)
add_subdirectory(Server)

if(BUILD_TESTS)
    add_subdirectory(Test)
endif()

# Основное приложение
add_subdirectory(App)