#pragma once
#include "../time_utils.hpp"
#include "../trading/OrderTypes.hpp"
#include <filesystem>
#include <fstream>
#include <iomanip>
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
        const std::string payload = order_payload(o);
        append("ORDER_SUBMIT", payload);
        append_order_lifecycle(payload);
    }

    void execution(const OrderExecution& e) {
        const std::string payload = execution_payload(e);

        // Backward-compatible event names used by existing UI/API consumers.
        append(e.status == OrderStatus::FILLED ? "ORDER_FILL" : "ORDER_EXECUTION", payload);

        // Normalized lifecycle stream for durable audit/replay/analytics consumers.
        append_execution_lifecycle(payload);
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
    static constexpr const char* lifecycle_event_types_[9] = {
        "ORDER_EVENT",
        "TRADE_EVENT",
        "EXECUTION_EVENT",
        "PORTFOLIO_EVENT",
        "RISK_EVENT",
        "ANALYTICS_EVENT",
        "LATENCY_EVENT",
        "QUEUE_EVENT",
        "FILL_QUALITY_EVENT"
    };

    static std::string order_payload(const OrderRequest& o) {
        std::ostringstream ss;
        ss << "{\"source\":\"paper_broker\""
           << ",\"event_stage\":\"order\""
           << ",\"client_order_id\":" << o.client_order_id
           << ",\"symbol\":\"" << esc(o.symbol) << "\""
           << ",\"side\":\"" << to_string(o.side) << "\""
           << ",\"quantity\":" << o.quantity
           << ",\"limit_price\":" << o.limit_price
           << ",\"strategy_tag\":\"" << esc(o.strategy_tag) << "\"}";
        return ss.str();
    }

    static std::string execution_payload(const OrderExecution& e) {
        std::ostringstream ss;
        ss << "{\"source\":\"paper_broker\""
           << ",\"event_stage\":\"execution\""
           << ",\"client_order_id\":" << e.client_order_id
           << ",\"broker_order_id\":\"" << esc(e.broker_order_id) << "\""
           << ",\"symbol\":\"" << esc(e.symbol) << "\""
           << ",\"side\":\"" << to_string(e.side) << "\""
           << ",\"status\":\"" << to_string(e.status) << "\""
           << ",\"requested_quantity\":" << e.requested_quantity
           << ",\"filled_quantity\":" << e.filled_quantity
           << ",\"remaining_quantity\":" << e.remaining_quantity
           << ",\"fill_price\":" << e.fill_price
           << ",\"avg_fill_price\":" << e.avg_fill_price
           << ",\"commission\":" << e.commission
           << ",\"exchange_ts_ns\":" << e.exchange_ts_ns
           << ",\"ack_ts_ns\":" << e.ack_ts_ns
           << ",\"message\":\"" << esc(e.message) << "\"}";
        return ss.str();
    }

    void append_order_lifecycle(const std::string& order_json_payload) {
        for (const char* type : lifecycle_event_types_) {
            append(type, order_json_payload);
        }
    }

    void append_execution_lifecycle(const std::string& execution_json_payload) {
        for (const char* type : lifecycle_event_types_) {
            append(type, execution_json_payload);
        }
    }

    static std::string esc(const std::string& s) {
        std::string r; r.reserve(s.size());
        for (unsigned char c : s) {
            switch (c) {
                case '"': r += "\\\""; break;
                case '\\': r += "\\\\"; break;
                case '\b': r += "\\b"; break;
                case '\f': r += "\\f"; break;
                case '\n': r += "\\n"; break;
                case '\r': r += "\\r"; break;
                case '\t': r += "\\t"; break;
                default:
                    if (c < 0x20) {
                        std::ostringstream ss;
                        ss << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(c);
                        r += ss.str();
                    } else {
                        r += static_cast<char>(c);
                    }
            }
        }
        return r;
    }
    std::string path_;
    std::ofstream out_;
    std::mutex mu_;
};
