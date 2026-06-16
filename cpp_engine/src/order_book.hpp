#pragma once

#include "engine_shared.hpp"

#include <atomic>
#include <cstdint>

class FastOrderBook
{
public:
    FastOrderBook() = default;

    inline void match(const TradePacket& trade)
    {
        last_price_.store(trade.price, std::memory_order_relaxed);

        total_volume_.fetch_add(
            static_cast<uint64_t>(trade.volume),
            std::memory_order_relaxed
        );

        total_trades_.fetch_add(1, std::memory_order_relaxed);
    }

    inline double last_price() const
    {
        return last_price_.load(std::memory_order_relaxed);
    }

    inline uint64_t total_volume() const
    {
        return total_volume_.load(std::memory_order_relaxed);
    }

    inline uint64_t total_trades() const
    {
        return total_trades_.load(std::memory_order_relaxed);
    }

    inline uint64_t updates() const
    {
        return total_trades_.load(std::memory_order_relaxed);
    }

private:
    std::atomic<double> last_price_{0.0};
    std::atomic<uint64_t> total_volume_{0};
    std::atomic<uint64_t> total_trades_{0};
};