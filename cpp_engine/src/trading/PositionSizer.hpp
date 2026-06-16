#pragma once
#include <algorithm>
#include <cmath>

class PositionSizer {
public:
    static double fixed_fractional(double equity, double risk_pct, double entry, double stop,
                                   double max_notional, double lot_step = 0.000001) {
        const double risk_per_unit = std::abs(entry - stop);
        if (equity <= 0.0 || risk_pct <= 0.0 || risk_per_unit <= 0.0 || entry <= 0.0) return 0.0;
        const double risk_amount = equity * risk_pct;
        const double qty_by_risk = risk_amount / risk_per_unit;
        const double qty_by_notional = max_notional / entry;
        double qty = std::min(qty_by_risk, qty_by_notional);
        if (lot_step > 0.0) qty = std::floor(qty / lot_step) * lot_step;
        return std::max(0.0, qty);
    }
};
