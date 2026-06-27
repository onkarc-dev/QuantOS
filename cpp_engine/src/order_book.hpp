#pragma once

#include "engine_shared.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <limits>
#include <unordered_map>
#include <vector>

namespace quantos::market_data {

enum class BookSide : uint8_t { Bid = 0, Ask = 1 };
enum class L3Action : uint8_t { Insert = 0, Modify = 1, Cancel = 2, Trade = 3 };

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

struct L3Order {
    uint64_t order_id = 0;
    double price = 0.0;
    double quantity = 0.0;
    uint64_t timestamp_ns = 0;
    BookSide side = BookSide::Bid;
    uint64_t exchange_sequence = 0;
    uint32_t queue_position = 0;
};

struct L3Update {
    char symbol[16]{};
    L3Action action = L3Action::Insert;
    uint64_t order_id = 0;
    double price = 0.0;
    double quantity = 0.0;
    uint64_t timestamp_ns = 0;
    BookSide side = BookSide::Bid;
    uint64_t exchange_sequence = 0;
};

class L2OrderBook {
public:
    explicit L2OrderBook(std::size_t reserved_levels = 4096) {
        bids_.reserve(reserved_levels);
        asks_.reserve(reserved_levels);
    }

    L2OrderBook(const L2OrderBook&) = delete;
    L2OrderBook& operator=(const L2OrderBook&) = delete;
    L2OrderBook(L2OrderBook&&) noexcept = default;
    L2OrderBook& operator=(L2OrderBook&&) noexcept = default;

    void clear() noexcept {
        bids_.clear();
        asks_.clear();
        last_sequence_ = 0;
        updates_ = 0;
        invalid_updates_ = 0;
    }

    bool apply_snapshot(const L2Update& snapshot) {
        bids_.clear();
        asks_.clear();
        last_sequence_ = 0;
        const bool ok = apply_incremental(snapshot, false);
        last_sequence_ = snapshot.final_sequence;
        return ok;
    }

    bool apply_incremental(const L2Update& update, bool validate_sequence = true) {
        if (validate_sequence && last_sequence_ != 0) {
            if (update.final_sequence <= last_sequence_) {
                ++invalid_updates_;
                return false;
            }
            if (update.first_sequence > last_sequence_ + 1 && update.previous_final_sequence != last_sequence_) {
                ++invalid_updates_;
                return false;
            }
        }

        for (std::size_t i = 0; i < update.bid_count; ++i) {
            upsert_level(bids_, update.bids[i]);
        }
        for (std::size_t i = 0; i < update.ask_count; ++i) {
            upsert_level(asks_, update.asks[i]);
        }

        last_sequence_ = update.final_sequence ? update.final_sequence : last_sequence_ + 1;
        ++updates_;

        if (is_crossed()) {
            ++invalid_updates_;
            return false;
        }
        return true;
    }

