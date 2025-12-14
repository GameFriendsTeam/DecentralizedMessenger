set(EXE_NAME DM-App)

file(GLOB_RECURSE APP_SOURCES
    src/*.cpp
)

file(GLOB_RECURSE APP_HEADERS
    include/*.h
    include/*.hpp
)

add_executable(${EXE_NAME}
    ${APP_SOURCES}
    ${APP_HEADERS}
)

target_include_directories(${EXE_NAME}
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
		${CMAKE_SOURCE_DIR}/external/third_party/asio/include
)

if (WIN32)
    target_compile_definitions(${EXE_NAME}
        PRIVATE _CRT_SECURE_NO_WARNINGS
    )
endif()
