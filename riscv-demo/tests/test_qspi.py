import unittest
from amaranth import *
from amaranth.lib import enum, io, data, wiring, stream
from amaranth.lib.wiring import In, Out, connect
from amaranth.lib.fifo import SyncFIFO
from amaranth.sim import *

from riscv_demo.ips.qspi.glasgow_qspi import QSPIMode, QSPIController
from riscv_demo.ips.qspi.qspi_flash import WishboneQSPIFlashController

class _QSPIFlashCommand(enum.Enum, shape=8):
    Read                = 0x03
    FastRead            = 0x0B
    FastReadDualOut     = 0x3B
    FastReadQuadOut     = 0x6B
    FastReadDualInOut   = 0xBB
    FastReadQuadInOut   = 0xEB


class _MockFlash(wiring.Component):
    def __init__(self):
        super().__init__({"o_octets": In(stream.Signature(data.StructLayout({
                "chip": range(2),
                "mode": QSPIMode,
                "data": 8
            }))),
            "i_octets": Out(stream.Signature(data.StructLayout({
                "data": 8
            }))),
            "divisor": In(16),
        })

    def elaborate(self, platform):
        m = Module()
        command = Signal(_QSPIFlashCommand, init=_QSPIFlashCommand.Read)
        address_count = Signal(2)
        address = Signal(24)

        m.d.comb += self.o_octets.ready.eq(1)
        m.d.sync += self.i_octets.valid.eq(0) # default

        with m.FSM():
            with m.State("IDLE"):
                with m.If(self.o_octets.valid):
                    m.d.sync += [
                        Assert(self.o_octets.p.chip == 1),
                        Assert(self.o_octets.p.mode == QSPIMode.PutX1),
                        command.eq(self.o_octets.p.data),
                        address_count.eq(2)
                    ]
                    m.next = "ADDRESS"
            with m.State("ADDRESS"):
                with m.If(self.o_octets.valid):
                    m.d.sync += [
                        Assert(self.o_octets.p.chip == 1),
                        Assert(self.o_octets.p.mode == QSPIMode.PutX1),
                        address.word_select(address_count, 8).eq(self.o_octets.p.data),
                        address_count.eq(address_count - 1)
                    ]
                    with m.If(address_count == 0):
                        m.next = "DATA"
            with m.State("DATA"):
                with m.If(self.o_octets.valid):
                    with m.If(self.o_octets.p.mode == QSPIMode.Dummy):
                        m.next = "IDLE"
                    with m.Else():
                        m.d.sync += [
                            Assert(self.o_octets.p.chip == 1),
                            Assert(self.o_octets.p.mode == QSPIMode.GetX1),
                            Assert(self.i_octets.ready == 1), # TODO: allowed to be not ready, too
                            self.i_octets.p.data.eq(0xAA ^ address[0:8]), # TODO: something more useful here
                            self.i_octets.valid.eq(1),
                            address.eq(address + 1)
                        ]

        return m

async def _wb_read(self, ctx, dut, addr, r_data):
    ctx.set(dut.wb_bus.adr, addr >> 2)
    ctx.set(dut.wb_bus.we, 0)
    ctx.set(dut.wb_bus.cyc, 1)
    ctx.set(dut.wb_bus.stb, 1)
    await ctx.tick()
    while ctx.get(dut.wb_bus.ack) == 0:
        await ctx.tick()        
    ctx.set(dut.wb_bus.cyc, 0)
    ctx.set(dut.wb_bus.stb, 0)
    self.assertEqual(ctx.get(dut.wb_bus.dat_r), r_data)

class QSPITestCase(unittest.TestCase):
    def test_sim(self):
        dut = WishboneQSPIFlashController(addr_width=24, data_width=32)
        phy = _MockFlash()

        m = Module()
        m.submodules.dut = dut
        m.submodules.phy = phy

        connect(m, dut.spi_bus, phy)

        async def testbench(ctx):
            await _wb_read(self, ctx, dut, 0x0, 0xa9a8abaa)
            await _wb_read(self, ctx, dut, 0x4, 0xadacafae)

        sim = Simulator(m)
        sim.add_clock(period=1 / 48e6)
        sim.add_testbench(testbench)
        with sim.write_vcd(vcd_file="test_qspi.vcd"):
            sim.run()

