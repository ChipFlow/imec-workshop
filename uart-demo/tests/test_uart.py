import unittest

from amaranth import *
from amaranth.lib import io
from amaranth.sim import *

from uart_demo.uart import LoopbackUART
from uart_demo.ports import PortGroup


class LoopbackUARTTestCase(unittest.TestCase):
    def test_hello(self):
        ports = PortGroup()
        ports.rx = io.SimulationPort("i", 1)
        ports.tx = io.SimulationPort("o", 1)

        dut = LoopbackUART(ports, clk_freq=48e6, baudrate=115200)

        # send "hello" to the UART receiver
        async def rx_testbench(ctx):
            ctx.set(ports.rx.i, 1)
            await ctx.delay(1 / dut.baudrate)

            for rx_chr in "hello":
                # send the start bit
                ctx.set(ports.rx.i, 0)
                await ctx.delay(1 / dut.baudrate)

                # send data bits
                for rx_bit in reversed(f"{ord(rx_chr):08b}"):
                    ctx.set(ports.rx.i, int(rx_bit))
                    await ctx.delay(1 / dut.baudrate)

                # send the stop bit
                ctx.set(ports.rx.i, 1)
                await ctx.delay(1 / dut.baudrate)

        # check that "hello" is transmitted back
        async def tx_testbench(ctx):
            for tx_chr in "hello":
                # wait for the start bit
                await ctx.negedge(ports.tx.o)
                await ctx.delay(1 / dut.baudrate)

                # check data bits
                for tx_bit in reversed(f"{ord(tx_chr):08b}"):
                    self.assertEqual(ctx.get(ports.tx.o), int(tx_bit))
                    await ctx.delay(1 / dut.baudrate)

                # check the stop bit
                self.assertEqual(ctx.get(ports.tx.o), 1)

        sim = Simulator(dut)
        sim.add_clock(period=1 / 48e6)
        sim.add_testbench(rx_testbench)
        sim.add_testbench(tx_testbench)

        with sim.write_vcd(vcd_file="test.vcd"):
            sim.run()
