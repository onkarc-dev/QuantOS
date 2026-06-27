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
    bool empty() const { return bids_.empty() && asks_.empty(); }
    void clear() { bids_.clear(); asks_.clear(); }

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

    BidMap bids_;
    AskMap asks_;
};
