import unittest
from amaranth import *
from amaranth.lib import io, wiring
from amaranth.lib.wiring import In, Out, connect
from amaranth.lib.fifo import SyncFIFO
from amaranth.sim import *

from riscv_demo.ips.ports import PortGroup
from riscv_demo.ips.uart import UARTPhy, UARTPeripheral


async def _csr_access(self, ctx, dut, addr, r_stb=0, r_data=0, w_stb=0, w_data=0):
    for offset in range(4):
        r_data_byte = (r_data >> (8 * offset)) & 0xff
        w_data_byte = (w_data >> (8 * offset)) & 0xff

        ctx.set(dut.csr_bus.addr, addr + offset)
        ctx.set(dut.csr_bus.r_stb, r_stb)
        ctx.set(dut.csr_bus.w_stb, w_stb)
        ctx.set(dut.csr_bus.w_data, w_data_byte)

        await ctx.tick()

        if r_stb:
            self.assertEqual(ctx.get(dut.csr_bus.r_data), r_data_byte)

        ctx.set(dut.csr_bus.r_stb, 0)
        ctx.set(dut.csr_bus.w_stb, 0)


class _LoopbackPHY(wiring.Component):
    def __init__(self):
        super().__init__(UARTPhy.Signature().flip())

    def elaborate(self, platform):
        m = Module()

        fifo = SyncFIFO(width=8, depth=4)
        fifo = ResetInserter(self.rx.reset | self.tx.reset)(fifo)
        m.submodules.fifo = fifo

        m.d.comb += [
            self.tx.symbols.ready.eq(fifo.w_rdy & ~self.tx.reset),
            fifo.w_en.eq(self.tx.symbols.valid),
            fifo.w_data.eq(self.tx.symbols.payload),

            self.rx.symbols.valid.eq(fifo.r_rdy),
            self.rx.symbols.payload.eq(fifo.r_data),
            fifo.r_en.eq(self.rx.symbols.ready),

            self.rx.overflow.eq(fifo.w_en & ~fifo.w_rdy),
        ]

        return m


class PeripheralTestCase(unittest.TestCase):
    def test_sim(self):
        ports = PortGroup()
        ports.rx = io.SimulationPort("i", 1)
        ports.tx = io.SimulationPort("o", 1)

        dut = UARTPeripheral(divisor_init=int(48e6 // 115200))
        phy = _LoopbackPHY()

        m = Module()
        m.submodules.dut = dut
        m.submodules.phy = phy

        connect(m, dut.phy.rx, phy.rx)
        connect(m, dut.phy.tx, phy.tx)

        rx_config_addr     = 0x000
        rx_phy_config_addr = 0x004
        rx_status_addr     = 0x008
        rx_data_addr       = 0x00c

        tx_config_addr     = 0x200
        tx_phy_config_addr = 0x204
        tx_status_addr     = 0x208
        tx_data_addr       = 0x20c

        async def testbench(ctx):
            # PHY disabled ========================================================================

            # - read RxStatus (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b000)

            # - read TxStatus (ready=0):
            await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=0)

            # - write "x" to TxData:
            await _csr_access(self, ctx, dut, tx_data_addr, w_stb=1, w_data=ord("x"))
            await ctx.tick()

            # - read RxStatus (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b000)

            # PHY disabled -> enabled =============================================================

            # - read RxConfig (enable=0) and write 1:
            await _csr_access(self, ctx, dut, rx_config_addr, r_stb=1, r_data=0, w_stb=1, w_data=1)
            await ctx.tick()

            # - read TxConfig (enable=0) and write 1:
            await _csr_access(self, ctx, dut, tx_config_addr, r_stb=1, r_data=0, w_stb=1, w_data=1)
            await ctx.tick()

            # - read RxStatus (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b000)

            # PHY enabled =========================================================================

            for c in "abcd":
                # - read TxStatus (ready=1):
                await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=1)

                # - write c to TxData:
                await _csr_access(self, ctx, dut, tx_data_addr, w_stb=1, w_data=ord(c))
                await ctx.tick()

            # - read RxStatus (ready=1, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b001)

            # - read TxStatus (ready=0):
            await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=0)

            # - write "e" to TxData:
            await _csr_access(self, ctx, dut, tx_data_addr, w_stb=1, w_data=ord("e"))
            await ctx.tick()

            # - read RxStatus (ready=1, overflow=1, error=0) and write 0b010:
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b011, w_stb=1,
                              w_data=0b010)
            await ctx.tick()

            for c in "abcd":
                # - read RxStatus (ready=1, overflow=0, error=0):
                await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b001)

                # - read RxData (=c)
                await _csr_access(self, ctx, dut, rx_data_addr, r_stb=1, r_data=ord(c))

            # - read RxStatus (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b000)

            # PHY enabled -> disabled =============================================================

            for c in "efgh":
                # - read TxStatus (ready=1):
                await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=1)

                # - write c to TxData:
                await _csr_access(self, ctx, dut, tx_data_addr, w_stb=1, w_data=ord(c))
                await ctx.tick()

            # - read TxStatus (ready=0):
            await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=0)

            # - read RxStatus (ready=1, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b001)

            # - read RxConfig (enable=1) and write 0:
            await _csr_access(self, ctx, dut, rx_config_addr, r_stb=1, r_data=1, w_stb=1, w_data=0)
            await ctx.tick()

            # - read TxConfig (enable=1) and write 0:
            await _csr_access(self, ctx, dut, tx_config_addr, r_stb=1, r_data=1, w_stb=1, w_data=0)
            await ctx.tick()

            # - read TxStatus (ready=0):
            await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=0)

            # - read RxStatus (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b000)

            # PHY disabled -> enabled =============================================================

            # - read RxConfig (enable=0) and write 1:
            await _csr_access(self, ctx, dut, rx_config_addr, r_stb=1, r_data=0, w_stb=1, w_data=1)
            await ctx.tick()

            # - read TxConfig (enable=0) and write 1:
            await _csr_access(self, ctx, dut, tx_config_addr, r_stb=1, r_data=0, w_stb=1, w_data=1)
            await ctx.tick()

            # - read TxStatus (ready=1):
            await _csr_access(self, ctx, dut, tx_status_addr, r_stb=1, r_data=1)

            # - read RxStatus (ready=0, overflow=0, error=0):
            await _csr_access(self, ctx, dut, rx_status_addr, r_stb=1, r_data=0b000)

        sim = Simulator(m)
        sim.add_clock(period=1 / 48e6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()
