#include <algorithm>
#include <chrono>
#include <iostream>
#include <numeric>
#include <string>
#include <thread>
#include <vector>
#include "adapters/MarketDataAdapter.hpp"

static std::string arg(int argc, char** argv, const std::string& key, const std::string& def) {
    for (int i = 1; i + 1 < argc; ++i) if (argv[i] == key) return argv[i + 1];
    return def;
}

int main(int argc, char** argv) {
    const auto token = arg(argc, argv, "--token", "");
    const auto mode = arg(argc, argv, "--mode", "paper");
    const auto exchange = arg(argc, argv, "--exchange", "binance");
    const auto symbol_arg = arg(argc, argv, "--symbol", "");
    const auto source = symbol_arg.empty() ? arg(argc, argv, "--source", "BTCUSDT") : symbol_arg;
    if (token.empty()) {
        std::cerr << "quantos-engine requires --token. No exchange API secrets are accepted by this command.\n";
        return 2;
    }
    quantos::adapters::BinanceWebSocketAdapter adapter(source);
    if (!adapter.connect()) return 3;
    std::vector<double> samples;
    for (int i = 0; i < 5; ++i) {
        const auto start = std::chrono::high_resolution_clock::now();
        auto ev = adapter.poll();
        const auto end = std::chrono::high_resolution_clock::now();
        samples.push_back(static_cast<double>(std::chrono::duration_cast<std::chrono::microseconds>(end - start).count()));
        std::sort(samples.begin(), samples.end());
        auto pct = [&](double q) { return samples[std::min(samples.size() - 1, static_cast<size_t>(q * (samples.size() - 1)))]; };
        std::cout << "heartbeat mode=" << mode << " exchange=" << exchange << " source=" << source
                  << " engine_version=0.1.0 p50_us=" << pct(0.50) << " p95_us=" << pct(0.95)
                  << " p99_us=" << pct(0.99) << " status=" << (ev ? ev->message : "empty") << "\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(250));
    }
    adapter.disconnect();
    return 0;
}
