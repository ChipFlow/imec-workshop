from amaranth import *
from amaranth.lib import wiring
from amaranth.lib.wiring import connect

from amaranth_soc import csr, wishbone
from amaranth_soc.csr.wishbone import WishboneCSRBridge
from amaranth_soc.wishbone.sram import WishboneSRAM

from minerva.core import Minerva

from .ips.qspi import QSPIController, WishboneQSPIFlashController
from .ips.uart import UARTPhy, UARTPeripheral


__all__ = ["DemoSoC"]


class DemoSoC(wiring.Component):
    def __init__(self, ports):
        super().__init__({})

        self.ports = ports

        # Memory regions:
        self.mem_spiflash_base = 0x00000000
        self.mem_sram_base     = 0x10000000

        # CSR regions:
        self.csr_base          = 0xb0000000
        self.csr_spiflash_base = 0xb0000000
        self.csr_uart_base     = 0xb2000000

        self.sram_size  = 0x400    # 1KiB
        self.bios_start = 0x100000 # 1MiB into spiflash

    def elaborate(self, platform):
        m = Module()

        wb_arbiter  = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8)
        wb_decoder  = wishbone.Decoder(addr_width=30, data_width=32, granularity=8)
        csr_decoder = csr.Decoder(addr_width=28, data_width=8)

        m.submodules.wb_arbiter  = wb_arbiter
        m.submodules.wb_decoder  = wb_decoder
        m.submodules.csr_decoder = csr_decoder

        connect(m, wb_arbiter.bus, wb_decoder.bus)

        # CPU

        m.submodules.cpu = cpu = Minerva(reset_address=self.bios_start)

        wb_arbiter.add(cpu.ibus)
        wb_arbiter.add(cpu.dbus)

        # SPI flash

        qspi = QSPIController(self.ports.qspi)
        spiflash = WishboneQSPIFlashController(addr_width=24, data_width=32)
        m.submodules.qspi = qspi
        m.submodules.spiflash = spiflash

        wb_decoder.add(spiflash.wb_bus, name="spiflash", addr=self.mem_spiflash_base)

        connect(m, spiflash.spi_bus, qspi)

        # SRAM

        m.submodules.sram = sram = WishboneSRAM(size=self.sram_size, data_width=32, granularity=8)
        wb_decoder.add(sram.wb_bus, name="sram", addr=self.mem_sram_base)

        # UART

        uart_divisor = int(48e6 // 115200)
        m.submodules.uart = uart = UARTPeripheral(ports=self.ports.uart, init_divisor=uart_divisor)
        csr_decoder.add(uart.csr_bus, name="uart", addr=self.csr_uart_base - self.csr_base)

        # Wishbone-CSR bridge

        m.submodules.wb_to_csr = wb_to_csr = WishboneCSRBridge(csr_decoder.bus, data_width=32)
        wb_decoder.add(wb_to_csr.wb_bus, name="csr", addr=self.csr_base, sparse=False)

        return m
