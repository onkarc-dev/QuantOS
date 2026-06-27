#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <unordered_map>
#include <utility>
#include <vector>

namespace quantos::market_data {

struct PriceLevelUpdate {
    double price = 0.0;
    double quantity = 0.0;
};

struct L2Update {
    static constexpr std::size_t kMaxLevelsPerMessage = 64;

    char symbol[16]{};
    uint64_t first_sequence = 0;
    uint64_t final_sequence = 0;
    uint64_t previous_final_sequence = 0;
    uint64_t exchange_ts_ns = 0;
    uint64_t ingest_ts_ns = 0;
    std::array<PriceLevelUpdate, kMaxLevelsPerMessage> bids{};
    std::array<PriceLevelUpdate, kMaxLevelsPerMessage> asks{};
    std::size_t bid_count = 0;
    std::size_t ask_count = 0;
};

struct BookSnapshot {
    double best_bid = 0.0;
    double best_ask = 0.0;
    double bid_depth = 0.0;
    double ask_depth = 0.0;
    double spread = 0.0;
    double mid_price = 0.0;
    double depth_imbalance = 0.0;
    double vwap_bid = 0.0;
    double vwap_ask = 0.0;
    uint64_t sequence = 0;
    uint64_t updates = 0;
    uint64_t invalid_updates = 0;
    bool crossed = false;
    bool valid = false;
};

class L2OrderBook {
public:
    explicit L2OrderBook(std::size_t reserved_levels = 4096) {
        bids_.reserve(reserved_levels);
        asks_.reserve(reserved_levels);
    }

    void clear() noexcept {
        bids_.clear();
        asks_.clear();
        last_sequence_ = 0;
        updates_ = 0;
        invalid_updates_ = 0;
    }

    bool apply_snapshot(const L2Update& snapshot) {
        Levels next_bids;
        Levels next_asks;
        next_bids.reserve(4096);
        next_asks.reserve(4096);
        apply_levels(next_bids, snapshot.bids, snapshot.bid_count);
        apply_levels(next_asks, snapshot.asks, snapshot.ask_count);

        if (is_crossed(next_bids, next_asks)) {
            ++invalid_updates_;
            return false;
        }

        bids_ = std::move(next_bids);
        asks_ = std::move(next_asks);
        last_sequence_ = snapshot.final_sequence;
        ++updates_;
        return true;
    }

    bool apply_incremental(const L2Update& update, bool validate_sequence = true) {
        if (validate_sequence && last_sequence_ != 0 && !sequence_is_contiguous(update)) {
            ++invalid_updates_;
            return false;
        }

        Levels next_bids = bids_;
        Levels next_asks = asks_;
        apply_levels(next_bids, update.bids, update.bid_count);
        apply_levels(next_asks, update.asks, update.ask_count);

        if (is_crossed(next_bids, next_asks)) {
            ++invalid_updates_;
            return false;
        }

        bids_ = std::move(next_bids);
        asks_ = std::move(next_asks);
        last_sequence_ = update.final_sequence ? update.final_sequence : last_sequence_ + 1;
        ++updates_;
        return true;
    }

    BookSnapshot snapshot(std::size_t depth_levels = 10) const {
        BookSnapshot s;
        s.best_bid = best_bid();
        s.best_ask = best_ask();
        s.crossed = is_crossed(bids_, asks_);
        s.spread = (s.best_bid > 0.0 && s.best_ask > 0.0) ? s.best_ask - s.best_bid : 0.0;
        s.mid_price = (s.best_bid > 0.0 && s.best_ask > 0.0) ? (s.best_bid + s.best_ask) * 0.5 : 0.0;
        s.bid_depth = side_depth(bids_, true, depth_levels);
        s.ask_depth = side_depth(asks_, false, depth_levels);
        const double total_depth = s.bid_depth + s.ask_depth;
        s.depth_imbalance = total_depth > 0.0 ? (s.bid_depth - s.ask_depth) / total_depth : 0.0;
        s.vwap_bid = side_vwap(bids_, true, depth_levels);
        s.vwap_ask = side_vwap(asks_, false, depth_levels);
        s.sequence = last_sequence_;
        s.updates = updates_;
        s.invalid_updates = invalid_updates_;
        s.valid = s.best_bid > 0.0 && s.best_ask > 0.0 && !s.crossed && s.spread > 0.0;
        return s;
    }

