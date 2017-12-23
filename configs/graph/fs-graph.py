# Copyright (c) 2010-2013, 2016 ARM Limited
# All rights reserved.
#


import optparse
import sys

import m5
from m5.defines import buildEnv
from m5.objects import *
from m5.util import addToPath, fatal

addToPath('../')

from ruby import Ruby

from common.FSConfig import *
from common.SysPaths import *
from common.Benchmarks import *
from common import Simulation
from common import CacheConfig
from common import MemConfig
from common import CpuConfig
from common.Caches import *
from common import Options

def build_test_system(np):

    test_sys = makeLinuxX86System(test_mem_mode, options.num_cpus, bm[0],
                                  options.ruby, cmdline=None)

    # Set the cache line size for the entire system
    test_sys.cache_line_size = options.cacheline_size

    # Create a top-level voltage domain
    test_sys.voltage_domain = VoltageDomain(voltage=options.sys_voltage)

    # Create a source clock for the system and set the clock period
    test_sys.clk_domain = SrcClockDomain(clock=options.sys_clock,
                                         voltage_domain=test_sys.voltage_domain)

    # Create a CPU voltage domain
    test_sys.cpu_voltage_domain = VoltageDomain()

    # Create a source clock for the CPUs and set the clock period
    test_sys.cpu_clk_domain = SrcClockDomain(clock=options.cpu_clock,
                                             voltage_domain=test_sys.cpu_voltage_domain)

    if options.kernel is not None:
        test_sys.kernel = binary(options.kernel)

    if options.script is not None:
        test_sys.readfile = options.script

    if options.lpae:
        test_sys.have_lpae = True

    if options.virtualisation:
        test_sys.have_virtualization = True

    test_sys.init_param = options.init_param

    # For now, assign all the CPUs to the same clock domain
    test_sys.cpu = [TestCPUClass(clk_domain=test_sys.cpu_clk_domain, cpu_id=i)
                    for i in xrange(np)]

    if options.caches or options.l2cache:
        # By default the IOCache runs at the system clock
        test_sys.iocache = IOCache(addr_ranges=test_sys.mem_ranges)
        test_sys.iocache.cpu_side = test_sys.iobus.master
        test_sys.iocache.mem_side = test_sys.membus.slave
    elif not options.external_memory_system:
        test_sys.iobridge = Bridge(
            delay='50ns', ranges=test_sys.mem_ranges)
        test_sys.iobridge.slave = test_sys.iobus.master
        test_sys.iobridge.master = test_sys.membus.slave

    # Sanity check
    if options.fastmem:
        if TestCPUClass != AtomicSimpleCPU:
            fatal("Fastmem can only be used with atomic CPU!")
        if (options.caches or options.l2cache):
            fatal("You cannot use fastmem in combination with caches!")

    if options.simpoint_profile:
        if not options.fastmem:
            # Atomic CPU checked with fastmem option already
            fatal("SimPoint generation should be done with atomic cpu and fastmem")
        if np > 1:
            fatal("SimPoint generation not supported with more than one CPUs")

    for i in xrange(np):
        if options.fastmem:
            test_sys.cpu[i].fastmem = True
        if options.simpoint_profile:
            test_sys.cpu[i].addSimPointProbe(options.simpoint_interval)
        if options.checker:
            test_sys.cpu[i].addCheckerCpu()
        test_sys.cpu[i].createThreads()

    if options.elastic_trace_en and options.checkpoint_restore == None and \
            not options.fast_forward:
        CpuConfig.config_etrace(TestCPUClass, test_sys.cpu, options)

    CacheConfig.config_cache(options, test_sys)

    MemConfig.config_mem(options, test_sys)

    return test_sys

# *************************** Main Starts Here ********************************

# Add options
parser = optparse.OptionParser()
Options.addCommonOptions(parser)
Options.addFSOptions(parser)

(options, args) = parser.parse_args()

if args:
    print "Error: script doesn't take any positional arguments"
    sys.exit(1)

# system under test can be any CPU
(TestCPUClass, test_mem_mode, FutureClass) = Simulation.setCPUClass(options)

# Match the memories with the CPUs, based on the options for the test system
TestMemClass = Simulation.setMemClass(options)


# print 'DEBUG:', options.disk_image, options.root_device, \
#     options.mem_size, options.os_type

bm = [SysConfig(disk=options.disk_image, rootdev=options.root_device,
                mem=options.mem_size, os_type=options.os_type)]

np = options.num_cpus

test_sys = build_test_system(np)

root = Root(full_system=True, system=test_sys)

Simulation.setWorkCountOptions(test_sys, options)
Simulation.run(options, root, test_sys, FutureClass)
