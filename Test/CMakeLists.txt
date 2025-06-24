cmake_minimum_required(VERSION 3.13 FATAL_ERROR)

set(PROJECT_NAME DMNet-Test)

project(${PROJECT_NAME})

add_executable(${PROJECT_NAME} src/main.cpp)

target_link_libraries(${PROJECT_NAME} PRIVATE DMNet-Server)
target_link_libraries(${PROJECT_NAME} PRIVATE DMNet-Client)

target_include_directories(${PROJECT_NAME} PUBLIC include)

if (WIN32)
    add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            $<TARGET_FILE:DMNet-Server>
            $<TARGET_FILE_DIR:${PROJECT_NAME}>
    )

    add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
            $<TARGET_FILE:DMNet-Client>
            $<TARGET_FILE_DIR:${PROJECT_NAME}>
    )
endif() 