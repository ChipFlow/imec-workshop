from amaranth import *
from amaranth.lib import io, wiring

from amaranth_stdio.serial import AsyncSerial


__all__ = ["LoopbackUART"]


class LoopbackUART(wiring.Component):
    def __init__(self, ports, clk_freq, baudrate=115200):
        super().__init__({})
        self.ports = ports
        self.clk_freq = clk_freq
        self.baudrate = baudrate

    def elaborate(self, platform):
        m = Module()

        m.submodules.rx_buffer = rx_buffer = io.Buffer("i", self.ports.rx)
        m.submodules.tx_buffer = tx_buffer = io.Buffer("o", self.ports.tx)

        m.submodules.uart = uart = AsyncSerial(divisor=int(self.clk_freq // self.baudrate))

        m.d.comb += [
            uart.rx.i.eq(rx_buffer.i),
            tx_buffer.o.eq(uart.tx.o),

            uart.rx.ack .eq(uart.tx.rdy),
            uart.tx.data.eq(uart.rx.data),
            uart.tx.ack .eq(uart.rx.rdy),
        ]

        return m
