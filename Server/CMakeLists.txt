# Server библиотека
file(GLOB SERVER_HEADERS 
    ../Client/include/*.h
    include/*.h
)
file(GLOB SERVER_SOURCES 
    src/*.cpp
)

# Создаем статическую библиотеку
add_library(Server STATIC ${SERVER_SOURCES})

# Устанавливаем пути для include файлов
target_include_directories(Server
    PUBLIC 
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
        ${CMAKE_CURRENT_SOURCE_DIR}/../Client/include
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
)


# Устанавливаем свойства для библиотеки
set_target_properties(Server PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF
)

# Для многопоточности - используем Threads::Threads вместо pthread
target_link_libraries(Server Threads::Threads)

# Для Windows
if(WIN32)
    target_compile_definitions(Server PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()