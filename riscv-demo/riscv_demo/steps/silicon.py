from amaranth import *
from amaranth.lib import io
from amaranth.lib.cdc import FFSynchronizer

from chipflow_lib.platforms.silicon import SiliconPlatformPort
from chipflow_lib.steps.silicon import SiliconStep

from ..soc import DemoSoC
from ..ips.ports import PortGroup


__all__ = ["IHP130SiliconStep"]


class _IHP130Top(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        # Clock generation
        m.domains.sync = ClockDomain()

        m.submodules.clk_buffer = clk_buffer = io.Buffer("i", platform.request("sys_clk"))
        m.submodules.rst_buffer = rst_buffer = io.Buffer("i", ~platform.request("sys_rst_n"))

        m.d.comb += ClockSignal().eq(clk_buffer.i)
        m.submodules.rst_sync = FFSynchronizer(rst_buffer.i, ResetSignal())

        # Heartbeat LED (to confirm clock/reset alive)
        heartbeat_ctr = Signal(23)
        m.d.sync += heartbeat_ctr.eq(heartbeat_ctr + 1)

        m.submodules.heartbeat_buffer = heartbeat_buffer = \
                io.Buffer("o", platform.request("heartbeat"))
        m.d.comb += heartbeat_buffer.o.eq(heartbeat_ctr[-1])

        # SoC ports
        ports = PortGroup()

        ports.qspi = PortGroup()
        ports.qspi.sck = platform.request("flash_clk")
        ports.qspi.io = (platform.request("flash_d0") + platform.request("flash_d1") +
                         platform.request("flash_d2") + platform.request("flash_d3"))
        ports.qspi.cs = platform.request("flash_csn")

        ports.uart = PortGroup()
        ports.uart.rx = platform.request("uart0_rx")
        ports.uart.tx = platform.request("uart0_tx")

        m.submodules.soc = soc = DemoSoC(ports)

        return m


class IHP130SiliconStep(SiliconStep):
    def prepare(self):
        return self.platform.build(_IHP130Top(), name="ihp130_top")
