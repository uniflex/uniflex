import logging
import time
import sys
import datetime
import uuid
from apscheduler.schedulers.background import BackgroundScheduler

import wishful_framework as msgs
from transport_channel import TransportChannel, get_ip_address
from controller_monitor import ControllerMonitor
from module_manager import ModuleManager

from rule_manager import *

__author__ = "Piotr Gawlowicz, Mikolaj Chwalisz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz, chwalisz}@tkn.tu-berlin.de"


class Agent(object):
    def __init__(self, local=False):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.local = local
        self.config = None
        self.uuid = str(uuid.uuid4())
        self.name = None
        self.info = None
        self.iface = None
        self.ip = None

        apscheduler_logger = logging.getLogger('apscheduler')
        apscheduler_logger.setLevel(logging.CRITICAL)
        self.jobScheduler = BackgroundScheduler()
        self.jobScheduler.start()

        self.moduleManager = ModuleManager(self)

        if not self.local:
            self.controllerMonitor = ControllerMonitor(self)

            self.transport = TransportChannel(self)
            self.transport.set_recv_callback(self.process_msgs)
        else:
            self.local_controller = self.add_module("local_control",
                                                    'wishful_module_local_control', 
                                                    'LocalControlModule')
            self.local_controller.set_agent(self)

        self.ruleManager = RuleManager(self)

    def get_local_controller(self):
        assert self.local_controller, "Start agent in local mode"
        return self.local_controller

    def set_agent_info(self, name=None, info=None, iface=None, ip=None):
        self.name = name
        self.info = info
        self.iface = iface
        self.ip = ip

        if self.ip == None and self.iface:
            self.ip = get_ip_address(self.iface)

    def add_module(self, moduleName, pyModule, className, interfaces=None, kwargs={}):
        return self.moduleManager.add_module(moduleName, pyModule, className, interfaces, kwargs)


    def load_config(self, config):
        self.log.debug("Config: {0}".format(config))
        
        agent_info = config['agent_info']

        if 'name' in agent_info:
            self.name = agent_info['name']

        if 'info' in agent_info:
            self.info = agent_info['info']    

        if 'iface' in agent_info:
            self.iface = agent_info['iface']
            self.ip = get_ip_address(self.iface)
            

        #load modules
        moduleDesc = config['modules']
        for m_name, m_params in moduleDesc.iteritems():
            
            supported_interfaces = None
            if 'interfaces' in m_params:
                supported_interfaces=m_params['interfaces']

            kwargs = {}
            if 'kwargs' in m_params:
                kwargs = m_params['kwargs']

            self.add_module(m_name, m_params['module'], m_params['class_name'], supported_interfaces, kwargs)


    #TODO: put it in new module
    def serve_rule(self, msgContainer):
        ruleDesc = msgs.RuleDesc()
        ruleDesc.ParseFromString(msgContainer[2])
        ruleId = self.ruleManager.add_rule(ruleDesc)
        #TODO: return some rule ID to controller, so it is able to remove it


    def send_upstream(self, msgContainer):
        if not self.local:
            self.transport.send_to_controller(msgContainer)
        else:
            self.local_controller.recv_cmd_response(msgContainer)


    def process_cmd(self, msgContainer):
        dest = msgContainer[0]
        cmdDesc = msgContainer[1]
        msg = msgContainer[2]

        self.log.debug("Agent serves command: {}:{} from controller".format(cmdDesc.type, cmdDesc.func_name))
        if not cmdDesc.exec_time or cmdDesc.exec_time == 0:
            self.log.debug("Agent sends message: {}:{} to module".format(cmdDesc.type, cmdDesc.func_name))
            self.moduleManager.send_cmd_to_module(msgContainer)
        else:
            execTime = datetime.datetime.strptime(cmdDesc.exec_time, "%Y-%m-%d %H:%M:%S.%f")
            self.log.debug("Agent schedule task for message: {}:{} at {}".format(cmdDesc.type, cmdDesc.func_name, execTime))
            self.jobScheduler.add_job(self.moduleManager.send_cmd_to_module, 'date', run_date=execTime, kwargs={'msgContainer' : msgContainer})


    def process_msgs(self, msgContainer):
        dest = msgContainer[0]
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
            self.process_cmd(msgContainer)


    def run(self):
        self.log.debug("Agent starting".format())
        #nofity START to modules
        self.moduleManager.start()
        if not self.local:
            self.controllerMonitor.start()
            self.transport.start()


    def stop(self):
        self.log.debug("Stop all modules")
        #nofity EXIT to modules
        self.moduleManager.exit()
        self.jobScheduler.shutdown()
        if not self.local:
            self.controllerMonitor.stop()
            self.transport.stop()