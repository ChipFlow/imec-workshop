#ifndef MODELS_H
#define MODELS_H

#include <cxxrtl/cxxrtl.h>
#include <string>
#include <vector>
#include <algorithm>
#include <optional>

#include "vendor/nlohmann/json.hpp"

namespace cxxrtl_design {

using namespace cxxrtl;

using json = nlohmann::json;

std::string stringf(const char *format, ...);

struct action {
    action(const std::string &event, const json &payload) : event(event), payload(payload) {};
    std::string event;
    json payload;
};

void open_event_log(const std::string &filename);
void open_input_commands(const std::string &filename);
void log_event(unsigned timestamp, const std::string &peripheral, const std::string &event_type, json payload);
std::vector<action> get_pending_actions(const std::string &peripheral);
void close_event_log();

struct spiflash_model {
    std::string name;
    spiflash_model(const std::string &name, const value<1> &clk, const value<1> &csn, const value<4> &d_o, const value<4> &d_oe, value<4> &d_i) :
        name(name), clk(clk), csn(csn), d_o(d_o), d_oe(d_oe), d_i(d_i) {
        data.resize(16*1024*1024);
        std::fill(data.begin(), data.end(), 0xFF); // flash starting value
    };

    void load_data(const std::string &filename, unsigned offset);
    void step(unsigned timestamp);

private:
    std::vector<uint8_t> data;
    const value<1> &clk;
    const value<1> &csn;
    const value<4> &d_o;
    const value<4> &d_oe;
    value<4> &d_i;
    // model state
    struct {
        bool last_clk = false, last_csn = false;
        int bit_count = 0;
        int byte_count = 0;
        unsigned data_width = 1;
        uint32_t addr = 0;
        uint8_t curr_byte = 0;
        uint8_t command = 0;
        uint8_t out_buffer = 0;
    } s;
};

struct uart_model {
    std::string name;
    uart_model(const std::string &name, const value<1> &tx, value<1> &rx, unsigned baud_div = 48000000/115200) : name(name), tx(tx), rx(rx), baud_div(baud_div) {};

    void step(unsigned timestamp);
private:
    const value<1> &tx;
    value<1> &rx;
    unsigned baud_div;

    // model state
    struct {
        bool tx_last;
        int rx_counter = 0;
        uint8_t rx_sr = 0;
        bool tx_active = false;
        int tx_counter = 0;
        uint8_t tx_data = 0;
    } s;
};

}

#endif
