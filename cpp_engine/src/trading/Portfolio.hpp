#pragma once
#include "OrderTypes.hpp"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <string>
#include <unordered_map>

class Portfolio {
public:
    explicit Portfolio(const std::string& ledger_path = "") {
        if (!ledger_path.empty()) {
            ledger_.open(ledger_path, std::ios::out | std::ios::app);
            if (ledger_.tellp() == 0) ledger_ << "event_id,symbol,side,qty,fill_price,commission,position_qty,avg_price,realized_pnl\n";
        }
    }

    void apply_fill(const OrderExecution& e) {
        if (!is_fill_status(e.status) || e.filled_quantity <= 0.0) return;

        const double effective_price = e.avg_fill_price > 0.0 ? e.avg_fill_price : e.fill_price;
        if (effective_price <= 0.0) return;

        auto& p = positions_[e.symbol];
        p.symbol = e.symbol;

        const double signed_fill_qty = signed_quantity(e.side, e.filled_quantity);
        const double old_qty = p.quantity;
        const double new_qty = old_qty + signed_fill_qty;
        const double commission = std::max(0.0, e.commission);

        if (is_flat(old_qty) || same_direction(old_qty, signed_fill_qty)) {
            add_to_position(p, old_qty, signed_fill_qty, effective_price);
            p.realized_pnl -= commission;
        } else {
            close_or_flip_position(p, old_qty, signed_fill_qty, effective_price, commission);
        }

        if (is_flat(new_qty)) {
            p.quantity = 0.0;
            p.avg_price = 0.0;
            p.unrealized_pnl = 0.0;
        } else {
            p.quantity = new_qty;
            const auto it = last_price_.find(e.symbol);
            if (it != last_price_.end() && it->second > 0.0) {
                p.unrealized_pnl = p.quantity * (it->second - p.avg_price);
            }
        }

        write_ledger(e, effective_price, p);
    }

    void mark(const std::string& symbol, double price) {
        if (price <= 0.0) return;
        last_price_[symbol] = price;
        auto it = positions_.find(symbol);
        if (it == positions_.end()) return;
        auto& p = it->second;
        p.unrealized_pnl = is_flat(p.quantity) ? 0.0 : p.quantity * (price - p.avg_price);
    }

    const std::unordered_map<std::string, Position>& positions() const { return positions_; }
    double last_price(const std::string& symbol) const { auto it=last_price_.find(symbol); return it==last_price_.end()?0.0:it->second; }
    int open_position_count() const { int c=0; for (auto& kv:positions_) if (std::abs(kv.second.quantity)>1e-12) ++c; return c; }
    double total_realized_pnl() const { double s=0; for (auto& kv:positions_) s+=kv.second.realized_pnl; return s; }
    double total_unrealized_pnl() const { double s=0; for (auto& kv:positions_) s+=kv.second.unrealized_pnl; return s; }
    double gross_notional() const {
        double s=0;
        for (const auto& kv:positions_) {
            const auto lp = last_price(kv.first);
            s += std::abs(kv.second.quantity * (lp > 0 ? lp : kv.second.avg_price));
        }
        return s;
    }

private:
    static constexpr double kEps = 1e-12;

    static bool is_flat(double q) { return std::abs(q) < kEps; }

    static bool is_fill_status(OrderStatus status) {
        return status == OrderStatus::FILLED ||
               status == OrderStatus::PARTIALLY_FILLED ||
               status == OrderStatus::EXPIRED;
    }

    static double signed_quantity(Side side, double quantity) {
        return (side == Side::BUY ? 1.0 : -1.0) * quantity;
    }

    static bool same_direction(double a, double b) {
        return (a > 0.0 && b > 0.0) || (a < 0.0 && b < 0.0);
    }

    static void add_to_position(Position& p, double old_qty, double signed_fill_qty, double fill_price) {
        const double new_qty = old_qty + signed_fill_qty;
        const double old_notional = std::abs(old_qty) * p.avg_price;
        const double add_notional = std::abs(signed_fill_qty) * fill_price;
        p.quantity = new_qty;
        p.avg_price = is_flat(new_qty) ? 0.0 : (old_notional + add_notional) / std::abs(new_qty);
    }

    static void close_or_flip_position(Position& p, double old_qty, double signed_fill_qty,
                                       double fill_price, double commission) {
        const double closing_qty = std::min(std::abs(old_qty), std::abs(signed_fill_qty));
        const double opening_qty = std::max(0.0, std::abs(signed_fill_qty) - closing_qty);
        const double old_direction = old_qty > 0.0 ? 1.0 : -1.0;
        const double new_qty = old_qty + signed_fill_qty;

        const double closing_commission = commission * (closing_qty / std::abs(signed_fill_qty));
        const double opening_commission = commission - closing_commission;

        p.realized_pnl += closing_qty * (fill_price - p.avg_price) * old_direction;
        p.realized_pnl -= closing_commission;

        if (is_flat(new_qty)) {
            p.avg_price = 0.0;
        } else if (!same_direction(old_qty, new_qty)) {
            p.avg_price = fill_price;
            p.realized_pnl -= opening_commission;
        }

        if (opening_qty <= kEps) {
            p.realized_pnl -= opening_commission;
        }
    }

    void write_ledger(const OrderExecution& e, double effective_price, const Position& p) {
        if (ledger_.is_open()) {
            ledger_ << (++event_id_) << ',' << e.symbol << ',' << to_string(e.side) << ',' << e.filled_quantity << ','
                    << effective_price << ',' << e.commission << ',' << p.quantity << ',' << p.avg_price << ',' << p.realized_pnl << "\n";
            ledger_.flush();
        }
    }

    std::unordered_map<std::string, Position> positions_;
    std::unordered_map<std::string, double> last_price_;
    std::ofstream ledger_;
    uint64_t event_id_ = 0;
};