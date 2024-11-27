from amaranth import *
from amaranth.lib import data, io, stream, wiring
from amaranth.lib.wiring import In, Out, flipped, connect

from amaranth_stdio.serial import AsyncSerialRX, AsyncSerialTX


__all__ = ["UARTPhyRx", "UARTPhyTx", "UARTPhy"]


class UARTPhyRx(wiring.Component):
    class Signature(wiring.Signature):
        def __init__(self):
            super().__init__({
                "reset":    Out(1),
                "config":   Out(data.StructLayout({"divisor": unsigned(24)})),
                "symbols":  In(stream.Signature(unsigned(8))),
                "overflow": In(1),
                "error":    In(1),
            })

    def __init__(self, port, clk_freq):
        super().__init__(self.Signature().flip())
        self._port = port
        self._clk_freq = clk_freq

    def elaborate(self, platform):
        m = Module()

        m.submodules.io_buffer = io_buffer = io.Buffer("i", self._port)

        lower = AsyncSerialRX(divisor=int(self._clk_freq // 115200), divisor_bits=24)
        lower = ResetInserter(self.reset)(lower)
        m.submodules.lower = lower

        m.d.comb += [
            lower.i.eq(io_buffer.i),

            lower.divisor.eq(self.config.divisor),

            self.symbols.payload.eq(lower.data),
            self.symbols.valid.eq(lower.rdy),
            lower.ack.eq(self.symbols.ready),

            self.overflow.eq(lower.err.overflow),
            self.error.eq(lower.err.frame),
        ]

        return m


class UARTPhyTx(wiring.Component):
    class Signature(wiring.Signature):
        def __init__(self):
            super().__init__({
                "reset":   Out(1),
                "config":  Out(data.StructLayout({"divisor": unsigned(24)})),
                "symbols": Out(stream.Signature(unsigned(8)))
            })

    def __init__(self, port, clk_freq):
        super().__init__(self.Signature().flip())
        self._port = port
        self._clk_freq = clk_freq

    def elaborate(self, platform):
        m = Module()

        m.submodules.io_buffer = io_buffer = io.Buffer("o", self._port)

        lower = AsyncSerialTX(divisor=int(self._clk_freq // 115200), divisor_bits=24)
        lower = ResetInserter(self.reset)(lower)
        m.submodules.lower = lower

        m.d.comb += [
            io_buffer.o.eq(lower.o),

            lower.divisor.eq(self.config.divisor),

            lower.data.eq(self.symbols.payload),
            lower.ack.eq(self.symbols.valid),
            self.symbols.ready.eq(lower.rdy),
        ]

        return m


class UARTPhy(wiring.Component):
    class Signature(wiring.Signature):
        def __init__(self):
            super().__init__({
                "rx": Out(UARTPhyRx.Signature()),
                "tx": Out(UARTPhyTx.Signature()),
            })

    def __init__(self, ports, clk_freq):
        super().__init__(self.Signature().flip())
        self._rx = UARTPhyRx(ports.rx, clk_freq)
        self._tx = UARTPhyTx(ports.tx, clk_freq)

    def elaborate(self, platform):
        m = Module()

        m.submodules.rx = self._rx
        m.submodules.tx = self._tx

        connect(m, self._rx, flipped(self.rx))
        connect(m, self._tx, flipped(self.tx))

        return m
