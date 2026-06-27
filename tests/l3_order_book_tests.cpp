#include "../cpp_engine/src/trading/L3OrderBook.hpp"

#include <cassert>
#include <cmath>
#include <vector>

namespace {
using Book = L3OrderBook;

void assert_near(double actual, double expected) {
    assert(std::fabs(actual - expected) < 1e-9);
}

void test_insert_tracks_each_order_and_fifo() {
    Book book;
    assert(book.insert(101, Book::Side::Buy, 100.0, 5.0));
    assert(book.insert(102, Book::Side::Buy, 100.0, 7.0));
    assert(book.insert(103, Book::Side::Buy, 100.0, 9.0));
    assert(!book.insert(102, Book::Side::Buy, 100.0, 1.0));

    assert(book.size() == 3);
    assert(book.queue_position(101) == 1);
    assert(book.queue_position(102) == 2);
    assert(book.queue_position(103) == 3);
    assert((book.level_order_ids(Book::Side::Buy, 100.0) == std::vector<uint64_t>{101, 102, 103}));
    assert_near(book.level_quantity(Book::Side::Buy, 100.0), 21.0);
}

void test_modify_quantity_keeps_priority() {
    Book book;
    assert(book.insert(201, Book::Side::Sell, 101.0, 5.0));
    assert(book.insert(202, Book::Side::Sell, 101.0, 7.0));
    assert(book.modify_quantity(201, 12.5));

    auto first = book.get_order(201);
    assert(first.has_value());
    assert_near(first->quantity, 12.5);
    assert(book.queue_position(201) == 1);
    assert(book.queue_position(202) == 2);
    assert((book.level_order_ids(Book::Side::Sell, 101.0) == std::vector<uint64_t>{201, 202}));
}

void test_modify_price_loses_priority() {
    Book book;
    assert(book.insert(301, Book::Side::Buy, 100.0, 5.0));
    assert(book.insert(302, Book::Side::Buy, 101.0, 7.0));
    assert(book.insert(303, Book::Side::Buy, 101.0, 9.0));
    assert(book.modify_price(301, 101.0));

    auto moved = book.get_order(301);
    assert(moved.has_value());
    assert_near(moved->price, 101.0);
    assert(book.queue_position(302) == 1);
    assert(book.queue_position(303) == 2);
    assert(book.queue_position(301) == 3);
    assert((book.level_order_ids(Book::Side::Buy, 101.0) == std::vector<uint64_t>{302, 303, 301}));
}

void test_cancel_refreshes_queue_position() {
    Book book;
    assert(book.insert(401, Book::Side::Sell, 99.5, 1.0));
    assert(book.insert(402, Book::Side::Sell, 99.5, 1.0));
    assert(book.insert(403, Book::Side::Sell, 99.5, 1.0));
    assert(book.cancel(402));

    assert(!book.contains(402));
    assert(book.queue_position(401) == 1);
    assert(book.queue_position(403) == 2);
    assert((book.level_order_ids(Book::Side::Sell, 99.5) == std::vector<uint64_t>{401, 403}));
}

void test_trade_execution_partial_and_full_refreshes_position() {
    Book book;
    assert(book.insert(501, Book::Side::Buy, 100.0, 10.0));
    assert(book.insert(502, Book::Side::Buy, 100.0, 20.0));
    assert(book.insert(503, Book::Side::Buy, 100.0, 30.0));

    assert(book.execute_trade(501, 4.0));
    auto partial = book.get_order(501);
    assert(partial.has_value());
    assert_near(partial->quantity, 6.0);
    assert(book.queue_position(501) == 1);
    assert(book.queue_position(502) == 2);
    assert(book.queue_position(503) == 3);

    assert(book.execute_trade(501, 6.0));
    assert(!book.contains(501));
    assert(book.queue_position(502) == 1);
    assert(book.queue_position(503) == 2);
    assert((book.level_order_ids(Book::Side::Buy, 100.0) == std::vector<uint64_t>{502, 503}));
    assert_near(book.level_quantity(Book::Side::Buy, 100.0), 50.0);
}

void test_modify_quantity_to_zero_cancels() {
    Book book;
    assert(book.insert(601, Book::Side::Buy, 88.0, 1.0));
    assert(book.modify_quantity(601, 0.0));
    assert(!book.contains(601));
    assert(book.level_order_ids(Book::Side::Buy, 88.0).empty());
}
} // namespace

int main() {
    test_insert_tracks_each_order_and_fifo();
    test_modify_quantity_keeps_priority();
    test_modify_price_loses_priority();
    test_cancel_refreshes_queue_position();
    test_trade_execution_partial_and_full_refreshes_position();
    test_modify_quantity_to_zero_cancels();
    return 0;
}