    double best_bid() const { return best_price(bids_, true); }
    double best_ask() const { return best_price(asks_, false); }
    uint64_t sequence() const noexcept { return last_sequence_; }
    uint64_t updates() const noexcept { return updates_; }
    uint64_t invalid_updates() const noexcept { return invalid_updates_; }
    std::size_t bid_levels() const noexcept { return bids_.size(); }
    std::size_t ask_levels() const noexcept { return asks_.size(); }

private:
    using Levels = std::unordered_map<int64_t, double>;
    static constexpr double kScale = 100000000.0;

    bool sequence_is_contiguous(const L2Update& update) const noexcept {
        if (update.final_sequence != 0 && update.final_sequence <= last_sequence_) {
            return false;
        }
        if (update.previous_final_sequence != 0) {
            return update.previous_final_sequence == last_sequence_;
        }
        if (update.first_sequence != 0 && update.final_sequence != 0) {
            return update.first_sequence <= last_sequence_ + 1 && update.final_sequence >= last_sequence_ + 1;
        }
        if (update.first_sequence != 0) {
            return update.first_sequence == last_sequence_ + 1;
        }
        return true;
    }

    static int64_t px(double price) noexcept {
        return static_cast<int64_t>(price * kScale + (price >= 0.0 ? 0.5 : -0.5));
    }

    static double unpx(int64_t price) noexcept {
        return static_cast<double>(price) / kScale;
    }

    static void apply_levels(Levels& levels,
                             const std::array<PriceLevelUpdate, L2Update::kMaxLevelsPerMessage>& updates,
                             std::size_t count) {
        const std::size_t capped = std::min(count, updates.size());
        for (std::size_t i = 0; i < capped; ++i) {
            upsert_level(levels, updates[i]);
        }
    }

    static void upsert_level(Levels& levels, const PriceLevelUpdate& update) {
        const int64_t key = px(update.price);
        if (key <= 0) return;
        if (update.quantity <= 0.0) {
            levels.erase(key);
        } else {
            levels[key] = update.quantity;
        }
    }

    static double best_price(const Levels& levels, bool bid) {
        if (levels.empty()) return 0.0;
        const auto it = bid
            ? std::max_element(levels.begin(), levels.end(), [](const auto& a, const auto& b) { return a.first < b.first; })
            : std::min_element(levels.begin(), levels.end(), [](const auto& a, const auto& b) { return a.first < b.first; });
        return it == levels.end() ? 0.0 : unpx(it->first);
    }

    static std::vector<std::pair<int64_t, double>> sorted_side(const Levels& levels, bool bid, std::size_t n) {
        std::vector<std::pair<int64_t, double>> out;
        out.reserve(std::min(n, levels.size()));
        for (const auto& kv : levels) out.push_back(kv);
        if (bid) {
            std::sort(out.begin(), out.end(), [](const auto& a, const auto& b) { return a.first > b.first; });
        } else {
            std::sort(out.begin(), out.end(), [](const auto& a, const auto& b) { return a.first < b.first; });
        }
        if (out.size() > n) out.resize(n);
        return out;
    }

    static double side_depth(const Levels& levels, bool bid, std::size_t n) {
        double qty = 0.0;
        for (const auto& kv : sorted_side(levels, bid, n)) qty += kv.second;
        return qty;
    }

    static double side_vwap(const Levels& levels, bool bid, std::size_t n) {
        double notional = 0.0;
        double qty = 0.0;
        for (const auto& kv : sorted_side(levels, bid, n)) {
            notional += unpx(kv.first) * kv.second;
            qty += kv.second;
        }
        return qty > 0.0 ? notional / qty : 0.0;
    }

    static bool is_crossed(const Levels& bids, const Levels& asks) {
        const double bid = best_price(bids, true);
        const double ask = best_price(asks, false);
        return bid > 0.0 && ask > 0.0 && bid >= ask;
    }

    Levels bids_;
    Levels asks_;
    uint64_t last_sequence_ = 0;
    uint64_t updates_ = 0;
    uint64_t invalid_updates_ = 0;
};

} // namespace quantos::market_data

using L2OrderBook = quantos::market_data::L2OrderBook;
using L2Update = quantos::market_data::L2Update;
using BookSnapshot = quantos::market_data::BookSnapshot;
