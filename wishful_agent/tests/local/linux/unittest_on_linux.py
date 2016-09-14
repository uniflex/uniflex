#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import sys
import datetime
import logging
import wishful_agent
import time
import yaml
import wishful_upis as upis
from wishful_framework import TimeEvent, PktEvent, MovAvgFilter, PeakDetector, Match, Action, Permanance, PktMatch, FieldSelector

"""
Unittest using local controller framework.
"""

class LocalTestCaseLinux(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        self.log = logging.getLogger('wishful_agent.main')
        self.log.info('Unittest started.')
        self.agent = wishful_agent.Agent(local=True)
        self.controller = self.agent.get_local_controller()

        log_level = logging.INFO
        logging.basicConfig(level=log_level,
            format='%(asctime)s - %(name)s.%(funcName)s() - %(levelname)s - %(message)s')

        config_file_path = './unittest_on_linux_config.yaml'
        config = None
        with open(config_file_path, 'r') as f:
            config = yaml.load(f)

        self.agent.load_config(config)
        self.agent.run()


    @classmethod
    def tearDownClass(self):
        self.agent.stop()
        self.log.info('Unittest stopped.')


    def test_get_hw_addr(self):

        iface = 'lo'
        hw_addr = self.controller.blocking(True).net.get_iface_hw_addr(iface)
        self.log.info('Hw address of {} is {}'.format(iface, str(hw_addr)))

        self.assertEqual(str(hw_addr), '00:00:00:00:00:00')


    def test_get_iface_ip_addr(self):

        iface = 'lo'
        hw_addr = self.controller.blocking(True).net.get_iface_ip_addr(iface)
        self.log.info('IP address of %s is %s' % (iface, hw_addr))

        self.assertEqual(str(hw_addr), '127.0.0.1')

if __name__ == '__main__':

    unittest.main()


