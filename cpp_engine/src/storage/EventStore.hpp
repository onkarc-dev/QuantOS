#pragma once
#include "../time_utils.hpp"
#include "../trading/OrderTypes.hpp"
#include <filesystem>
#include <fstream>
#include <mutex>
#include <sstream>
#include <string>

class EventStore {
public:
    explicit EventStore(const std::string& path = "events.jsonl") : path_(path) {
        const auto parent = std::filesystem::path(path_).parent_path();
        if (!parent.empty()) {
            std::filesystem::create_directories(parent);
        }
        out_.open(path_, std::ios::out | std::ios::app);
    }

    void append(const std::string& type, const std::string& json_payload) {
        std::lock_guard<std::mutex> lock(mu_);
        if (!out_.is_open()) return;
        out_ << "{\"ts_ns\":" << now_ns()
             << ",\"type\":\"" << esc(type) << "\",\"payload\":" << json_payload << "}\n";
        out_.flush();
    }

    void signal(const std::string& symbol, const std::string& reason, double entry, double stop, double target1, double target2) {
        std::ostringstream ss;
        ss << "{\"symbol\":\"" << esc(symbol) << "\",\"reason\":\"" << esc(reason)
           << "\",\"entry\":" << entry << ",\"stop\":" << stop
           << ",\"target1\":" << target1 << ",\"target2\":" << target2 << "}";
        append("SIGNAL", ss.str());
    }

    void risk_decision(const std::string& symbol, bool approved, const std::string& reason, double notional) {
        std::ostringstream ss;
        ss << "{\"symbol\":\"" << esc(symbol) << "\",\"approved\":" << (approved?"true":"false")
           << ",\"reason\":\"" << esc(reason) << "\",\"notional\":" << notional << "}";
        append(approved ? "RISK_APPROVED" : "RISK_REJECT", ss.str());
    }

    void order(const OrderRequest& o) {
        std::ostringstream ss;
        ss << "{\"client_order_id\":" << o.client_order_id
           << ",\"symbol\":\"" << esc(o.symbol) << "\""
           << ",\"side\":\"" << to_string(o.side) << "\""
           << ",\"quantity\":" << o.quantity
           << ",\"limit_price\":" << o.limit_price
           << ",\"strategy_tag\":\"" << esc(o.strategy_tag) << "\"}";
        append("ORDER_SUBMIT", ss.str());
    }

    void execution(const OrderExecution& e) {
        std::ostringstream ss;
        ss << "{\"client_order_id\":" << e.client_order_id
           << ",\"broker_order_id\":\"" << esc(e.broker_order_id) << "\""
           << ",\"symbol\":\"" << esc(e.symbol) << "\""
           << ",\"side\":\"" << to_string(e.side) << "\""
           << ",\"status\":\"" << to_string(e.status) << "\""
           << ",\"requested_quantity\":" << e.requested_quantity
           << ",\"filled_quantity\":" << e.filled_quantity
           << ",\"fill_price\":" << e.fill_price
           << ",\"commission\":" << e.commission
           << ",\"message\":\"" << esc(e.message) << "\"}";
        append(e.status == OrderStatus::FILLED ? "ORDER_FILL" : "ORDER_EXECUTION", ss.str());
    }

    void position_snapshot(const std::string& symbol, double qty, double avg, double realized, double unrealized) {
        std::ostringstream ss;
        ss << "{\"symbol\":\"" << esc(symbol) << "\",\"qty\":" << qty << ",\"avg\":" << avg
           << ",\"realized\":" << realized << ",\"unrealized\":" << unrealized << "}";
        append("POSITION", ss.str());
    }

    void metric(const std::string& name, double value) {
        std::ostringstream ss;
        ss << "{\"name\":\"" << esc(name) << "\",\"value\":" << value << "}";
        append("METRIC", ss.str());
    }

private:
    static std::string esc(const std::string& s) {
        std::string r; r.reserve(s.size());
        for (char c : s) {
            if (c == '"') r += "\\\"";
            else if (c == '\\') r += "\\\\";
            else if (c == '\n') r += "\\n";
            else r += c;
        }
        return r;
    }
    std::string path_;
    std::ofstream out_;
    std::mutex mu_;
};
