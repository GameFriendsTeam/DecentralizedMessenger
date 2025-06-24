cmake_minimum_required(VERSION 3.13 FATAL_ERROR)

set(PROJECT_NAME DMNet)

project(${PROJECT_NAME} VERSION 0.0.1)

add_subdirectory(Server)
add_subdirectory(Client)
add_subdirectory(Test)