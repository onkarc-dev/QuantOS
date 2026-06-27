#pragma once

// Single source of truth for L2 types/book is order_book.hpp.
// This compatibility header prevents duplicate definitions when code includes
// market_data/l2_order_book.hpp and order_book.hpp in the same translation unit.
#include "../order_book.hpp"
