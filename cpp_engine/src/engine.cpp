#include <iostream>
#include <thread>
#include "engine_shared.hpp"

// Define the global instances declared as 'extern' in the header
SimpleSPSCQueue<TradePacket, 65536> trade_queue;
std::atomic<bool> running{true};

class OrderBook {
public:
    void match(const TradePacket& p) {
        // High-performance matching logic (e.g., fixed-array lookups)
        // std::cout << "Matched: " << p.price << std::endl; 
    }
};

OrderBook book;

void processing_thread_func() {
    while (running.load(std::memory_order_relaxed)) {
        TradePacket p;
        if (trade_queue.pop(p)) {
            book.match(p);
        } else {
            PAUSE(); // Portable CPU pause
        }
    }
}

int main() {
    // Start the matching engine thread
    std::thread worker(processing_thread_func);
    
    // Ingestion loop logic would go here:
    // while (running) { ... trade_queue.push(new_packet); }
    
    // Graceful shutdown
    std::cout << "Press Enter to stop..." << std::endl;
    std::cin.get();
    
    running = false;
    worker.join();
    
    return 0;
}