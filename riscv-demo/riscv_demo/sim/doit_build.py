import os
import sys
import importlib.resources

from doit.action import CmdAction


OUTPUT_DIR  = "./build/sim"
SOURCE_DIR  = importlib.resources.files("riscv_demo") / "sim"
RUNTIME_DIR = importlib.resources.files("yowasp_yosys") / "share/include/backends/cxxrtl/runtime"

ZIG_CXX  = f"{sys.executable} -m ziglang c++"
if os.name == "nt":
    CXXFLAGS = f"-O3 -DWIN32 -g -std=c++17 -Wno-array-bounds -Wno-shift-count-overflow -fbracket-depth=1024"
    LIBS = "-lws2_32"
else:
    CXXFLAGS = f"-O3 -g -std=c++17 -Wno-array-bounds -Wno-shift-count-overflow -fbracket-depth=1024"
    LIBS = ""
INCLUDES = f"-I {OUTPUT_DIR} -I {SOURCE_DIR}/vendor -I {RUNTIME_DIR}"


def task_build_sim_rtlil():
    return {
        "actions": [
            f"pdm run chipflow sim build-rtlil",
        ],
        "targets": [
            f"{OUTPUT_DIR}/sim_soc.ys",
            f"{OUTPUT_DIR}/sim_soc.il",
        ],
    }


def task_build_sim_cxxrtl():
    return {
        "actions": [
            f"cd {OUTPUT_DIR} && pdm run yowasp-yosys sim_soc.ys",
        ],
        "targets": [
            f"{OUTPUT_DIR}/sim_soc.cc",
            f"{OUTPUT_DIR}/sim_soc.h"
        ],
        "file_dep": [
            f"{OUTPUT_DIR}/sim_soc.ys",
            f"{OUTPUT_DIR}/sim_soc.il"
        ],
    }


def task_build_sim():
    exe = ".exe" if os.name == "nt" else ""

    return {
        "actions": [
            f"{ZIG_CXX} {CXXFLAGS} {INCLUDES} -o {OUTPUT_DIR}/sim_soc{exe} "
            f"{OUTPUT_DIR}/sim_soc.cc {SOURCE_DIR}/main.cc {SOURCE_DIR}/models.cc {LIBS}"
        ],
        "targets": [
            f"{OUTPUT_DIR}/sim_soc{exe}"
        ],
        "file_dep": [
            f"{OUTPUT_DIR}/sim_soc.cc",
            f"{OUTPUT_DIR}/sim_soc.h",
            f"{SOURCE_DIR}/main.cc",
            f"{SOURCE_DIR}/models.cc",
            f"{SOURCE_DIR}/models.h",
            f"{SOURCE_DIR}/vendor/nlohmann/json.hpp",
            f"{SOURCE_DIR}/vendor/cxxrtl/cxxrtl_server.h",
        ],
    }


def task_run_sim():
    exe = ".exe" if os.name == "nt" else ""

    return {
        "actions": [
            CmdAction(f"{'' if os.name == 'nt' else './'}sim_soc{exe}", buffering=1, cwd=OUTPUT_DIR)
        ],
        "file_dep": [
            f"{OUTPUT_DIR}/sim_soc{exe}"
        ],
    }
