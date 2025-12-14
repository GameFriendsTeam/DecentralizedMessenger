set(EXE_NAME DM-App)

include(${CMAKE_SOURCE_DIR}/cmake/CopyDlls.cmake)

file(GLOB_RECURSE SOURCE_FILES
    ${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp
)

assign_source_groups("${CMAKE_CURRENT_SOURCE_DIR}/src" SOURCE_FILES "src")

add_executable(${EXE_NAME} ${SOURCE_FILES})

target_include_directories(${EXE_NAME}
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include
)

file(GLOB_RECURSE HEADER_FILES
    ${CMAKE_CURRENT_SOURCE_DIR}/include/*.h
    ${CMAKE_CURRENT_SOURCE_DIR}/include/*.hpp
)

assign_source_groups("${CMAKE_CURRENT_SOURCE_DIR}/include" HEADER_FILES "include")

target_sources(${EXE_NAME} PRIVATE
	${HEADER_FILES}
)

target_link_libraries(${EXE_NAME}
    Client-Lib
    Server-Lib
    Threads::Threads
)

if(WIN32)
    target_compile_definitions(${EXE_NAME} PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()

set_target_properties(DM-App PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF
    OUTPUT_NAME "dm"
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    DEBUG_POSTFIX "_d"
    RELEASE_POSTFIX ""
)

install(TARGETS DM-App
    RUNTIME DESTINATION bin
    COMPONENT applications
)