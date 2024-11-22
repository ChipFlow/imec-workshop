#undef NDEBUG

#include <cxxrtl/cxxrtl.h>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <fstream>
#include <stdarg.h>
#include <unordered_map>
#include "models.h"

namespace cxxrtl_design {

// Helper functions

std::string vstringf(const char *fmt, va_list ap)
{
    std::string string;
    char *str = NULL;

#if defined(_WIN32) || defined(__CYGWIN__)
    int sz = 64 + strlen(fmt), rc;
    while (1) {
        va_list apc;
        va_copy(apc, ap);
        str = (char *)realloc(str, sz);
        rc = vsnprintf(str, sz, fmt, apc);
        va_end(apc);
        if (rc >= 0 && rc < sz)
            break;
        sz *= 2;
    }
#else
    if (vasprintf(&str, fmt, ap) < 0)
        str = NULL;
#endif

    if (str != NULL) {
        string = str;
        free(str);
    }

    return string;
}

std::string stringf(const char *format, ...)
{
    va_list ap;
    va_start(ap, format);
    std::string result = vstringf(format, ap);
    va_end(ap);
    return result;
}

// Action generation
namespace {
json input_cmds;
size_t input_ptr = 0;
std::unordered_map<std::string, std::vector<action>> queued_actions;

// Update the queued_actions map
void fetch_actions_into_queue() {
    while (input_ptr < input_cmds.size()) {
        auto &cmd = input_cmds.at(input_ptr);
        if (cmd["type"] == "wait")
            break;
        if (cmd["type"] != "action")
            throw std::out_of_range("invalid 'type' value for command");
        queued_actions[cmd["peripheral"]].emplace_back(cmd["event"], cmd["payload"]);
        ++input_ptr;
    }
}
}

void open_input_commands(const std::string &filename) {
    std::ifstream f(filename);
    if (!f) {
        throw std::runtime_error("failed to open event log for writing!");
    }
    json data = json::parse(f);
    input_cmds = data["commands"];
}

// Event logging

static std::ofstream event_log;

void open_event_log(const std::string &filename) {
    event_log.open(filename);
    if (!event_log) {
        throw std::runtime_error("failed to open event log for writing!");
    }
    event_log << "{" << std::endl;
    event_log << "\"events\": [" << std::endl;
    fetch_actions_into_queue();
}

void log_event(unsigned timestamp, const std::string &peripheral, const std::string &event_type, json payload) {
    static bool had_event = false;
    // Note: we don't use the JSON library to serialise the output event overall, so we get a partial log
    // even if the simulation crashes.
    // But we use `json` objects as a container for complex payloads that can be compared with the action input
    if (had_event)
        event_log << "," << std::endl;
    auto payload_str = payload.dump();
    event_log << stringf("{ \"timestamp\": %u, \"peripheral\": \"%s\", \"event\": \"%s\", \"payload\": %s }",
        timestamp, peripheral.c_str(), event_type.c_str(), payload_str.c_str());
    had_event = true;
    // Check if we have actions waiting on this
    if (input_ptr < input_cmds.size()) {
        const auto &cmd = input_cmds.at(input_ptr);
        // fetch_actions_into_queue should never leave input_ptr sitting on an action
        assert(cmd["type"] == "wait");
        if (cmd["peripheral"] == peripheral && cmd["event"] == event_type && cmd["payload"] == payload) {
            ++input_ptr;
            fetch_actions_into_queue();
        }
    }
}

std::vector<action> get_pending_actions(const std::string &peripheral) {
    std::vector<action> result;
    if (queued_actions.count(peripheral))
        std::swap(queued_actions.at(peripheral), result);
    return result;
}

void close_event_log() {
    event_log << std::endl << "]" << std::endl;
    event_log << "}" << std::endl;
    if (input_ptr != input_cmds.size()) {
        fprintf(stderr, "WARNING: not all input actions were executed (%d/%d remain)!\n",
             int(input_cmds.size()) - int(input_ptr), int(input_cmds.size()));
    }
}

// SPI flash
void spiflash_model::load_data(const std::string &filename, unsigned offset) {
    std::ifstream in(filename, std::ifstream::binary);
    if (offset >= data.size()) {
        throw std::out_of_range("flash: offset beyond end");
    }
    if (!in) {
        throw std::runtime_error("flash: failed to read input file: " + filename);
    }
    in.read(reinterpret_cast<char*>(data.data() + offset), (data.size() - offset));
}
void spiflash_model::step(unsigned timestamp) {
    auto process_byte = [&]() {
        s.out_buffer = 0;
        if (s.byte_count == 0) {
            s.addr = 0;
            s.data_width = 1;
            s.command = s.curr_byte;
            if (s.command == 0xab) {
                // power up
            } else if (s.command == 0x03 || s.command == 0x9f || s.command == 0xff
                || s.command == 0x35 || s.command == 0x31 || s.command == 0x50
                || s.command == 0x05 || s.command == 0x01 || s.command == 0x06) {
                // nothing to do
            } else if (s.command == 0xeb) {
                s.data_width = 4;
            } else {
                throw std::runtime_error(stringf("flash: unknown command %02x", s.command));
            }
        } else {
            if (s.command == 0x03) {
                // Single read
                if (s.byte_count <= 3) {
                    s.addr |= (uint32_t(s.curr_byte) << ((3 - s.byte_count) * 8));
                }
                if (s.byte_count >= 3) {
                    s.out_buffer = data.at(s.addr);
                    s.addr = (s.addr + 1) & 0x00FFFFFF;
                }
            } else if (s.command == 0xeb) {
                // Quad read
                if (s.byte_count <= 3) {
                    s.addr |= (uint32_t(s.curr_byte) << ((3 - s.byte_count) * 8));
                }
                if (s.byte_count >= 4) {
                    // read 4 bytes
                    s.out_buffer = data.at(s.addr);
                    s.addr = (s.addr + 1) & 0x00FFFFFF;
                }
            }
        }
        if (s.command == 0x9f) {
            // Read ID
            static const std::array<uint8_t, 4> flash_id{0xCA, 0x7C, 0xA7, 0xFF};
            s.out_buffer = flash_id.at(s.byte_count % int(flash_id.size()));
        }
    };

    if (csn && !s.last_csn) {
        s.bit_count = 0;
        s.byte_count = 0;
        s.data_width = 1;
    } else if (clk && !s.last_clk && !csn) {
        if (s.data_width == 4)
            s.curr_byte = (s.curr_byte << 4U) | (d_o.get<uint32_t>() & 0xF);
        else
            s.curr_byte = (s.curr_byte << 1U) | d_o.bit(0);
        s.out_buffer = s.out_buffer << unsigned(s.data_width);
        s.bit_count += s.data_width;
        if (s.bit_count == 8) {
            process_byte();
            ++s.byte_count;
            s.bit_count = 0;
        }
    } else if (!clk && s.last_clk && !csn) {
        if (s.data_width == 4) {
            d_i.set((s.out_buffer >> 4U) & 0xFU);
        } else {
            d_i.set(((s.out_buffer >> 7U) & 0x1U) << 1U);
        }
    }
    s.last_clk = bool(clk);
    s.last_csn = bool(csn);
}

// UART

void uart_model::step(unsigned timestamp) {

    for (auto action : get_pending_actions(name)) {
        if (action.event == "tx") {
            s.tx_active = true;
            s.tx_data = uint8_t(action.payload);
        }
    }

    if (s.rx_counter == 0) {
        if (s.tx_last && !tx) { // start bit
            s.rx_counter = 1;
        }
    } else {
        ++s.rx_counter;
        if (s.rx_counter > (baud_div / 2) && ((s.rx_counter - (baud_div / 2)) % baud_div) == 0) {
            int bit = ((s.rx_counter - (baud_div / 2)) / baud_div);
            if (bit >= 1 && bit <= 8) {
                // update shift register
                s.rx_sr = (tx ? 0x80U : 0x00U) | (s.rx_sr >> 1U);
            }
            if (bit == 8) {
                // print to console
                log_event(timestamp, name, "tx", json(s.rx_sr));
                if (name == "uart")
                    fprintf(stderr, "%c", char(s.rx_sr));
            }
            if (bit == 9) {
                // end
                s.rx_counter = 0;
            }
        }
    }
    s.tx_last = bool(tx);

    if (s.tx_active) {
        ++s.tx_counter;
        int bit = (s.tx_counter  / baud_div);
        if (bit == 0) {
            rx.set(0); // start
        } else if (bit >= 1 && bit <= 8) {
            rx.set((s.tx_data  >> (bit - 1)) & 0x1);
        } else if (bit == 9) { // stop
            rx.set(1);
        } else {
            s.tx_active = false;
        }
    } else {
        s.tx_counter = 0;
        rx.set(1); // idle
    }
}

}
