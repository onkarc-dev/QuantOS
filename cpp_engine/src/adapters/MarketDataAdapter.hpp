#pragma once
#include <algorithm>
#include <chrono>
#include <cctype>
#include <cstdlib>
#include <optional>
#include <queue>
#include <string>
#include <string_view>
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

inline std::string lower_copy(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return value;
}

inline std::string upper_copy(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) {
        return static_cast<char>(std::toupper(c));
    });
    return value;
}

inline bool extract_json_string(std::string_view json, const char* key, std::string& out) {
    const std::string pattern = std::string("\"") + key + "\":\"";
    const auto pos = json.find(pattern);
    if (pos == std::string_view::npos) return false;
    const auto start = pos + pattern.size();
    const auto end = json.find('"', start);
    if (end == std::string_view::npos) return false;
    out.assign(json.substr(start, end - start));
    return true;
}

inline double extract_json_double_string(std::string_view json, const char* key) {
    std::string raw;
    if (!extract_json_string(json, key, raw)) return 0.0;
    return std::strtod(raw.c_str(), nullptr);
}

inline long long extract_json_int(std::string_view json, const char* key) {
    const std::string pattern = std::string("\"") + key + "\":";
    const auto pos = json.find(pattern);
    if (pos == std::string_view::npos) return 0;
    const auto start = pos + pattern.size();
    return static_cast<long long>(std::strtoll(json.data() + start, nullptr, 10));
}

class BinanceWebSocketAdapter final : public MarketDataAdapter {
public:
    explicit BinanceWebSocketAdapter(std::string symbol = "BTCUSDT")
        : symbol_(upper_copy(std::move(symbol))), stream_symbol_(lower_copy(symbol_)) {
        websocket_url_ = "wss://stream.binance.com:9443/ws/" + stream_symbol_ + "@trade";
    }
    std::string name() const override { return "BinanceWebSocketAdapter"; }
    std::string websocket_url() const { return websocket_url_; }
    bool connect() override {
        connected_ = true;
        queued_.push(NormalizedMarketEvent{
            NormalizedEventType::Heartbeat,
            name(),
            symbol_,
            std::nullopt,
            std::nullopt,
            std::nullopt,
            std::nullopt,
            "local-adapter-ready websocket_url=" + websocket_url_
        });
        return true;
    }
    void disconnect() override { connected_ = false; }
    std::optional<NormalizedMarketEvent> poll() override {
        if (!connected_) return std::nullopt;
        if (!queued_.empty()) {
            auto event = queued_.front();
            queued_.pop();
            return event;
        }
        return NormalizedMarketEvent{NormalizedEventType::Heartbeat, name(), symbol_, std::nullopt, std::nullopt, std::nullopt, std::nullopt, "connected websocket_url=" + websocket_url_};
    }
    bool ingest_public_message(const std::string& payload) {
        auto event = parse_trade_message(payload);
        if (!event) return false;
        queued_.push(*event);
        return true;
    }
    std::optional<NormalizedMarketEvent> parse_trade_message(std::string_view payload) const {
        std::string event_type;
        if (!extract_json_string(payload, "e", event_type) || event_type != "trade") {
            return std::nullopt;
        }
        std::string raw_symbol;
        extract_json_string(payload, "s", raw_symbol);
        const auto symbol = raw_symbol.empty() ? symbol_ : upper_copy(raw_symbol);
        const double price = extract_json_double_string(payload, "p");
        const double quantity = extract_json_double_string(payload, "q");
        const long long ts = extract_json_int(payload, "T");
        if (price <= 0.0 || quantity <= 0.0 || ts <= 0) return std::nullopt;
        const auto side = payload.find("\"m\":true") != std::string_view::npos ? "sell" : "buy";
        Trade trade{ts, symbol, price, quantity, side};
        Tick tick{ts, symbol, price, quantity};
        return NormalizedMarketEvent{
            NormalizedEventType::Trade,
            name(),
            symbol,
            std::nullopt,
            tick,
            std::nullopt,
            trade,
            "binance-public-trade"
        };
    }
private:
    std::string symbol_;
    std::string stream_symbol_;
    std::string websocket_url_;
    bool connected_{false};
    std::queue<NormalizedMarketEvent> queued_;
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
