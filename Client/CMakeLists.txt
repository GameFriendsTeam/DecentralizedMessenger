# Client библиотека

set(CLIENT Client-Lib)

include(${CMAKE_SOURCE_DIR}/cmake/CopyDlls.cmake)

file(GLOB_RECURSE SOURCE_FILES
    ${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp
)

assign_source_groups("${CMAKE_CURRENT_SOURCE_DIR}/src" SOURCE_FILES "src")

add_library(${CLIENT} STATIC ${SOURCE_FILES})

target_include_directories(${CLIENT}
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include
)

file(GLOB_RECURSE HEADER_FILES
    ${CMAKE_CURRENT_SOURCE_DIR}/include/*.h
    ${CMAKE_CURRENT_SOURCE_DIR}/include/*.hpp
)

assign_source_groups("${CMAKE_CURRENT_SOURCE_DIR}/include" HEADER_FILES "include")

target_sources(${CLIENT} PRIVATE
	${HEADER_FILES}
)

set_target_properties(${CLIENT} PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF
)

# Для многопоточности - используем Threads::Threads вместо pthread
target_link_libraries(${CLIENT} Threads::Threads)

# Для Windows
if(WIN32)
    target_compile_definitions(${CLIENT} PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()