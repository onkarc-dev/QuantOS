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
#include <utility>
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

    struct ExecutionReport {
        OrderExecution execution;
        uint64_t sequence = 0;
        uint64_t replaced_client_order_id = 0;
    };

    struct MatchResult {
        OrderExecution execution;
        std::vector<Fill> fills;
        std::vector<ExecutionReport> execution_reports;
        bool rested = false;
        bool triggered = false;
    };

    using ReduceOnlyHook = std::function<bool(const OrderRequest&, double)>;

    void set_reduce_only_hook(ReduceOnlyHook hook) { reduce_only_hook_ = std::move(hook); }

    MatchResult submit_order(const OrderRequest& request, uint64_t ts_ns = 0) {
        MatchResult result;
        initialise_execution(result.execution, request, ts_ns);
        emit(result, result.execution, "new order received");

        if (!is_valid(request)) {
            result.execution.status = OrderStatus::REJECTED;
            result.execution.message = "invalid matching-engine order";
            emit(result, result.execution, result.execution.message);
            return result;
        }

        if (request.reduce_only && reduce_only_hook_ && !reduce_only_hook_(request, request.quantity)) {
            result.execution.status = OrderStatus::REJECTED;
            result.execution.message = "reduce-only check rejected order";
            emit(result, result.execution, result.execution.message);
            return result;
        }

        if (is_stop_order(request)) {
            stop_orders_.push_back(RestingOrder{request, request.quantity, next_sequence_++});
            result.execution.status = OrderStatus::ACCEPTED;
            result.execution.message = "stop order accepted pending trigger";
            emit(result, result.execution, result.execution.message);
            return result;
        }

        return submit_active_order(request, ts_ns, result);
    }

    MatchResult cancel_order_report(uint64_t client_order_id, uint64_t ts_ns = 0) {
        MatchResult result;
        auto active = get_order(client_order_id);
        if (active) initialise_execution(result.execution, active->request, ts_ns);
        else result.execution.client_order_id = client_order_id;
        emit(result, result.execution, "cancel requested");

        if (active && erase_active(client_order_id)) {
            result.execution.status = OrderStatus::CANCELLED;
            result.execution.symbol = active->request.symbol;
            result.execution.side = active->request.side;
            result.execution.requested_quantity = active->request.quantity;
            result.execution.remaining_quantity = active->remaining_quantity;
            result.execution.message = "order cancelled";
            emit(result, result.execution, result.execution.message);
            return result;
        }

        auto stop_it = find_stop(client_order_id);
        if (stop_it != stop_orders_.end()) {
            auto stopped = *stop_it;
            stop_orders_.erase(stop_it);
            initialise_execution(result.execution, stopped.request, ts_ns);
            result.execution.status = OrderStatus::CANCELLED;
            result.execution.remaining_quantity = stopped.remaining_quantity;
            result.execution.message = "stop order cancelled";
            emit(result, result.execution, result.execution.message);
            return result;
        }

        result.execution.status = OrderStatus::REJECTED;
        result.execution.message = "order not found";
        emit(result, result.execution, result.execution.message);
        return result;
    }

    bool cancel_order(uint64_t client_order_id) { return cancel_order_report(client_order_id).execution.status == OrderStatus::CANCELLED; }

    MatchResult modify_order(uint64_t client_order_id, double new_quantity, double new_price, uint64_t ts_ns = 0) {
        MatchResult result;
        auto active = get_order(client_order_id);
        if (!active) {
            result.execution.client_order_id = client_order_id;
            result.execution.status = OrderStatus::REJECTED;
            result.execution.message = "order not found";
            emit(result, result.execution, result.execution.message);
            return result;
        }
        initialise_execution(result.execution, active->request, ts_ns);
        emit(result, result.execution, "modify requested");

        if (new_quantity <= 0.0 || new_price <= 0.0) {
            result.execution.status = OrderStatus::REJECTED;
            result.execution.message = "invalid modify request";
            emit(result, result.execution, result.execution.message);
            return result;
        }

        auto loc = locations_.at(client_order_id);
        auto* queue = find_queue(loc.side, loc.price);
        if (!queue) {
            result.execution.status = OrderStatus::REJECTED;
            result.execution.message = "order location missing";
            emit(result, result.execution, result.execution.message);
            return result;
        }
        for (auto it = queue->begin(); it != queue->end(); ++it) {
            if (it->request.client_order_id != client_order_id) continue;
            const bool price_changed = (new_price > loc.price ? new_price - loc.price : loc.price - new_price) > kEpsilon;
            it->request.quantity = new_quantity;
            it->request.limit_price = new_price;
            it->remaining_quantity = new_quantity;
            if (price_changed) {
                RestingOrder moved = *it;
                queue->erase(it);
                if (queue->empty()) erase_empty_level(loc.side, loc.price);
                locations_.erase(client_order_id);
                rest_remainder(moved.request, moved.remaining_quantity);
            }
            result.rested = true;
            result.execution.status = OrderStatus::ACCEPTED;
            result.execution.requested_quantity = new_quantity;
            result.execution.remaining_quantity = new_quantity;
            result.execution.message = price_changed ? "order modified; price changed so priority reset" : "order modified; priority preserved";
            emit(result, result.execution, result.execution.message);
            return result;
        }
        result.execution.status = OrderStatus::REJECTED;
        result.execution.message = "order not found at price level";
        emit(result, result.execution, result.execution.message);
        return result;
    }

    MatchResult replace_order(uint64_t old_client_order_id, const OrderRequest& replacement, uint64_t ts_ns = 0) {
        MatchResult result = cancel_order_report(old_client_order_id, ts_ns);
        if (result.execution.status != OrderStatus::CANCELLED) return result;
        MatchResult created = submit_order(replacement, ts_ns);
        result.fills.insert(result.fills.end(), created.fills.begin(), created.fills.end());
        result.execution_reports.insert(result.execution_reports.end(), created.execution_reports.begin(), created.execution_reports.end());
        result.execution = created.execution;
        if (!result.execution_reports.empty()) result.execution_reports.back().replaced_client_order_id = old_client_order_id;
        result.rested = created.rested;
        return result;
    }

    std::vector<MatchResult> on_market_price(const std::string& symbol, double last_price, uint64_t ts_ns = 0) {
        std::vector<MatchResult> triggered;
        for (auto it = stop_orders_.begin(); it != stop_orders_.end();) {
            if (it->request.symbol == symbol && stop_triggered(it->request, last_price)) {
                OrderRequest active = it->request;
                active.type = active.type == OrderType::STOP_LIMIT ? OrderType::LIMIT : OrderType::MARKET;
                it = stop_orders_.erase(it);
                MatchResult result = submit_order(active, ts_ns);
                result.triggered = true;
                if (!result.execution_reports.empty()) result.execution_reports.front().execution.message = "stop triggered";
                triggered.push_back(result);
            } else {
                ++it;
            }
        }
        return triggered;
    }

    std::optional<RestingOrder> get_order(uint64_t client_order_id) const {
        auto loc_it = locations_.find(client_order_id);
        if (loc_it == locations_.end()) return std::nullopt;
        if (loc_it->second.side == Side::BUY) return find_resting_order(bids_, client_order_id, loc_it->second.price);
        return find_resting_order(asks_, client_order_id, loc_it->second.price);
    }

    std::vector<uint64_t> bid_order_ids(double price) const { return order_ids_at(bids_, price); }
    std::vector<uint64_t> ask_order_ids(double price) const { return order_ids_at(asks_, price); }
    double bid_quantity(double price) const { return quantity_at(bids_, price); }
    double ask_quantity(double price) const { return quantity_at(asks_, price); }
    std::optional<double> best_bid() const { if (bids_.empty()) return std::nullopt; return bids_.begin()->first; }
    std::optional<double> best_ask() const { if (asks_.empty()) return std::nullopt; return asks_.begin()->first; }
    std::size_t resting_order_count() const { return locations_.size(); }
    std::size_t pending_stop_count() const { return stop_orders_.size(); }

