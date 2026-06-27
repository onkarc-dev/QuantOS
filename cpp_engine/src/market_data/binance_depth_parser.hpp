#pragma once

#include "../engine_shared.hpp"
#include "../order_book.hpp"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <cstring>
#include <string>

namespace quantos::market_data::binance_depth_parser {

inline uint64_t read_uint_after(const std::string& view, const char* key) {
    const std::string pattern = std::string("\"") + key + "\":";
    const auto pos = view.find(pattern);
    if (pos == std::string::npos) return 0;
    return static_cast<uint64_t>(std::strtoull(view.c_str() + pos + pattern.size(), nullptr, 10));
}

inline bool read_string_after(const std::string& view, const char* key, char* out, std::size_t out_size) {
    if (out_size == 0) return false;
    const std::string pattern = std::string("\"") + key + "\":\"";
    const auto pos = view.find(pattern);
    if (pos == std::string::npos) return false;
    const auto start = pos + pattern.size();
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

inline std::size_t parse_side(const std::string& view,
                              const char* key,
                              std::array<PriceLevelUpdate, L2Update::kMaxLevelsPerMessage>& out) {
    const std::string pattern = std::string("\"") + key + "\":";
    auto key_pos = view.find(pattern);
    if (key_pos == std::string::npos) return 0;
    auto outer_open = view.find('[', key_pos + pattern.size());
    if (outer_open == std::string::npos) return 0;
    const auto outer_close = matching_array_end(view, outer_open);
    if (outer_close == std::string::npos || outer_close <= outer_open) return 0;

    std::size_t count = 0;
    std::size_t pos = outer_open + 1;
    while (pos < outer_close && count < out.size()) {
        const auto level_open = view.find('[', pos);
        if (level_open == std::string::npos || level_open >= outer_close) break;
        const auto price_quote = view.find('"', level_open);
        if (price_quote == std::string::npos || price_quote >= outer_close) break;
        const auto price_end = view.find('"', price_quote + 1);
        if (price_end == std::string::npos || price_end >= outer_close) break;
        const auto qty_quote = view.find('"', price_end + 1);
        if (qty_quote == std::string::npos || qty_quote >= outer_close) break;
        const auto qty_end = view.find('"', qty_quote + 1);
        if (qty_end == std::string::npos || qty_end >= outer_close) break;

        out[count].price = std::strtod(view.c_str() + price_quote + 1, nullptr);
        out[count].quantity = std::strtod(view.c_str() + qty_quote + 1, nullptr);
        ++count;
        pos = qty_end + 1;
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
