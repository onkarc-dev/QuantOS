#pragma once
#include <chrono>
#include <cstdint>

inline uint64_t now_ns() noexcept {
    using clock = std::chrono::steady_clock;
    return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        clock::now().time_since_epoch()).count());
}
