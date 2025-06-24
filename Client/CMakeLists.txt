cmake_minimum_required(VERSION 3.13 FATAL_ERROR)

set(PROJECT_NAME DMNet-Client)

add_library(${PROJECT_NAME} SHARED src/Client.cpp)

target_include_directories(${PROJECT_NAME} PUBLIC include)

file(GLOB_RECURSE HEADER_FILES
    ${CMAKE_CURRENT_SOURCE_DIR}/include/*.h
    ${CMAKE_CURRENT_SOURCE_DIR}/include/*.hpp
)

target_sources(${PROJECT_NAME} PRIVATE
  ${HEADER_FILES}
)

if(WIN32)
    target_compile_definitions(${PROJECT_NAME} PRIVATE DMNET)
endif()