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


# TODO
