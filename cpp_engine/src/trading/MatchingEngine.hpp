#pragma once

#include "OrderTypes.hpp"

#include <algorithm>
#include <cstdint>
#include <deque>
#include <functional>
#include <map>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

class MatchingEngine {
public:
    struct RestingOrder {
        OrderRequest request;
        double remaining_quantity = 0.0;
        uint64_t sequence = 0;
    };

    struct Fill {
        uint64_t incoming_client_order_id = 0;
        uint64_t resting_client_order_id = 0;
        std::string symbol;
        Side incoming_side = Side::BUY;
        double quantity = 0.0;
        double price = 0.0;
        uint64_t sequence = 0;
    };

    struct MatchResult {
        OrderExecution execution;
        std::vector<Fill> fills;
        bool rested = false;
    };

    MatchResult submit_order(const OrderRequest& request, uint64_t ts_ns = 0) {
        MatchResult result;
        result.execution.client_order_id = request.client_order_id;
        result.execution.symbol = request.symbol;
        result.execution.side = request.side;
        result.execution.requested_quantity = request.quantity;
        result.execution.remaining_quantity = request.quantity;
        result.execution.exchange_ts_ns = ts_ns;
        result.execution.ack_ts_ns = ts_ns;

        if (!is_valid(request)) {
            result.execution.status = OrderStatus::REJECTED;
            result.execution.message = "invalid matching-engine order";
            return result;
        }

        double remaining = request.quantity;
        if (request.side == Side::BUY) {
            match_buy(request, remaining, result);
        } else {
            match_sell(request, remaining, result);
        }

        result.execution.filled_quantity = request.quantity - remaining;
        result.execution.remaining_quantity = remaining;
        result.execution.fill_ratio = request.quantity > 0.0 ? result.execution.filled_quantity / request.quantity : 0.0;
        result.execution.avg_fill_price = average_fill_price(result.fills);
        result.execution.fill_price = result.fills.empty() ? 0.0 : result.fills.back().price;

        if (remaining <= kEpsilon) {
            result.execution.status = OrderStatus::FILLED;
            result.execution.remaining_quantity = 0.0;
            result.execution.message = "fully matched";
            return result;
        }

        if (request.type == OrderType::MARKET || request.time_in_force == TimeInForce::IOC) {
            result.execution.status = result.execution.filled_quantity > 0.0 ? OrderStatus::PARTIALLY_FILLED : OrderStatus::REJECTED;
            result.execution.message = result.execution.filled_quantity > 0.0 ? "partially matched; remainder not rested" : "no liquidity available";
            return result;
        }

        if (request.type == OrderType::LIMIT) {
            rest_remainder(request, remaining);
            result.rested = true;
            result.execution.status = result.execution.filled_quantity > 0.0 ? OrderStatus::PARTIALLY_FILLED : OrderStatus::ACCEPTED;
            result.execution.message = result.execution.filled_quantity > 0.0 ? "partially matched; remainder rested" : "rested on book";
            return result;
        }

        result.execution.status = OrderStatus::REJECTED;
        result.execution.message = "unsupported order type";
        return result;
    }

    bool cancel_order(uint64_t client_order_id) {
        auto loc_it = locations_.find(client_order_id);
        if (loc_it == locations_.end()) return false;
        const auto location = loc_it->second;
        bool removed = false;
        if (location.side == Side::BUY) {
            removed = erase_from_book(bids_, client_order_id, location.price);
        } else {
            removed = erase_from_book(asks_, client_order_id, location.price);
        }
        locations_.erase(loc_it);
        return removed;
    }

    std::optional<RestingOrder> get_order(uint64_t client_order_id) const {
        auto loc_it = locations_.find(client_order_id);
        if (loc_it == locations_.end()) return std::nullopt;
        if (loc_it->second.side == Side::BUY) {
            return find_resting_order(bids_, client_order_id, loc_it->second.price);
        }
        return find_resting_order(asks_, client_order_id, loc_it->second.price);
    }

    std::vector<uint64_t> bid_order_ids(double price) const { return order_ids_at(bids_, price); }
    std::vector<uint64_t> ask_order_ids(double price) const { return order_ids_at(asks_, price); }

    double bid_quantity(double price) const { return quantity_at(bids_, price); }
    double ask_quantity(double price) const { return quantity_at(asks_, price); }

    std::optional<double> best_bid() const {
        if (bids_.empty()) return std::nullopt;
        return bids_.begin()->first;
    }

    std::optional<double> best_ask() const {
        if (asks_.empty()) return std::nullopt;
        return asks_.begin()->first;
    }

    std::size_t resting_order_count() const { return locations_.size(); }

private:
    static constexpr double kEpsilon = 1e-12;
    using BidBook = std::map<double, std::deque<RestingOrder>, std::greater<double>>;
    using AskBook = std::map<double, std::deque<RestingOrder>, std::less<double>>;

