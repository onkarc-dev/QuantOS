#pragma once

#include "../engine_shared.hpp"
#include "../order_book.hpp"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <cstring>
#include <string>

namespace quantos::market_data::binance_depth_parser {

inline std::size_t skip_ws(const std::string& view, std::size_t pos) {
    while (pos < view.size() && std::isspace(static_cast<unsigned char>(view[pos]))) ++pos;
    return pos;
}

inline uint64_t read_uint_after(const std::string& view, const char* key) {
    const std::string pattern = std::string("\"") + key + "\"";
    const auto key_pos = view.find(pattern);
    if (key_pos == std::string::npos) return 0;
    auto colon = view.find(':', key_pos + pattern.size());
    if (colon == std::string::npos) return 0;
    const auto value_pos = skip_ws(view, colon + 1);
    return static_cast<uint64_t>(std::strtoull(view.c_str() + value_pos, nullptr, 10));
}

inline bool read_string_after(const std::string& view, const char* key, char* out, std::size_t out_size) {
    if (out_size == 0) return false;
    const std::string pattern = std::string("\"") + key + "\"";
    const auto key_pos = view.find(pattern);
    if (key_pos == std::string::npos) return false;
    auto colon = view.find(':', key_pos + pattern.size());
    if (colon == std::string::npos) return false;
    auto start = skip_ws(view, colon + 1);
    if (start >= view.size() || view[start] != '"') return false;
    ++start;
    const auto end = view.find('"', start);
    if (end == std::string::npos) return false;
    const std::size_t n = std::min(out_size - 1, end - start);
    std::memcpy(out, view.data() + start, n);
    out[n] = '\0';
    return true;
}

inline void lower_symbol(char* s) {
    for (; *s; ++s) *s = static_cast<char>(std::tolower(static_cast<unsigned char>(*s)));
}

inline std::size_t matching_array_end(const std::string& view, std::size_t array_open) {
    int depth = 0;
    bool in_string = false;
    bool escaped = false;
    for (std::size_t i = array_open; i < view.size(); ++i) {
        const char c = view[i];
        if (escaped) { escaped = false; continue; }
        if (c == '\\') { escaped = in_string; continue; }
        if (c == '"') { in_string = !in_string; continue; }
        if (in_string) continue;
        if (c == '[') ++depth;
        else if (c == ']') {
            --depth;
            if (depth == 0) return i;
        }
    }
    return std::string::npos;
}

inline bool parse_number_token(const std::string& view, std::size_t& pos, std::size_t limit, double& out) {
    pos = skip_ws(view, pos);
    if (pos >= limit) return false;

    const char* begin = view.c_str() + pos;
    char* end = nullptr;

    if (view[pos] == '"') {
        ++pos;
        begin = view.c_str() + pos;
        out = std::strtod(begin, &end);
        if (end == begin) return false;
        pos = static_cast<std::size_t>(end - view.c_str());
        if (pos >= limit || view[pos] != '"') return false;
        ++pos;
        return true;
    }

    out = std::strtod(begin, &end);
    if (end == begin) return false;
    pos = static_cast<std::size_t>(end - view.c_str());
    return pos <= limit;
}

inline std::size_t parse_side(const std::string& view,
                              const char* key,
                              std::array<PriceLevelUpdate, L2Update::kMaxLevelsPerMessage>& out) {
    const std::string pattern = std::string("\"") + key + "\"";
    auto key_pos = view.find(pattern);
    if (key_pos == std::string::npos) return 0;
    auto colon = view.find(':', key_pos + pattern.size());
    if (colon == std::string::npos) return 0;
    auto outer_open = view.find('[', colon + 1);
    if (outer_open == std::string::npos) return 0;
    const auto outer_close = matching_array_end(view, outer_open);
    if (outer_close == std::string::npos || outer_close <= outer_open) return 0;

    std::size_t count = 0;
    std::size_t pos = outer_open + 1;
    while (pos < outer_close && count < out.size()) {
        const auto level_open = view.find('[', pos);
        if (level_open == std::string::npos || level_open >= outer_close) break;
        const auto level_close = matching_array_end(view, level_open);
        if (level_close == std::string::npos || level_close > outer_close) break;

        std::size_t value_pos = level_open + 1;
        double price = 0.0;
        double quantity = 0.0;
        if (!parse_number_token(view, value_pos, level_close, price)) break;
        auto comma = view.find(',', value_pos);
        if (comma == std::string::npos || comma >= level_close) break;
        value_pos = comma + 1;
        if (!parse_number_token(view, value_pos, level_close, quantity)) break;

        out[count++] = PriceLevelUpdate{price, quantity};
        pos = level_close + 1;
    }

    return count;
}

inline bool parse_l2_update(const RawMarketMessage& raw, L2Update& out) {
    if (raw.len == 0) return false;
    const std::string view(raw.data, raw.len);
    if (view.find("depthUpdate") == std::string::npos) return false;

    L2Update update;
    update.ingest_ts_ns = raw.ingest_ts_ns;
    update.exchange_ts_ns = read_uint_after(view, "E") * 1000000ULL;
    update.first_sequence = read_uint_after(view, "U");
    update.final_sequence = read_uint_after(view, "u");
    update.previous_final_sequence = read_uint_after(view, "pu");

    if (!read_string_after(view, "s", update.symbol, sizeof(update.symbol))) {
        std::strncpy(update.symbol, "unknown", sizeof(update.symbol) - 1);
    }
    lower_symbol(update.symbol);

    update.bid_count = parse_side(view, "b", update.bids);
    update.ask_count = parse_side(view, "a", update.asks);

    if (update.bid_count == 0 && update.ask_count == 0) return false;
    out = update;
    return true;
}

} // namespace quantos::market_data::binance_depth_parser