    BookSnapshot snapshot(std::size_t depth_levels = 10) const {
        BookSnapshot s;
        s.best_bid = best_bid();
        s.best_ask = best_ask();
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
        s.crossed = is_crossed();
        s.valid = s.best_bid > 0.0 && s.best_ask > 0.0 && !s.crossed;
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

    static int64_t px(double price) noexcept {
        return static_cast<int64_t>(price * kScale + (price >= 0.0 ? 0.5 : -0.5));
    }

    static double unpx(int64_t price) noexcept {
        return static_cast<double>(price) / kScale;
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
        auto it = bid
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

    bool is_crossed() const {
        const double bid = best_bid();
        const double ask = best_ask();
        return bid > 0.0 && ask > 0.0 && bid >= ask;
    }

    Levels bids_;
    Levels asks_;
    uint64_t last_sequence_ = 0;
    uint64_t updates_ = 0;
    uint64_t invalid_updates_ = 0;
};

class L3OrderBook {
public:
    explicit L3OrderBook(std::size_t reserved_orders = 65536) {
        orders_.reserve(reserved_orders);
    }

    L3OrderBook(const L3OrderBook&) = delete;
    L3OrderBook& operator=(const L3OrderBook&) = delete;
    L3OrderBook(L3OrderBook&&) noexcept = default;
    L3OrderBook& operator=(L3OrderBook&&) noexcept = default;

    bool apply(const L3Update& update) {
        switch (update.action) {
            case L3Action::Insert: return insert(update);
            case L3Action::Modify: return modify(update);
            case L3Action::Cancel: return cancel(update.order_id);
            case L3Action::Trade: return execute(update.order_id, update.quantity, update.exchange_sequence);
        }
        return false;
    }

    bool insert(const L3Update& update) {
        if (update.order_id == 0 || update.price <= 0.0 || update.quantity <= 0.0) return false;
        L3Order order;
        order.order_id = update.order_id;
        order.price = update.price;
        order.quantity = update.quantity;
        order.timestamp_ns = update.timestamp_ns;
        order.side = update.side;
        order.exchange_sequence = update.exchange_sequence;
        order.queue_position = next_queue_position(update.side, update.price);
        orders_[order.order_id] = order;
        ++updates_;
        return true;
    }

    bool modify(const L3Update& update) {
        auto it = orders_.find(update.order_id);
        if (it == orders_.end()) return insert(update);
        if (update.quantity <= 0.0) return cancel(update.order_id);
        L3Order& order = it->second;
        const bool price_or_side_changed = order.price != update.price || order.side != update.side;
        order.price = update.price;
        order.quantity = update.quantity;
        order.timestamp_ns = update.timestamp_ns;
        order.side = update.side;
        order.exchange_sequence = update.exchange_sequence;
        if (price_or_side_changed) order.queue_position = next_queue_position(update.side, update.price);
        ++updates_;
        return true;
    }

    bool cancel(uint64_t order_id) {
        const auto erased = orders_.erase(order_id);
        updates_ += erased ? 1 : 0;
        return erased != 0;
    }

    bool execute(uint64_t order_id, double executed_quantity, uint64_t sequence) {
        auto it = orders_.find(order_id);
        if (it == orders_.end() || executed_quantity <= 0.0) return false;
        if (executed_quantity >= it->second.quantity) {
            orders_.erase(it);
        } else {
            it->second.quantity -= executed_quantity;
            it->second.exchange_sequence = sequence;
        }
        ++updates_;
        return true;
    }

    BookSnapshot aggregate(std::size_t depth_levels = 10) const {
        L2OrderBook tmp(std::max<std::size_t>(orders_.size(), 16));
        L2Update snapshot;
        for (const auto& kv : orders_) {
            const L3Order& o = kv.second;
            PriceLevelUpdate plu{o.price, o.quantity};
            if (o.side == BookSide::Bid) {
                append_level(snapshot.bids, snapshot.bid_count, plu);
            } else {
                append_level(snapshot.asks, snapshot.ask_count, plu);
            }
            if (snapshot.bid_count == L2Update::kMaxLevelsPerMessage || snapshot.ask_count == L2Update::kMaxLevelsPerMessage) {
                tmp.apply_incremental(snapshot, false);
                snapshot = L2Update{};
            }
        }
        tmp.apply_incremental(snapshot, false);
        return tmp.snapshot(depth_levels);
    }

    const L3Order* find(uint64_t order_id) const {
        auto it = orders_.find(order_id);
        return it == orders_.end() ? nullptr : &it->second;
    }

    std::size_t order_count() const noexcept { return orders_.size(); }
    uint64_t updates() const noexcept { return updates_; }

private:
    static void append_level(std::array<PriceLevelUpdate, L2Update::kMaxLevelsPerMessage>& levels,
                             std::size_t& count,
                             const PriceLevelUpdate& value) {
        for (std::size_t i = 0; i < count; ++i) {
            if (levels[i].price == value.price) {
                levels[i].quantity += value.quantity;
                return;
            }
        }
        if (count < levels.size()) levels[count++] = value;
    }

    uint32_t next_queue_position(BookSide side, double price) const {
        uint32_t pos = 0;
        for (const auto& kv : orders_) {
            const L3Order& o = kv.second;
            if (o.side == side && o.price == price) ++pos;
        }
        return pos;
    }

    std::unordered_map<uint64_t, L3Order> orders_;
    uint64_t updates_ = 0;
};

// Backward-compatible name retained for older live engine experiments.
class FastOrderBook {
public:
    inline void match(const TradePacket& trade) {
        last_price_ = trade.price;
        total_volume_ += trade.volume;
        ++total_trades_;
    }
    inline double last_price() const { return last_price_; }
    inline uint64_t total_volume() const { return static_cast<uint64_t>(total_volume_); }
    inline uint64_t total_trades() const { return total_trades_; }
    inline uint64_t updates() const { return total_trades_; }
private:
    double last_price_ = 0.0;
    double total_volume_ = 0.0;
    uint64_t total_trades_ = 0;
};

} // namespace quantos::market_data

using FastOrderBook = quantos::market_data::FastOrderBook;
using L2OrderBook = quantos::market_data::L2OrderBook;
using L3OrderBook = quantos::market_data::L3OrderBook;
using L2Update = quantos::market_data::L2Update;
using L3Update = quantos::market_data::L3Update;
using BookSnapshot = quantos::market_data::BookSnapshot;
using BookSide = quantos::market_data::BookSide;
using L3Action = quantos::market_data::L3Action;
