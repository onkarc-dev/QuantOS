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
        const bool has_fill = e.filled_quantity > 0.0;
        const bool fill_status = e.status == OrderStatus::FILLED || e.status == OrderStatus::PARTIALLY_FILLED || e.status == OrderStatus::EXPIRED;
        if (!has_fill || !fill_status) return;

        auto& p = positions_[e.symbol];
        p.symbol = e.symbol;
        const double effective_price = e.fill_price > 0.0 ? e.fill_price : e.avg_fill_price;
        if (effective_price <= 0.0) return;

        const double signed_qty = (e.side == Side::BUY ? 1.0 : -1.0) * e.filled_quantity;
        const double old_qty = p.quantity;
        const double new_qty = old_qty + signed_qty;
        if (std::abs(old_qty) < 1e-12 || (old_qty > 0) == (signed_qty > 0)) {
            const double old_notional = std::abs(old_qty) * p.avg_price;
            const double add_notional = std::abs(signed_qty) * effective_price;
            p.avg_price = (std::abs(new_qty) > 1e-12) ? (old_notional + add_notional) / std::abs(new_qty) : 0.0;
            p.realized_pnl -= e.commission;
        } else {
            const double closing_qty = std::min(std::abs(old_qty), std::abs(signed_qty));
            const double direction = old_qty > 0 ? 1.0 : -1.0;
            p.realized_pnl += closing_qty * (effective_price - p.avg_price) * direction - e.commission;
            if (std::abs(new_qty) < 1e-12) p.avg_price = 0.0;
            else if ((new_qty > 0) != (old_qty > 0)) p.avg_price = effective_price;
        }
        p.quantity = new_qty;
        if (ledger_.is_open()) {
            ledger_ << (++event_id_) << ',' << e.symbol << ',' << to_string(e.side) << ',' << e.filled_quantity << ','
                    << effective_price << ',' << e.commission << ',' << p.quantity << ',' << p.avg_price << ',' << p.realized_pnl << "\n";
            ledger_.flush();
        }
    }

    void mark(const std::string& symbol, double price) {
        last_price_[symbol] = price;
        auto it = positions_.find(symbol);
        if (it == positions_.end()) return;
        auto& p = it->second;
        p.unrealized_pnl = p.quantity * (price - p.avg_price);
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
    std::unordered_map<std::string, Position> positions_;
    std::unordered_map<std::string, double> last_price_;
    std::ofstream ledger_;
    uint64_t event_id_ = 0;
};
