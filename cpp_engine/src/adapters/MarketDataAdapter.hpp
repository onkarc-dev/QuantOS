#pragma once
#include <chrono>
#include <optional>
#include <string>
#include <vector>

namespace quantos::adapters {

enum class NormalizedEventType { Candle, Tick, OrderBookUpdate, Trade, Heartbeat, Error };

struct Candle { long long timestamp_ms{}; double open{}, high{}, low{}, close{}, volume{}; };
struct Tick { long long timestamp_ms{}; std::string symbol; double price{}, size{}; };
struct OrderBookLevel { double price{}, quantity{}; };
struct OrderBookUpdate { long long timestamp_ms{}; std::string symbol; std::vector<OrderBookLevel> bids; std::vector<OrderBookLevel> asks; };
struct Trade { long long timestamp_ms{}; std::string symbol; double price{}, quantity{}; std::string side; };

struct NormalizedMarketEvent {
    NormalizedEventType type{NormalizedEventType::Heartbeat};
    std::string source;
    std::string symbol;
    std::optional<Candle> candle;
    std::optional<Tick> tick;
    std::optional<OrderBookUpdate> orderbook;
    std::optional<Trade> trade;
    std::string message;
};

class MarketDataAdapter {
public:
    virtual ~MarketDataAdapter() = default;
    virtual std::string name() const = 0;
    virtual bool connect() = 0;
    virtual void disconnect() = 0;
    virtual std::optional<NormalizedMarketEvent> poll() = 0;
};

class BinanceWebSocketAdapter final : public MarketDataAdapter {
public:
    explicit BinanceWebSocketAdapter(std::string symbol = "BTCUSDT") : symbol_(std::move(symbol)) {}
    std::string name() const override { return "BinanceWebSocketAdapter"; }
    bool connect() override { connected_ = true; return true; }
    void disconnect() override { connected_ = false; }
    std::optional<NormalizedMarketEvent> poll() override {
        if (!connected_) return std::nullopt;
        return NormalizedMarketEvent{NormalizedEventType::Heartbeat, name(), symbol_, std::nullopt, std::nullopt, std::nullopt, std::nullopt, "connected"};
    }
private:
    std::string symbol_;
    bool connected_{false};
};

class CsvFileAdapter final : public MarketDataAdapter {
public:
    explicit CsvFileAdapter(std::string path) : path_(std::move(path)) {}
    std::string name() const override { return "CsvFileAdapter"; }
    bool connect() override { connected_ = true; return true; }
    void disconnect() override { connected_ = false; }
    std::optional<NormalizedMarketEvent> poll() override {
        if (!connected_) return std::nullopt;
        return NormalizedMarketEvent{NormalizedEventType::Heartbeat, name(), path_, std::nullopt, std::nullopt, std::nullopt, std::nullopt, "csv-ready"};
    }
private:
    std::string path_;
    bool connected_{false};
};

class CustomWebSocketAdapter final : public MarketDataAdapter {
public:
    explicit CustomWebSocketAdapter(std::string endpoint) : endpoint_(std::move(endpoint)) {}
    std::string name() const override { return "CustomWebSocketAdapter"; }
    bool connect() override { connected_ = !endpoint_.empty(); return connected_; }
    void disconnect() override { connected_ = false; }
    std::optional<NormalizedMarketEvent> poll() override {
        if (!connected_) return NormalizedMarketEvent{NormalizedEventType::Error, name(), {}, std::nullopt, std::nullopt, std::nullopt, std::nullopt, "not-connected"};
        return NormalizedMarketEvent{NormalizedEventType::Heartbeat, name(), endpoint_, std::nullopt, std::nullopt, std::nullopt, std::nullopt, "connected"};
    }
private:
    std::string endpoint_;
    bool connected_{false};
};

} // namespace quantos::adapters
