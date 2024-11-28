#undef NDEBUG

#include <cxxrtl/cxxrtl.h>
#include <cxxrtl/cxxrtl_server.h>
#include <cxxrtl/cxxrtl_vcd.h>
#include "sim_soc.h"
#include "models.h"

#include <fstream>
#include <filesystem>

using namespace cxxrtl::time_literals;
using namespace cxxrtl_design;

int main(int argc, char **argv) {
    p_sim__top top;

    spiflash_model flash("flash",
        top.p_qspi__sck____o,
        top.p_qspi__cs____o,
        top.p_qspi__io____o, top.p_qspi__io____oe, top.p_qspi__io____i);

    uart_model uart("uart", top.p_uart__tx____o, top.p_uart__rx____i);

    cxxrtl::agent agent(cxxrtl::spool("spool.bin"), top);
    if (getenv("DEBUG")) // can also be done when a condition is violated, etc
        std::cerr << "Waiting for debugger on " << agent.start_debugging() << std::endl;

    cxxrtl::vcd_writer vcd;
    std::ofstream vcd_file;
    debug_items debug_items;
    uint64_t cycle = 0;

    if (getenv("TRACE")) {
        vcd_file.open("trace.vcd");
        top.debug_info(&debug_items, /*scopes=*/nullptr, "");
        vcd.timescale(1, "us");
        vcd.add_without_memories(debug_items);
    }

    unsigned timestamp = 0;
    auto tick = [&]() {
        flash.step(timestamp);
        uart.step(timestamp);

        top.p_clk.set(false);
        agent.step();
        agent.advance(1_us);
        ++timestamp;

        if (getenv("TRACE"))
            vcd.sample(2 * cycle);

        top.p_clk.set(true);
        agent.step();
        agent.advance(1_us);
        ++timestamp;

        if (timestamp % 100000 == 0)
            agent.snapshot();

        if (getenv("TRACE")) {
            vcd.sample(2 * cycle + 1);
            vcd_file << vcd.buffer;
            vcd.buffer.clear();
            cycle += 1;
        }
    };

    flash.load_data("../../zephyr.bin", 0x00100000U);
    agent.step();
    agent.advance(1_us);

    top.p_rst.set(true);
    tick();

    top.p_rst.set(false);
    while (1)
        tick();

    return 0;
}
