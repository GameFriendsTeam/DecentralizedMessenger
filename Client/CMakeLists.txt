# Client библиотека

file(GLOB CLIENT_HEADERS 
    ../Server/include/*.h
    include/*.h
)
file(GLOB CLIENT_SOURCES 
    src/*.cpp
)

# Создаем статическую библиотеку
add_library(Client STATIC ${CLIENT_SOURCES})

# Устанавливаем пути для include файлов
target_include_directories(Client
    PUBLIC 
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
        ${CMAKE_CURRENT_SOURCE_DIR}/../Server/include
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Устанавливаем свойства для библиотеки
set_target_properties(Client PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF
)

# Для многопоточности - используем Threads::Threads вместо pthread
target_link_libraries(Client Threads::Threads)

# Для Windows
if(WIN32)
    target_compile_definitions(Client PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()