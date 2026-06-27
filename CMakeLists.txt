cmake_minimum_required(VERSION 3.20)
project(PRISMFlowLowLatencyEngine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(MSVC)
    add_compile_options(/O2 /Oi /Ot /EHsc /DNOMINMAX)
else()
    add_compile_options(-O3 -DNDEBUG)
endif()

add_executable(l3_order_book_tests
    tests/l3_order_book_tests.cpp
)

target_include_directories(l3_order_book_tests PRIVATE
    cpp_engine/src
)

add_executable(benchmark_engine
    cpp_engine/benchmarks/benchmark_engine.cpp
)

target_include_directories(benchmark_engine PRIVATE
    cpp_engine/src
)

# Live WebSocket engine dependencies.
set(LIVE_ENGINE_AVAILABLE FALSE)
set(LWS_INCLUDE_DIR "")
set(LWS_LINK_LIBS "")

if(WIN32)
    set(VCPKG_ROOT_DIR "C:/vcpkg")
    set(LWS_INCLUDE_DIR "${VCPKG_ROOT_DIR}/installed/x64-windows/include")
    set(LWS_LIB_DIR "${VCPKG_ROOT_DIR}/installed/x64-windows/lib")

    if(EXISTS "${LWS_INCLUDE_DIR}/libwebsockets.h" AND EXISTS "${LWS_LIB_DIR}/websockets.lib")
        set(LIVE_ENGINE_AVAILABLE TRUE)
        set(LWS_LINK_LIBS "${LWS_LIB_DIR}/websockets.lib" ws2_32 crypt32 userenv iphlpapi secur32)
    endif()
else()
    find_path(LWS_INCLUDE_DIR
        NAMES libwebsockets.h
        PATHS
            /usr/include
            /usr/local/include
            /usr/include/libwebsockets
            /usr/local/include/libwebsockets
    )

    find_library(LWS_LIBRARY
        NAMES websockets libwebsockets
        PATHS
            /usr/lib
            /usr/local/lib
            /usr/lib/x86_64-linux-gnu
            /usr/local/lib/x86_64-linux-gnu
    )

    find_package(OpenSSL QUIET)

    if(LWS_INCLUDE_DIR AND LWS_LIBRARY)
        set(LIVE_ENGINE_AVAILABLE TRUE)
        set(LWS_LINK_LIBS ${LWS_LIBRARY})

        if(OpenSSL_FOUND)
            list(APPEND LWS_LINK_LIBS OpenSSL::SSL OpenSSL::Crypto)
        endif()

        list(APPEND LWS_LINK_LIBS z pthread)
        message(STATUS "libwebsockets found: include=${LWS_INCLUDE_DIR}, lib=${LWS_LIBRARY}")
    else()
        message(WARNING "libwebsockets not found by CMake search.")
        message(WARNING "LWS_INCLUDE_DIR=${LWS_INCLUDE_DIR}")
        message(WARNING "LWS_LIBRARY=${LWS_LIBRARY}")
    endif()
endif()

if(LIVE_ENGINE_AVAILABLE)

    add_executable(live_binance_engine
        cpp_engine/src/live_binance_engine.cpp
        cpp_engine/src/prism_live_engine.cpp
        cpp_engine/src/prism_strategy.cpp
        cpp_engine/src/trade_manager.cpp
        cpp_engine/src/connectors/BinanceClient.cpp
    )

    target_include_directories(live_binance_engine PRIVATE
        cpp_engine/src
        cpp_engine/src/connectors
        ${LWS_INCLUDE_DIR}
    )

    target_link_libraries(live_binance_engine PRIVATE ${LWS_LINK_LIBS})

    message(STATUS "live_binance_engine enabled with PRISM and TradeManager")

    add_executable(prism_live_paper_trading
        cpp_engine/src/apps/prism_live_paper_trading_app.cpp
        cpp_engine/src/prism_live_engine.cpp
        cpp_engine/src/prism_strategy.cpp
        cpp_engine/src/connectors/BinanceClient.cpp
        cpp_engine/src/raw_market_queue.cpp
    )

    target_include_directories(prism_live_paper_trading PRIVATE
        cpp_engine/src
        cpp_engine/src/connectors
        cpp_engine/src/trading
        cpp_engine/src/storage
        cpp_engine/src/dashboard
        ${LWS_INCLUDE_DIR}
    )

    target_link_libraries(prism_live_paper_trading PRIVATE ${LWS_LINK_LIBS})

    message(STATUS "prism_live_paper_trading enabled with Binance live feed + C++ PaperBroker")

else()
    message(WARNING "libwebsockets not found. live_binance_engine and prism_live_paper_trading skipped.")
endif()

find_package(protobuf CONFIG QUIET)
find_package(RdKafka CONFIG QUIET)

set(RDKAFKA_TARGET "")

if(TARGET RdKafka::rdkafka++)
    set(RDKAFKA_TARGET RdKafka::rdkafka++)
elseif(TARGET RdKafka::rdkafka)
    set(RDKAFKA_TARGET RdKafka::rdkafka)
elseif(TARGET rdkafka++)
    set(RDKAFKA_TARGET rdkafka++)
endif()

if(protobuf_FOUND AND RDKAFKA_TARGET)

    add_library(proto_lib)

    protobuf_generate(
        TARGET proto_lib
        LANGUAGE cpp
        PROTOS ${CMAKE_CURRENT_SOURCE_DIR}/proto/market_data.proto
    )

    target_include_directories(proto_lib PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}>
        $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}/proto>
    )

    target_link_libraries(proto_lib PUBLIC protobuf::libprotobuf)

    add_executable(kafka_producer cpp_engine/src/producer.cpp)
    add_executable(kafka_consumer cpp_engine/src/consumer.cpp)

    foreach(target kafka_producer kafka_consumer)
        target_include_directories(${target} PRIVATE
            ${CMAKE_CURRENT_BINARY_DIR}
            ${CMAKE_CURRENT_BINARY_DIR}/proto
        )

        target_link_libraries(${target} PRIVATE
            proto_lib
            ${RDKAFKA_TARGET}
        )

        add_dependencies(${target} proto_lib)
    endforeach()

    message(STATUS "Kafka producer/consumer enabled")

else()
    message(WARNING "protobuf and/or librdkafka not found. Kafka targets skipped.")
endif()

add_executable(prism_backtest
    cpp_engine/src/prism_backtest.cpp
)

target_include_directories(prism_backtest PRIVATE
    cpp_engine/src
)

add_executable(prism_cpp_heavy_paper
    cpp_engine/src/apps/prism_paper_trading_app.cpp
    cpp_engine/src/prism_live_engine.cpp
    cpp_engine/src/prism_strategy.cpp
)

target_include_directories(prism_cpp_heavy_paper PRIVATE
    cpp_engine/src
    cpp_engine/src/trading
    cpp_engine/src/storage
    cpp_engine/src/dashboard
)
