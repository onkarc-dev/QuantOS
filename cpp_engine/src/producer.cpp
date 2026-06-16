#include <atomic>
#include <chrono>
#include <csignal>
#include <cstring>
#include <iostream>
#include <string>
#include <thread>

#include <librdkafka/rdkafkacpp.h>
#include "proto/market_data.pb.h"

namespace {
std::atomic<bool> running{true};

void signal_handler(int) { running.store(false, std::memory_order_relaxed); }

uint64_t epoch_ns() {
    using clock = std::chrono::system_clock;
    return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        clock::now().time_since_epoch()).count());
}

class DeliveryReportCb final : public RdKafka::DeliveryReportCb {
public:
    void dr_cb(RdKafka::Message& message) override {
        if (message.err()) {
            std::cerr << "Delivery failed: " << message.errstr() << "\n";
        }
    }
};
}

int main(int argc, char** argv) {
    std::string brokers = "localhost:9092";
    std::string topic_name = "raw-trades";
    uint64_t rate_per_sec = 100000;
    if (argc >= 2) brokers = argv[1];
    if (argc >= 3) topic_name = argv[2];
    if (argc >= 4) rate_per_sec = std::stoull(argv[3]);

    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    std::string errstr;
    auto* conf = RdKafka::Conf::create(RdKafka::Conf::CONF_GLOBAL);
    DeliveryReportCb dr_cb;

    conf->set("bootstrap.servers", brokers, errstr);
    conf->set("dr_cb", &dr_cb, errstr);
    conf->set("acks", "1", errstr);
    conf->set("compression.type", "none", errstr);
    conf->set("linger.ms", "0", errstr);
    conf->set("batch.num.messages", "10000", errstr);

    RdKafka::Producer* producer = RdKafka::Producer::create(conf, errstr);
    delete conf;
    if (!producer) {
        std::cerr << "Failed to create Kafka producer: " << errstr << "\n";
        return 1;
    }

    std::cout << "kafka_producer started brokers=" << brokers
              << " topic=" << topic_name
              << " target_rate=" << rate_per_sec << " msg/s\n";

    const uint64_t interval_ns = rate_per_sec ? 1'000'000'000ULL / rate_per_sec : 0;
    auto steady_start = std::chrono::steady_clock::now();
    uint64_t sent = 0;
    uint64_t last_print = 0;

    while (running.load(std::memory_order_relaxed)) {
        if (interval_ns > 0) {
            const auto due = steady_start + std::chrono::nanoseconds(sent * interval_ns);
            while (std::chrono::steady_clock::now() < due) {}
        }

        marketdata::Trade trade;
        trade.set_exchange_id("SIM");
        trade.set_symbol("BTCUSDT");
        trade.set_timestamp_ns(static_cast<int64_t>(epoch_ns()));
        trade.set_price(65000.0 + static_cast<double>(sent % 10000) * 0.01);
        trade.set_volume(0.01 + static_cast<double>(sent % 100) * 0.0001);
        trade.set_trade_id(std::to_string(sent));

        std::string payload;
        trade.SerializeToString(&payload);

        RdKafka::ErrorCode rc = producer->produce(
            topic_name, RdKafka::Topic::PARTITION_UA,
            RdKafka::Producer::RK_MSG_COPY,
            const_cast<char*>(payload.data()), payload.size(),
            nullptr, 0, 0, nullptr);

        if (rc == RdKafka::ERR__QUEUE_FULL) {
            producer->poll(1);
            continue;
        } else if (rc != RdKafka::ERR_NO_ERROR) {
            std::cerr << "produce failed: " << RdKafka::err2str(rc) << "\n";
        } else {
            ++sent;
        }

        producer->poll(0);
        if (sent - last_print >= rate_per_sec) {
            std::cout << "sent_total=" << sent << "\n";
            last_print = sent;
        }
    }

    std::cout << "flushing producer...\n";
    producer->flush(5000);
    delete producer;
    return 0;
}
