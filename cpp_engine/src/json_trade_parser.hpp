#pragma once

#include "engine_shared.hpp"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <cstring>
#include <string>
#include <string_view>

namespace json_trade_parser {

inline bool extract_json_string(
    const char* data,
    size_t len,
    const char* key,
    char* out,
    size_t out_size)
{
    if (out_size == 0) return false;
    const std::string_view view(data, len);
    const std::string pattern = std::string("\"") + key + "\":\"";
    const auto pos = view.find(pattern);
    if (pos == std::string_view::npos) return false;
    const auto start = pos + pattern.size();
    const auto end = view.find('"', start);
    if (end == std::string_view::npos) return false;
    const size_t n = std::min(out_size - 1, static_cast<size_t>(end - start));
    std::memcpy(out, view.data() + start, n);
    out[n] = '\0';
    return true;
}

inline double extract_json_double_string(const char* data, size_t len, const char* key)
{
    char tmp[64]{};
    if (!extract_json_string(data, len, key, tmp, sizeof(tmp))) return 0.0;
    return std::strtod(tmp, nullptr);
}

inline uint64_t extract_json_uint(const char* data, size_t len, const char* key)
{
    const std::string_view view(data, len);
    const std::string pattern = std::string("\"") + key + "\":";
    const auto pos = view.find(pattern);
    if (pos == std::string_view::npos) return 0;
    const auto start = pos + pattern.size();
    return static_cast<uint64_t>(std::strtoull(view.data() + start, nullptr, 10));
}

inline bool parse_trade_packet(const RawTradeMessage& raw, TradePacket& p)
{
    if (raw.len == 0) return false;

    char symbol[16]{};
    extract_json_string(raw.data, raw.len, "s", symbol, sizeof(symbol));

    p = TradePacket{};
    std::strncpy(p.symbol, symbol, sizeof(p.symbol) - 1);
    p.price = extract_json_double_string(raw.data, raw.len, "p");
    p.volume = extract_json_double_string(raw.data, raw.len, "q");
    p.trade_id = extract_json_uint(raw.data, raw.len, "t");
    p.exchange_ts_ns = extract_json_uint(raw.data, raw.len, "T") * 1000000ULL;
    p.ingest_ts_ns = raw.ingest_ts_ns;

    return p.price > 0.0 && p.volume > 0.0 && p.symbol[0] != '\0';
}

} // namespace json_trade_parser
