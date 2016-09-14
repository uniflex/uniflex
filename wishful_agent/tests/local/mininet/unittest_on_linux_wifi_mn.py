#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Wishful IEEE 802.11 test example consisting of single APs and two STAs. The AP is controlled by an
local Wishful controller.
"""

import time
from mininet.net import Mininet
from mininet.node import Controller,OVSKernelSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

from wishful_mininet import WishfulNode, WishfulAgent, WishfulController

__author__ = "Zubow"
__copyright__ = "Copyright (c) 2016, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{zubow}@tkn.tu-berlin.de"

# enable mininet cli
MN_CLI = False
# enable GUI
GUI = False
# enable mobility
MOBILITY = False

'''
Simple topology with AP and STA.

sudo python ./test_wifi_mn.py
'''
def topology():

    "Create a network."
    net = Mininet( controller=Controller, link=TCLink, switch=OVSKernelSwitch )

    print("*** Creating nodes")
    sta1 = net.addStation( 'sta1', mac='00:00:00:00:00:02', ip='10.0.0.2/8' )
    sta2 = net.addStation( 'sta2', mac='00:00:00:00:00:03', ip='10.0.0.3/8' )
    ap1 = net.addBaseStation( 'ap1', ssid= 'new-ssid1', mode= 'g', channel= '1', position='15,50,0' )
    c1 = net.addController( 'c1', controller=Controller )

    print("*** Creating links")
    net.addLink(ap1, sta1)
    net.addLink(ap1, sta2)

    print("*** Starting network")
    net.build()
    c1.start()
    ap1.start( [c1] )

    "Configure IP addresses on APs for binding Wishful agent"
    ap1.cmd('ifconfig ap1-eth1 20.0.0.2/8')
    "Setup monitor interface ..."
    ap1.cmd('./cfg_mon.sh')
    ap1.cmd('ifconfig mon0 up')

    print("*** Starting Wishful framework")
    folder = './'

    print("*** local controller ...")
    wf_ctrl = WishfulController(ap1, folder + 'unittest_on_linux_wifi_wishful_local_controller', folder + 'unittest_on_linux_wifi_config.yaml')
    wf_ctrl.start()

    print("*** Starting network")
    sta1.cmd('ping -c10 %s' % sta2.IP())

    print("*** Check that Wishful agents/controllers are still running ...")
    if not wf_ctrl.check_is_running():
        print('*****')
        print(wf_ctrl.read_log_file())
        print('*****')

        raise Exception("Error; wishful controller not running; check logfile: " + wf_ctrl.logfile)

    else:
        print("*** Wishful agents/controllers: OK")

    if MN_CLI:
        print("*** Running CLI")
        CLI( net )

    print("*** Stopping network")
    wf_ctrl.stop()
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    topology()
