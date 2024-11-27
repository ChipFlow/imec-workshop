from amaranth import *
from amaranth.lib import io, wiring
from amaranth.lib.wiring import In, Out, flipped, connect

from amaranth_soc import csr

from .phy import UARTPhy


__all__ = ["UARTPeripheral"]


# TODO
