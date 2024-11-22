from amaranth import *
from amaranth.lib import io, wiring
from amaranth.lib.wiring import In, Out, flipped, connect

from amaranth_soc import csr
from amaranth_stdio.serial import AsyncSerialRX, AsyncSerialTX

from .ports import PortGroup


__all__ = ["UARTPeripheral"]


# TODO
