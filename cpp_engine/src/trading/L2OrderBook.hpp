#pragma once

#include <cstddef>
#include <functional>
#include <map>
#include <optional>
#include <vector>

class L2OrderBook {
public:
    struct Level {
        double price = 0.0;
        double quantity = 0.0;
    };

    bool reconstruct_snapshot(uint64_t sequence,
                              const std::vector<Level>& bids,
                              const std::vector<Level>& asks) {
        clear();
        for (const auto& level : bids) {
            if (!set_bid(level.price, level.quantity)) return false;
        }
        for (const auto& level : asks) {
            if (!set_ask(level.price, level.quantity)) return false;
        }
        last_sequence_ = sequence;
        initialized_ = true;
        return true;
    }

    bool apply_incremental_update(uint64_t sequence,
                                  const std::vector<Level>& bid_updates,
                                  const std::vector<Level>& ask_updates) {
        if (!initialized_) return false;
        if (sequence != last_sequence_ + 1) return false;
        for (const auto& level : bid_updates) {
            if (!set_bid(level.price, level.quantity)) return false;
        }
        for (const auto& level : ask_updates) {
            if (!set_ask(level.price, level.quantity)) return false;
        }
        last_sequence_ = sequence;
        return true;
    }

    bool set_bid(double price, double quantity) { return set_level(bids_, price, quantity); }
    bool set_ask(double price, double quantity) { return set_level(asks_, price, quantity); }

    bool remove_bid(double price) { return bids_.erase(price) > 0; }
    bool remove_ask(double price) { return asks_.erase(price) > 0; }

    std::optional<Level> best_bid() const {
        if (bids_.empty()) return std::nullopt;
        return Level{bids_.begin()->first, bids_.begin()->second};
    }

    std::optional<Level> best_ask() const {
        if (asks_.empty()) return std::nullopt;
        return Level{asks_.begin()->first, asks_.begin()->second};
    }

    double bid_quantity(double price) const { return quantity_at(bids_, price); }
    double ask_quantity(double price) const { return quantity_at(asks_, price); }

    std::vector<Level> bid_levels(std::size_t depth = 0) const { return levels_from(bids_, depth); }
    std::vector<Level> ask_levels(std::size_t depth = 0) const { return levels_from(asks_, depth); }

    std::size_t bid_depth() const { return bids_.size(); }
    std::size_t ask_depth() const { return asks_.size(); }

    double bid_depth_quantity(std::size_t depth = 0) const { return depth_quantity(bids_, depth); }
    double ask_depth_quantity(std::size_t depth = 0) const { return depth_quantity(asks_, depth); }

    bool is_crossed() const {
        auto bid = best_bid();
        auto ask = best_ask();
        return bid.has_value() && ask.has_value() && bid->price >= ask->price;
    }

    std::optional<double> spread() const {
        auto bid = best_bid();
        auto ask = best_ask();
        if (!bid || !ask) return std::nullopt;
        return ask->price - bid->price;
    }

    std::optional<double> mid_price() const {
        auto bid = best_bid();
        auto ask = best_ask();
        if (!bid || !ask) return std::nullopt;
        return (bid->price + ask->price) / 2.0;
    }

    double imbalance(std::size_t depth = 0) const {
        const double bq = bid_depth_quantity(depth);
        const double aq = ask_depth_quantity(depth);
        const double total = bq + aq;
        return total <= 0.0 ? 0.0 : (bq - aq) / total;
    }

    std::optional<double> bid_vwap(std::size_t depth = 0) const { return vwap(bids_, depth); }
    std::optional<double> ask_vwap(std::size_t depth = 0) const { return vwap(asks_, depth); }

    uint64_t last_sequence() const { return last_sequence_; }
    bool initialized() const { return initialized_; }
    bool empty() const { return bids_.empty() && asks_.empty(); }

    void clear() {
        bids_.clear();
        asks_.clear();
        last_sequence_ = 0;
        initialized_ = false;
    }

private:
    using BidMap = std::map<double, double, std::greater<double>>;
    using AskMap = std::map<double, double, std::less<double>>;

    template <typename BookT>
    static bool set_level(BookT& book, double price, double quantity) {
        if (price <= 0.0) return false;
        if (quantity <= 0.0) {
            book.erase(price);
            return true;
        }
        book[price] = quantity;
        return true;
    }

    template <typename BookT>
    static double quantity_at(const BookT& book, double price) {
        auto it = book.find(price);
        return it == book.end() ? 0.0 : it->second;
    }

    template <typename BookT>
    static std::vector<Level> levels_from(const BookT& book, std::size_t depth) {
        std::vector<Level> levels;
        const std::size_t limit = depth == 0 ? book.size() : depth;
        levels.reserve(limit < book.size() ? limit : book.size());
        for (const auto& kv : book) {
            if (depth != 0 && levels.size() >= depth) break;
            levels.push_back(Level{kv.first, kv.second});
        }
        return levels;
    }

    template <typename BookT>
    static double depth_quantity(const BookT& book, std::size_t depth) {
        double total = 0.0;
        std::size_t seen = 0;
        for (const auto& kv : book) {
            if (depth != 0 && seen >= depth) break;
            total += kv.second;
            ++seen;
        }
        return total;
    }

    template <typename BookT>
    static std::optional<double> vwap(const BookT& book, std::size_t depth) {
        double notional = 0.0;
        double quantity = 0.0;
        std::size_t seen = 0;
        for (const auto& kv : book) {
            if (depth != 0 && seen >= depth) break;
            notional += kv.first * kv.second;
            quantity += kv.second;
            ++seen;
        }
        if (quantity <= 0.0) return std::nullopt;
        return notional / quantity;
    }

    BidMap bids_;
    AskMap asks_;
    uint64_t last_sequence_ = 0;
    bool initialized_ = false;
};