    struct Location {
        Side side = Side::BUY;
        double price = 0.0;
    };

    bool is_valid(const OrderRequest& request) const {
        if (request.client_order_id == 0 || request.symbol.empty() || request.quantity <= 0.0) return false;
        if (locations_.count(request.client_order_id) != 0) return false;
        if (request.type == OrderType::LIMIT && request.limit_price <= 0.0) return false;
        return request.type == OrderType::MARKET || request.type == OrderType::LIMIT;
    }

    bool crosses_buy(const OrderRequest& request, double ask_price) const {
        return request.type == OrderType::MARKET || request.limit_price + kEpsilon >= ask_price;
    }

    bool crosses_sell(const OrderRequest& request, double bid_price) const {
        return request.type == OrderType::MARKET || request.limit_price <= bid_price + kEpsilon;
    }

    void match_buy(const OrderRequest& request, double& remaining, MatchResult& result) {
        while (remaining > kEpsilon && !asks_.empty()) {
            auto level_it = asks_.begin();
            const double price = level_it->first;
            if (!crosses_buy(request, price)) break;
            consume_level(request, remaining, price, level_it->second, result);
            if (level_it->second.empty()) asks_.erase(level_it);
        }
    }

    void match_sell(const OrderRequest& request, double& remaining, MatchResult& result) {
        while (remaining > kEpsilon && !bids_.empty()) {
            auto level_it = bids_.begin();
            const double price = level_it->first;
            if (!crosses_sell(request, price)) break;
            consume_level(request, remaining, price, level_it->second, result);
            if (level_it->second.empty()) bids_.erase(level_it);
        }
    }

    void consume_level(const OrderRequest& incoming, double& remaining, double price, std::deque<RestingOrder>& queue, MatchResult& result) {
        while (remaining > kEpsilon && !queue.empty()) {
            auto& resting = queue.front();
            const double fill_qty = std::min(remaining, resting.remaining_quantity);
            remaining -= fill_qty;
            resting.remaining_quantity -= fill_qty;

            result.fills.push_back(Fill{
                incoming.client_order_id,
                resting.request.client_order_id,
                incoming.symbol,
                incoming.side,
                fill_qty,
                price,
                next_sequence_++
            });

            if (resting.remaining_quantity <= kEpsilon) {
                locations_.erase(resting.request.client_order_id);
                queue.pop_front();
            }
        }
    }

    void rest_remainder(const OrderRequest& request, double remaining) {
        RestingOrder resting{request, remaining, next_sequence_++};
        if (request.side == Side::BUY) {
            bids_[request.limit_price].push_back(resting);
        } else {
            asks_[request.limit_price].push_back(resting);
        }
        locations_[request.client_order_id] = Location{request.side, request.limit_price};
    }

    static double average_fill_price(const std::vector<Fill>& fills) {
        double notional = 0.0;
        double quantity = 0.0;
        for (const auto& fill : fills) {
            notional += fill.quantity * fill.price;
            quantity += fill.quantity;
        }
        return quantity > kEpsilon ? notional / quantity : 0.0;
    }

    template <typename BookT>
    static bool erase_from_book(BookT& book, uint64_t client_order_id, double price) {
        auto level_it = book.find(price);
        if (level_it == book.end()) return false;
        auto& queue = level_it->second;
        for (auto it = queue.begin(); it != queue.end(); ++it) {
            if (it->request.client_order_id == client_order_id) {
                queue.erase(it);
                if (queue.empty()) book.erase(level_it);
                return true;
            }
        }
        return false;
    }

    template <typename BookT>
    static std::optional<RestingOrder> find_resting_order(const BookT& book, uint64_t client_order_id, double price) {
        auto level_it = book.find(price);
        if (level_it == book.end()) return std::nullopt;
        for (const auto& order : level_it->second) {
            if (order.request.client_order_id == client_order_id) return order;
        }
        return std::nullopt;
    }

    template <typename BookT>
    static std::vector<uint64_t> order_ids_at(const BookT& book, double price) {
        auto it = book.find(price);
        if (it == book.end()) return {};
        std::vector<uint64_t> ids;
        ids.reserve(it->second.size());
        for (const auto& order : it->second) ids.push_back(order.request.client_order_id);
        return ids;
    }

    template <typename BookT>
    static double quantity_at(const BookT& book, double price) {
        auto it = book.find(price);
        if (it == book.end()) return 0.0;
        double total = 0.0;
        for (const auto& order : it->second) total += order.remaining_quantity;
        return total;
    }

    BidBook bids_;
    AskBook asks_;
    std::unordered_map<uint64_t, Location> locations_;
    uint64_t next_sequence_ = 1;
};
