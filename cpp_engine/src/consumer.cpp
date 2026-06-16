#include <atomic>
#include <csignal>
#include <iostream>
#include <string>
#include <vector>

#include <librdkafka/rdkafkacpp.h>
#include "proto/market_data.pb.h"

namespace {
std::atomic<bool> running{true};
void signal_handler(int) { running.store(false, std::memory_order_relaxed); }
}

int main(int argc, char** argv) {
    std::string brokers = "localhost:9092";
    std::string topic_name = "raw-trades";
    if (argc >= 2) brokers = argv[1];
    if (argc >= 3) topic_name = argv[2];

    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    std::string errstr;
    auto* conf = RdKafka::Conf::create(RdKafka::Conf::CONF_GLOBAL);
    conf->set("bootstrap.servers", brokers, errstr);
    conf->set("group.id", "market-data-consumer", errstr);
    conf->set("auto.offset.reset", "latest", errstr);
    conf->set("enable.auto.commit", "true", errstr);

    RdKafka::KafkaConsumer* consumer = RdKafka::KafkaConsumer::create(conf, errstr);
    delete conf;
    if (!consumer) {
        std::cerr << "Failed to create Kafka consumer: " << errstr << "\n";
        return 1;
    }

    consumer->subscribe({topic_name});
    std::cout << "kafka_consumer started brokers=" << brokers << " topic=" << topic_name << "\n";

    uint64_t received = 0;
    while (running.load(std::memory_order_relaxed)) {
        RdKafka::Message* msg = consumer->consume(1000);
        if (!msg) continue;

        if (msg->err() == RdKafka::ERR_NO_ERROR) {
            marketdata::Trade trade;
            if (trade.ParseFromArray(msg->payload(), static_cast<int>(msg->len()))) {
                ++received;
                // No per-message printing. It destroys throughput.
                if (received % 100000 == 0) {
                    std::cout << "received_total=" << received
                              << " last=" << trade.symbol()
                              << " price=" << trade.price()
                              << " volume=" << trade.volume() << "\n";
                }
            }
        } else if (msg->err() != RdKafka::ERR__TIMED_OUT && msg->err() != RdKafka::ERR__PARTITION_EOF) {
            std::cerr << "Kafka error: " << msg->errstr() << "\n";
        }
        delete msg;
    }

    consumer->close();
    delete consumer;
    return 0;
}