private:
    static constexpr double kEpsilon = 1e-12;
    using BidBook = std::map<double, std::deque<RestingOrder>, std::greater<double>>;
    using AskBook = std::map<double, std::deque<RestingOrder>, std::less<double>>;
    struct Location { Side side = Side::BUY; double price = 0.0; };

    MatchResult submit_active_order(const OrderRequest& request, uint64_t ts_ns, MatchResult result) {
        if (request.time_in_force == TimeInForce::FOK && available_quantity(request) + kEpsilon < request.quantity) {
            result.execution.status = OrderStatus::REJECTED;
            result.execution.message = "FOK full fill unavailable";
            emit(result, result.execution, result.execution.message);
            return result;
        }
        if ((request.post_only || request.time_in_force == TimeInForce::POST_ONLY) && would_cross(request)) {
            result.execution.status = OrderStatus::REJECTED;
            result.execution.message = "post-only order would cross";
            emit(result, result.execution, result.execution.message);
            return result;
        }

        double remaining = request.quantity;
        if (request.side == Side::BUY) match_buy(request, remaining, result);
        else match_sell(request, remaining, result);
        update_execution_from_fills(result.execution, request, remaining, result.fills);

        if (remaining <= kEpsilon) {
            result.execution.status = OrderStatus::FILLED;
            result.execution.remaining_quantity = 0.0;
            result.execution.message = "fully matched";
            emit(result, result.execution, result.execution.message);
            return result;
        }
        if (request.type == OrderType::MARKET || request.time_in_force == TimeInForce::IOC) {
            result.execution.status = result.execution.filled_quantity > 0.0 ? OrderStatus::EXPIRED : OrderStatus::REJECTED;
            result.execution.message = result.execution.filled_quantity > 0.0 ? "IOC partially filled; remainder expired" : "no liquidity available";
            emit(result, result.execution, result.execution.message);
            return result;
        }
        if (request.type == OrderType::LIMIT) {
            rest_remainder(request, remaining);
            result.rested = true;
            result.execution.status = result.execution.filled_quantity > 0.0 ? OrderStatus::PARTIALLY_FILLED : OrderStatus::ACCEPTED;
            result.execution.message = result.execution.filled_quantity > 0.0 ? "partially matched; remainder rested" : "rested on book";
            emit(result, result.execution, result.execution.message);
            return result;
        }
        result.execution.status = OrderStatus::REJECTED;
        result.execution.message = "unsupported order type";
        emit(result, result.execution, result.execution.message);
        return result;
    }

    static void initialise_execution(OrderExecution& e, const OrderRequest& r, uint64_t ts_ns) {
        e = OrderExecution{}; e.client_order_id = r.client_order_id; e.symbol = r.symbol; e.side = r.side; e.status = OrderStatus::NEW; e.requested_quantity = r.quantity; e.remaining_quantity = r.quantity; e.exchange_ts_ns = ts_ns; e.ack_ts_ns = ts_ns;
    }
    void emit(MatchResult& result, OrderExecution execution, const std::string& message) { execution.message = message; result.execution_reports.push_back(ExecutionReport{execution, next_sequence_++, 0}); }
    bool is_stop_order(const OrderRequest& r) const { return r.type == OrderType::STOP || r.type == OrderType::STOP_LIMIT; }
    bool is_valid(const OrderRequest& r) const {
        if (r.client_order_id == 0 || r.symbol.empty() || r.quantity <= 0.0) return false;
        if (locations_.count(r.client_order_id) != 0 || stop_id_exists(r.client_order_id)) return false;
        if ((r.type == OrderType::LIMIT || r.type == OrderType::STOP_LIMIT) && r.limit_price <= 0.0) return false;
        if (is_stop_order(r) && r.stop_price <= 0.0) return false;
        return r.type == OrderType::MARKET || r.type == OrderType::LIMIT || r.type == OrderType::STOP || r.type == OrderType::STOP_LIMIT;
    }
    bool stop_id_exists(uint64_t id) const { return std::any_of(stop_orders_.begin(), stop_orders_.end(), [id](const RestingOrder& o){ return o.request.client_order_id == id; }); }
    bool stop_triggered(const OrderRequest& r, double last) const { return r.side == Side::BUY ? last + kEpsilon >= r.stop_price : last <= r.stop_price + kEpsilon; }
    bool crosses_buy(const OrderRequest& r, double ask) const { return r.type == OrderType::MARKET || r.limit_price + kEpsilon >= ask; }
    bool crosses_sell(const OrderRequest& r, double bid) const { return r.type == OrderType::MARKET || r.limit_price <= bid + kEpsilon; }
    bool would_cross(const OrderRequest& r) const { if (r.side == Side::BUY) return best_ask() && crosses_buy(r, *best_ask()); return best_bid() && crosses_sell(r, *best_bid()); }
    double available_quantity(const OrderRequest& r) const {
        double total = 0.0;
        if (r.side == Side::BUY) { for (const auto& [p,q] : asks_) { if (!crosses_buy(r,p)) break; for (const auto& o:q) total += o.remaining_quantity; if (total + kEpsilon >= r.quantity) break; } }
        else { for (const auto& [p,q] : bids_) { if (!crosses_sell(r,p)) break; for (const auto& o:q) total += o.remaining_quantity; if (total + kEpsilon >= r.quantity) break; } }
        return total;
    }
    void match_buy(const OrderRequest& r, double& rem, MatchResult& res) { while (rem > kEpsilon && !asks_.empty()) { auto it = asks_.begin(); if (!crosses_buy(r,it->first)) break; consume_level(r, rem, it->first, it->second, res); if (it->second.empty()) asks_.erase(it); } }
    void match_sell(const OrderRequest& r, double& rem, MatchResult& res) { while (rem > kEpsilon && !bids_.empty()) { auto it = bids_.begin(); if (!crosses_sell(r,it->first)) break; consume_level(r, rem, it->first, it->second, res); if (it->second.empty()) bids_.erase(it); } }
    void consume_level(const OrderRequest& incoming, double& remaining, double price, std::deque<RestingOrder>& queue, MatchResult& result) {
        while (remaining > kEpsilon && !queue.empty()) {
            auto& resting = queue.front(); double fill_qty = std::min(remaining, resting.remaining_quantity); remaining -= fill_qty; resting.remaining_quantity -= fill_qty;
            result.fills.push_back(Fill{incoming.client_order_id, resting.request.client_order_id, incoming.symbol, incoming.side, fill_qty, price, next_sequence_++});
            if (resting.remaining_quantity <= kEpsilon) { locations_.erase(resting.request.client_order_id); queue.pop_front(); }
        }
    }
    void update_execution_from_fills(OrderExecution& e, const OrderRequest& r, double remaining, const std::vector<Fill>& fills) const { e.filled_quantity = r.quantity - remaining; e.remaining_quantity = remaining; e.fill_ratio = r.quantity > 0.0 ? e.filled_quantity / r.quantity : 0.0; e.avg_fill_price = average_fill_price(fills); e.fill_price = fills.empty() ? 0.0 : fills.back().price; }
    void rest_remainder(const OrderRequest& r, double rem) { RestingOrder resting{r, rem, next_sequence_++}; if (r.side == Side::BUY) bids_[r.limit_price].push_back(resting); else asks_[r.limit_price].push_back(resting); locations_[r.client_order_id] = Location{r.side, r.limit_price}; }
    bool erase_active(uint64_t id) { auto loc_it = locations_.find(id); if (loc_it == locations_.end()) return false; auto loc = loc_it->second; bool removed = loc.side == Side::BUY ? erase_from_book(bids_, id, loc.price) : erase_from_book(asks_, id, loc.price); locations_.erase(loc_it); return removed; }
    std::deque<RestingOrder>::iterator find_stop(uint64_t id) { return std::find_if(stop_orders_.begin(), stop_orders_.end(), [id](const RestingOrder& o){ return o.request.client_order_id == id; }); }
    std::deque<RestingOrder>* find_queue(Side s, double p) { if (s == Side::BUY) { auto it=bids_.find(p); return it==bids_.end()?nullptr:&it->second; } auto it=asks_.find(p); return it==asks_.end()?nullptr:&it->second; }
    void erase_empty_level(Side s, double p) { if (s == Side::BUY) { auto it=bids_.find(p); if (it!=bids_.end() && it->second.empty()) bids_.erase(it); } else { auto it=asks_.find(p); if (it!=asks_.end() && it->second.empty()) asks_.erase(it); } }
    static double average_fill_price(const std::vector<Fill>& fills) { double n=0.0,q=0.0; for (auto& f:fills){ n += f.quantity*f.price; q += f.quantity; } return q > kEpsilon ? n/q : 0.0; }
    template <typename BookT> static bool erase_from_book(BookT& book, uint64_t id, double price) { auto lit=book.find(price); if(lit==book.end()) return false; auto& q=lit->second; for(auto it=q.begin(); it!=q.end(); ++it) if(it->request.client_order_id==id){ q.erase(it); if(q.empty()) book.erase(lit); return true; } return false; }
    template <typename BookT> static std::optional<RestingOrder> find_resting_order(const BookT& book, uint64_t id, double price) { auto lit=book.find(price); if(lit==book.end()) return std::nullopt; for(const auto& o:lit->second) if(o.request.client_order_id==id) return o; return std::nullopt; }
    template <typename BookT> static std::vector<uint64_t> order_ids_at(const BookT& book, double price) { auto it=book.find(price); if(it==book.end()) return {}; std::vector<uint64_t> ids; for(const auto& o:it->second) ids.push_back(o.request.client_order_id); return ids; }
    template <typename BookT> static double quantity_at(const BookT& book, double price) { auto it=book.find(price); if(it==book.end()) return 0.0; double total=0.0; for(const auto& o:it->second) total += o.remaining_quantity; return total; }

    BidBook bids_;
    AskBook asks_;
    std::deque<RestingOrder> stop_orders_;
    std::unordered_map<uint64_t, Location> locations_;
    ReduceOnlyHook reduce_only_hook_;
    uint64_t next_sequence_ = 1;
};
