#pragma once

#include <cstddef>
#include <cstdint>
#include <deque>
#include <map>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

class L3OrderBook {
public:
    enum class Side { Buy, Sell };

    struct Order {
        uint64_t order_id = 0;
        Side side = Side::Buy;
        double price = 0.0;
        double quantity = 0.0;
        std::size_t queue_position = 0; // 1-based within side+price FIFO level.
    };

    bool insert(uint64_t order_id, Side side, double price, double quantity) {
        if (order_id == 0 || price <= 0.0 || quantity <= 0.0 || orders_.count(order_id) != 0) {
            return false;
        }

        auto& queue = level(side, price);
        queue.push_back(order_id);
        orders_.emplace(order_id, Order{order_id, side, price, quantity, queue.size()});
        return true;
    }

    bool modify_quantity(uint64_t order_id, double new_quantity) {
        auto it = orders_.find(order_id);
        if (it == orders_.end()) return false;
        if (new_quantity <= 0.0) return cancel(order_id);

        it->second.quantity = new_quantity;
        // Quantity-only amend keeps existing FIFO priority.
        refresh_level(it->second.side, it->second.price);
        return true;
    }

    bool modify_price(uint64_t order_id, double new_price) {
        auto it = orders_.find(order_id);
        if (it == orders_.end() || new_price <= 0.0) return false;

        Order order = it->second;
        remove_from_level(order.side, order.price, order_id);
        refresh_level(order.side, order.price);

        order.price = new_price;
        auto& new_queue = level(order.side, new_price);
        new_queue.push_back(order_id);
        order.queue_position = new_queue.size();
        it->second = order;
        return true;
    }

    bool cancel(uint64_t order_id) {
        auto it = orders_.find(order_id);
        if (it == orders_.end()) return false;

        const Side side = it->second.side;
        const double price = it->second.price;
        remove_from_level(side, price, order_id);
        orders_.erase(it);
        refresh_level(side, price);
        return true;
    }

    bool execute_trade(uint64_t order_id, double executed_quantity) {
        auto it = orders_.find(order_id);
        if (it == orders_.end() || executed_quantity <= 0.0) return false;

        if (executed_quantity >= it->second.quantity) {
            return cancel(order_id);
        }

        it->second.quantity -= executed_quantity;
        // Partial fills do not change FIFO priority, but positions are refreshed
        // deterministically in case earlier orders were already removed.
        refresh_level(it->second.side, it->second.price);
        return true;
    }

    bool trade(uint64_t order_id, double executed_quantity) {
        return execute_trade(order_id, executed_quantity);
    }

    bool contains(uint64_t order_id) const {
        return orders_.count(order_id) != 0;
    }

    std::optional<Order> get_order(uint64_t order_id) const {
        auto it = orders_.find(order_id);
        if (it == orders_.end()) return std::nullopt;
        return it->second;
    }

    std::size_t queue_position(uint64_t order_id) const {
        auto it = orders_.find(order_id);
        return it == orders_.end() ? 0 : it->second.queue_position;
    }

    std::vector<uint64_t> level_order_ids(Side side, double price) const {
        const auto* levels = levels_for(side);
        auto it = levels->find(price);
        if (it == levels->end()) return {};
        return {it->second.begin(), it->second.end()};
    }

    double level_quantity(Side side, double price) const {
        double total = 0.0;
        for (uint64_t order_id : level_order_ids(side, price)) {
            auto it = orders_.find(order_id);
            if (it != orders_.end()) total += it->second.quantity;
        }
        return total;
    }

    std::size_t size() const { return orders_.size(); }
    bool empty() const { return orders_.empty(); }

private:
    using LevelMap = std::map<double, std::deque<uint64_t>>;

    LevelMap& levels_for(Side side) {
        return side == Side::Buy ? bids_ : asks_;
    }

    const LevelMap* levels_for(Side side) const {
        return side == Side::Buy ? &bids_ : &asks_;
    }

    std::deque<uint64_t>& level(Side side, double price) {
        return levels_for(side)[price];
    }

    void remove_from_level(Side side, double price, uint64_t order_id) {
        auto& levels = levels_for(side);
        auto it = levels.find(price);
        if (it == levels.end()) return;

        auto& queue = it->second;
        for (auto qit = queue.begin(); qit != queue.end(); ++qit) {
            if (*qit == order_id) {
                queue.erase(qit);
                break;
            }
        }
        if (queue.empty()) levels.erase(it);
    }

    void refresh_level(Side side, double price) {
        auto& levels = levels_for(side);
        auto it = levels.find(price);
        if (it == levels.end()) return;

        std::size_t position = 1;
        for (uint64_t order_id : it->second) {
            auto order_it = orders_.find(order_id);
            if (order_it != orders_.end()) {
                order_it->second.queue_position = position++;
            }
        }
    }

    std::unordered_map<uint64_t, Order> orders_;
    LevelMap bids_;
    LevelMap asks_;
};
