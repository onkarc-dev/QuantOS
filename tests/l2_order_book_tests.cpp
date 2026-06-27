#include "trading/L2OrderBook.hpp"

#include <cassert>
#include <cmath>
#include <vector>

namespace {

void assert_near(double actual, double expected) {
    assert(std::fabs(actual - expected) < 1e-9);
}

void test_best_bid_and_ask_are_sorted() {
    L2OrderBook book;
    assert(book.set_bid(100.0, 1.0));
    assert(book.set_bid(101.0, 2.0));
    assert(book.set_bid(99.0, 3.0));
    assert(book.set_ask(103.0, 4.0));
    assert(book.set_ask(102.0, 5.0));
    assert(book.set_ask(104.0, 6.0));

    auto bid = book.best_bid();
    auto ask = book.best_ask();
    assert(bid.has_value());
    assert(ask.has_value());
    assert_near(bid->price, 101.0);
    assert_near(bid->quantity, 2.0);
    assert_near(ask->price, 102.0);
    assert_near(ask->quantity, 5.0);
}

void test_update_and_remove_levels() {
    L2OrderBook book;
    assert(book.set_bid(100.0, 1.0));
    assert(book.set_bid(100.0, 2.5));
    assert_near(book.bid_quantity(100.0), 2.5);
    assert(book.set_bid(100.0, 0.0));
    assert_near(book.bid_quantity(100.0), 0.0);
    assert(book.best_bid() == std::nullopt);

    assert(book.set_ask(101.0, 3.0));
    assert(book.remove_ask(101.0));
    assert(book.best_ask() == std::nullopt);
}

void test_depth_snapshots() {
    L2OrderBook book;
    assert(book.set_bid(100.0, 1.0));
    assert(book.set_bid(99.0, 2.0));
    assert(book.set_ask(101.0, 3.0));
    assert(book.set_ask(102.0, 4.0));

    const auto bids = book.bid_levels();
    const auto asks = book.ask_levels(1);
    assert(bids.size() == 2);
    assert(asks.size() == 1);
    assert_near(bids[0].price, 100.0);
    assert_near(bids[1].price, 99.0);
    assert_near(asks[0].price, 101.0);
}

} // namespace

int main() {
    test_best_bid_and_ask_are_sorted();
    test_update_and_remove_levels();
    test_depth_snapshots();
    return 0;
}
