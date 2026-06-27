#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <string>

#include <libwebsockets.h>

class BinanceClient {
public:
    explicit BinanceClient(std::string symbol = "btcusdt", bool enable_depth_stream = true);
    ~BinanceClient();

    BinanceClient(const BinanceClient&) = delete;
    BinanceClient& operator=(const BinanceClient&) = delete;

    void run();
    void stop();
    uint64_t received() const noexcept { return received_.load(std::memory_order_relaxed); }
    uint64_t dropped() const noexcept { return dropped_.load(std::memory_order_relaxed); }
    uint64_t dropped_queue_full() const noexcept { return dropped_queue_full_.load(std::memory_order_relaxed); }
    uint64_t dropped_too_large() const noexcept { return dropped_too_large_.load(std::memory_order_relaxed); }
    uint64_t market_received() const noexcept { return market_received_.load(std::memory_order_relaxed); }
    uint64_t market_dropped() const noexcept { return market_dropped_.load(std::memory_order_relaxed); }
    bool connected() const noexcept { return connected_.load(std::memory_order_relaxed); }

    static int callback_ws(struct lws* wsi, enum lws_callback_reasons reason,
                           void* user, void* in, size_t len);

private:
    bool connect();
    void handle_message(const char* data, size_t len);
    void enqueue_trade(const char* data, size_t len, uint64_t ingest_ts_ns);
    void enqueue_market(const char* data, size_t len, uint64_t ingest_ts_ns);

    std::string symbol_;
    std::string path_;
    bool enable_depth_stream_ = true;
    struct lws_context* context_ = nullptr;
    struct lws* wsi_ = nullptr;
    std::atomic<bool> connected_{false};
    std::atomic<uint64_t> received_{0};
    std::atomic<uint64_t> dropped_{0};
    std::atomic<uint64_t> dropped_queue_full_{0};
    std::atomic<uint64_t> dropped_too_large_{0};
    std::atomic<uint64_t> market_received_{0};
    std::atomic<uint64_t> market_dropped_{0};
};
