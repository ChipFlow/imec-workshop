from amaranth import *
from amaranth.lib import io, wiring
from amaranth.lib.wiring import In, Out, flipped, connect

from amaranth_soc import csr

from .phy import UARTPhy


__all__ = ["UARTPeripheral"]


class _PhyConfigFieldAction(csr.FieldAction):
    """A field that is read/write if `w_en` is asserted, and read-only otherwise."""
    def __init__(self, shape, *, init=0):
        super().__init__(shape, access="rw", members=(
            ("data", Out(shape)),
            ("w_en", In(1)),
        ))
        self._storage = Signal(shape, init=init)

    def elaborate(self, platform):
        m = Module()

        with m.If(self.w_en & self.port.w_stb):
            m.d.sync += self._storage.eq(self.port.w_data)

        m.d.comb += [
            self.port.r_data.eq(self._storage),
            self.data.eq(self._storage),
        ]

        return m


class UARTPeripheral(wiring.Component):
    class Config(csr.Register, access="rw"):
        enable: csr.Field(csr.action.RW,       1)
        _unimp: csr.Field(csr.action.ResRAW0, 31)

    class PhyConfig(csr.Register, access="rw"):
        def __init__(self, divisor_init):
            super().__init__({
                "divisor": csr.Field(_PhyConfigFieldAction, 24, init=divisor_init),
                "_unimp":  csr.Field(csr.action.ResRAWL,     8),
            })

    class RxStatus(csr.Register, access="rw"):
        ready:    csr.Field(csr.action.R,        1)
        overflow: csr.Field(csr.action.RW1C,     1)
        error:    csr.Field(csr.action.RW1C,     1)
        _unimp:   csr.Field(csr.action.ResRAW0, 29)

    class RxData(csr.Register, access="r"):
        symbol: csr.Field(csr.action.R,        8)
        _unimp: csr.Field(csr.action.ResRAWL, 24)

    class TxStatus(csr.Register, access="r"):
        ready:  csr.Field(csr.action.R,        1)
        _unimp: csr.Field(csr.action.ResRAW0, 31)

    class TxData(csr.Register, access="w"):
        symbol: csr.Field(csr.action.W,        8)
        _unimp: csr.Field(csr.action.ResRAWL, 24)

    def __init__(self, divisor_init):
        regs = csr.Builder(addr_width=10, data_width=8)

        with regs.Cluster("Rx"):
            self._rx_config     = regs.add("Config",    self.Config(),                offset=0x000)
            self._rx_phy_config = regs.add("PhyConfig", self.PhyConfig(divisor_init), offset=0x004)
            self._rx_status     = regs.add("Status",    self.RxStatus(),              offset=0x008)
            self._rx_data       = regs.add("Data",      self.RxData(),                offset=0x00c)

        with regs.Cluster("Tx"):
            self._tx_config     = regs.add("Config",    self.Config(),                offset=0x200)
            self._tx_phy_config = regs.add("PhyConfig", self.PhyConfig(divisor_init), offset=0x204)
            self._tx_status     = regs.add("Status",    self.TxStatus(),              offset=0x208)
            self._tx_data       = regs.add("Data",      self.TxData(),                offset=0x20c)

        self._csr_bridge = csr.Bridge(regs.as_memory_map())

        super().__init__({
            "csr_bus": In(csr.Signature(addr_width=10, data_width=8)),
            "phy":     Out(UARTPhy.Signature()),
        })
        self.csr_bus.memory_map = self._csr_bridge.bus.memory_map

    def elaborate(self, platform):
        m = Module()

        m.submodules.csr_bridge = self._csr_bridge

        connect(m, flipped(self.csr_bus), self._csr_bridge.bus)

        m.d.comb += [
            self.phy.rx.reset.eq(~self._rx_config.f.enable.data),

            self._rx_phy_config.f.divisor.w_en.eq(self.phy.rx.reset),
            self.phy.rx.config.divisor.eq(self._rx_phy_config.f.divisor.data),

            self._rx_status.f.ready.r_data.eq(self.phy.rx.symbols.valid),
            self._rx_status.f.overflow.set.eq(self.phy.rx.overflow),
            self._rx_status.f.error.set.eq(self.phy.rx.error),

            self._rx_data.f.symbol.r_data.eq(self.phy.rx.symbols.payload),
            self.phy.rx.symbols.ready.eq(self._rx_data.f.symbol.r_stb),
        ]

        m.d.comb += [
            self.phy.tx.reset.eq(~self._tx_config.f.enable.data),

            self._tx_phy_config.f.divisor.w_en.eq(self.phy.tx.reset),
            self.phy.tx.config.divisor.eq(self._tx_phy_config.f.divisor.data),

            self._tx_status.f.ready.r_data.eq(self.phy.tx.symbols.ready),

            self.phy.tx.symbols.payload.eq(self._tx_data.f.symbol.w_data),
            self.phy.tx.symbols.valid.eq(self._tx_data.f.symbol.w_stb),
        ]

        return m
