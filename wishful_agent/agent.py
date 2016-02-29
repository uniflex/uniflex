import logging
import time
import sys
import yaml
from agent_module import *
from rule_manager import *
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import uuid

import socket
import fcntl
import struct

import wishful_framework as msgs
from transport_channel import TransportChannel
from controller_monitor import ControllerMonitor
from module_manager import ModuleManager

__author__ = "Piotr Gawlowicz, Mikolaj Chwalisz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz, chwalisz}@tkn.tu-berlin.de"


def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])


class Agent(object):
    def __init__(self, controller):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.log.debug("Controller: {0}".format(controller))
        self.config = None
        self.uuid = str(uuid.uuid4())
        self.agent_info = {}
        self.ip = None

        apscheduler_logger = logging.getLogger('apscheduler')
        apscheduler_logger.setLevel(logging.CRITICAL)
        self.jobScheduler = BackgroundScheduler()
        self.jobScheduler.start()

        self.moduleManager = ModuleManager(self)
        self.controllerMonitor = ControllerMonitor(self)

        self.transport = TransportChannel(self)
        self.transport.set_recv_callback(self.process_msgs)

        self.ruleManager = RuleManager(self)


    def read_config_file(self, path=None):
        self.log.debug("Path to module: {0}".format(path))

        with open(path, 'r') as f:
           config = yaml.load(f)

        return config


    def add_module(self, moduleName, pyModule, className, interfaces):
        self.moduleManager.add_module(moduleName, pyModule, className, interfaces)


    def load_modules(self, config):
        self.log.debug("Config: {0}".format(config))
        self.agent_info = config['agent_info']
        if 'ip' in self.agent_info:
            self.ip = self.agent_info['ip']
        else:
            self.ip = get_ip_address(self.agent_info['iface'])

        #load modules
        moduleDesc = config['modules']
        for m_name, m_params in moduleDesc.iteritems():
            
            supported_interfaces = None
            if 'interfaces' in m_params:
                supported_interfaces=m_params['interfaces'] 

            self.add_module(m_name, m_params['module'], m_params['class_name'], supported_interfaces)


    #TODO: put it in new module
    def serve_rule(self, msgContainer):
        ruleDesc = msgs.RuleDesc()
        ruleDesc.ParseFromString(msgContainer[2])
        ruleId = self.ruleManager.add_rule(ruleDesc)
        #TODO: return some rule ID to controller, so it is able to remove it


    def send_to_controller(self, msgContainer):
        self.transport.send_to_controller(msgContainer)


    def process_msgs(self, msgContainer):
        group = msgContainer[0]
        cmdDesc = msgContainer[1]
        msg = msgContainer[2]          
        self.log.debug("Agent received message: {} from controller".format(cmdDesc.type))

        if cmdDesc.type == msgs.get_msg_type(msgs.NewNodeAck):
            self.controllerMonitor.setup_connection_to_controller_complete(msgContainer)
        elif cmdDesc.type == msgs.get_msg_type(msgs.HelloMsg):
            self.controllerMonitor.serve_hello_msg(msgContainer)
        elif cmdDesc.type == msgs.get_msg_type(msgs.RuleDesc):
            self.serve_rule(msgContainer)
        else:
            self.log.debug("Agent serves command: {}:{} from controller".format(cmdDesc.type, cmdDesc.func_name))
            if not cmdDesc.exec_time or cmdDesc.exec_time == 0:
                self.log.debug("Agent sends message: {}:{} to module".format(cmdDesc.type, cmdDesc.func_name))
                self.moduleManager.send_cmd_to_module(msgContainer)
            else:
                execTime = datetime.datetime.strptime(cmdDesc.exec_time, "%Y-%m-%d %H:%M:%S.%f")
                self.log.debug("Agent schedule task for message: {}:{} at {}".format(cmdDesc.type, cmdDesc.func_name, execTime))
                self.jobScheduler.add_job(self.moduleManager.send_cmd_to_module, 'date', run_date=execTime, kwargs={'msgContainer' : msgContainer})


    def run(self):
        self.log.debug("Agent starting".format())

        try:
            #nofity START to modules
            self.moduleManager.start()
            self.controllerMonitor.start()
            self.transport.start()

        except KeyboardInterrupt:
            self.log.debug("Agent exits")

        finally:
            self.log.debug("Stop all modules")
            #nofity EXIT to modules
            self.moduleManager.exit()

            self.jobScheduler.shutdown()
            self.controllerMonitor.stop()
            self.transport.stop()