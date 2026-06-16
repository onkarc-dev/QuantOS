#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#include "../src/engine_shared.hpp"
#include "../src/order_book.hpp"
#include "../src/time_utils.hpp"

TradeQueue trade_queue;
std::atomic<bool> running{true};

static uint64_t percentile(std::vector<uint64_t>& values, double p) {
    if (values.empty()) return 0;
    std::sort(values.begin(), values.end());
    const size_t idx = static_cast<size_t>((p / 100.0) * (values.size() - 1));
    return values[idx];
}

int main(int argc, char** argv) {
    uint64_t total_messages = 10'000'000;
    uint64_t target_rate_per_sec = 0; // 0 = unlimited stress mode
    if (argc >= 2) total_messages = std::stoull(argv[1]);
    if (argc >= 3) target_rate_per_sec = std::stoull(argv[2]);

    FastOrderBook book;
    std::atomic<uint64_t> processed{0};
    std::vector<uint64_t> latencies;
    latencies.reserve(static_cast<size_t>(std::min<uint64_t>(total_messages, 5'000'000)));

    auto start_time = std::chrono::steady_clock::now();

    std::thread consumer([&]() {
        TradePacket p{};
        while (processed.load(std::memory_order_relaxed) < total_messages) {
            if (trade_queue.pop(p)) {
                const uint64_t receive_ns = now_ns();
                book.match(p);
                const uint64_t latency = receive_ns - p.ingest_ts_ns;
                if (latencies.size() < latencies.capacity()) latencies.push_back(latency);
                processed.fetch_add(1, std::memory_order_relaxed);
            } else {
                PAUSE();
            }
        }
    });

    TradePacket packet{};
    std::memcpy(packet.symbol, "BTCUSDT", 7);
    packet.price = 65000.0;
    packet.volume = 0.01;

    const uint64_t start_ns = now_ns();
    const uint64_t interval_ns = target_rate_per_sec ? (1'000'000'000ULL / target_rate_per_sec) : 0;

    for (uint64_t i = 0; i < total_messages; ++i) {
        if (interval_ns > 0) {
            const uint64_t due = start_ns + i * interval_ns;
            while (now_ns() < due) PAUSE();
        }
        packet.price += 0.01;
        packet.volume = 0.01 + static_cast<double>(i % 100) * 0.0001;
        packet.ingest_ts_ns = now_ns();
        packet.exchange_ts_ns = packet.ingest_ts_ns;
        packet.trade_id = i;

        while (!trade_queue.push(packet)) PAUSE();
    }

    consumer.join();

    auto end_time = std::chrono::steady_clock::now();
    const double seconds = std::chrono::duration<double>(end_time - start_time).count();
    const double msg_per_sec = static_cast<double>(total_messages) / seconds;

    uint64_t p50 = percentile(latencies, 50.0);
    uint64_t p90 = percentile(latencies, 90.0);
    uint64_t p99 = percentile(latencies, 99.0);
    uint64_t p999 = percentile(latencies, 99.9);

    std::cout << "===== Engine-only benchmark =====\n";
    std::cout << "mode: " << (target_rate_per_sec ? "rate-limited" : "unlimited-stress") << "\n";
    std::cout << "target_rate_msg_per_sec: " << target_rate_per_sec << "\n";
    std::cout << "messages_processed: " << processed.load() << "\n";
    std::cout << "elapsed_seconds: " << seconds << "\n";
    std::cout << "throughput_msg_per_sec: " << static_cast<uint64_t>(msg_per_sec) << "\n";
    std::cout << "latency_p50_ns: " << p50 << "\n";
    std::cout << "latency_p90_ns: " << p90 << "\n";
    std::cout << "latency_p99_ns: " << p99 << "\n";
    std::cout << "latency_p999_ns: " << p999 << "\n";
    std::cout << "latency_p99_ms: " << static_cast<double>(p99) / 1'000'000.0 << "\n";
    std::cout << "book_updates: " << book.updates() << "\n";
    std::cout << "last_price: " << book.last_price() << "\n";
    return 0;
}
