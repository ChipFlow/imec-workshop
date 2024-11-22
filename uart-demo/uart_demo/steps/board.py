from amaranth import *

from doit.cmd_base import ModuleTaskLoader
from doit.doit_cmd import DoitMain

from chipflow_lib.steps.board import BoardStep

from glasgow.platform.generic import GlasgowPlatformPort
from glasgow.platform.rev_c import GlasgowRevC123Platform
from glasgow.target.hardware import GlasgowBuildPlan
from glasgow.target.toolchain import find_toolchain

from ..uart import LoopbackUART
from ..board import doit_glasgow
from ..ports import PortGroup


__all__ = ["GlasgowBoardStep"]


class _GlasgowTop(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        a_ports = [platform.request("port_a", n, dir={"io": "-", "oe": "-"}) for n in range(8)]
        b_ports = [platform.request("port_b", n, dir={"io": "-", "oe": "-"}) for n in range(8)]

        ports = PortGroup()
        ports.rx = GlasgowPlatformPort(io=a_ports[0].io, oe=a_ports[0].oe)
        ports.tx = GlasgowPlatformPort(io=a_ports[1].io, oe=a_ports[1].oe)

        m.submodules.uart = uart = LoopbackUART(ports, clk_freq=48e6, baudrate=115200)

        return m


class GlasgowBoardStep(BoardStep):
    def __init__(self, config):
        platform = GlasgowRevC123Platform()
        super().__init__(config, platform)

    def build_cli_parser(self, parser):
        action_argument = parser.add_subparsers(dest="action")
        build_subparser = action_argument.add_parser(
            "build-bitstream", help="Build the FPGA bitstream.")
        bitstream_subparser = action_argument.add_parser(
            "load-bitstream", help="Load the FPGA bitstream to the board.")
        software_subparser = action_argument.add_parser(
            "flash-software", help="Write the software to the board SPI flash.")

    def run_cli(self, args):
        if args.action == "build-bitstream":
            self.build_bitstream()
        if args.action == "load-bitstream":
            self.load_bitstream()
        if args.action == "flash-software":
            self.flash_software()

    def build_bitstream(self):
        plan = GlasgowBuildPlan(
            find_toolchain(),
            self.platform.prepare(_GlasgowTop(), nextpnr_opts="--timing-allow-fail"))
        plan.execute(build_dir="build/board", debug=True)

    def load_bitstream(self):
        DoitMain(ModuleTaskLoader(doit_glasgow)).run(["load_bitstream"])

    def flash_software(self):
        DoitMain(ModuleTaskLoader(doit_glasgow)).run(["flash_software"])