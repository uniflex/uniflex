import logging
import time
import sys
import yaml
from agent_module import *
from rule_manager import *
import zmq
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import uuid
import socket
import fcntl
import struct
import threading

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

        self.discoveryThread = None
        self.connectedToController = False
        self.controllerDL = None
        self.controllerUL = None

        self.echoMsgInterval = 3
        self.echoTimeOut = 10
        self.echoSendJob = None
        self.connectionLostJob = None

        self.ruleManager = RuleManager(self)


        #self.transport = TransportChannel(ul, dl)
        self.poller = zmq.Poller()
        self.context = zmq.Context()
        self.socket_sub = self.context.socket(zmq.SUB) # for downlink communication with controller
        self.socket_sub.setsockopt(zmq.SUBSCRIBE,  self.uuid)
        self.socket_sub.setsockopt(zmq.LINGER, 100)
        self.socket_pub = self.context.socket(zmq.PUB) # for uplink communication with controller

        #register module socket in poller
        self.poller.register(self.socket_sub, zmq.POLLIN)


    def read_config_file(self, path=None):
        self.log.debug("Path to module: {0}".format(path))

        with open(path, 'r') as f:
           config = yaml.load(f)

        return config

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

            self.moduleManager.add_module(m_name, m_params['module'], m_params['class_name'], supported_interfaces)


    def serve_rule(self, msgContainer):
        ruleDesc = msgs.RuleDesc()
        ruleDesc.ParseFromString(msgContainer[2])
        ruleId = self.ruleManager.add_rule(ruleDesc)
        #TODO: return some rule ID to controller, so it is able to remove it


    def send_msg_to_controller(self, msgContainer):
        ## stamp with my uuid
        cmdDesc = msgs.CmdDesc()
        cmdDesc.ParseFromString(msgContainer[1])
        cmdDesc.caller_id = self.uuid
        msgContainer[1] = cmdDesc.SerializeToString()
        self.socket_pub.send_multipart(msgContainer)

    def setup_connection_to_controller(self, dlink, uplink):

        if self.connectedToController:
            self.log.debug("Agent already connected to controller".format())
            return

        self.log.debug("Agent connects controller: DL-{}, UL-{}".format(dlink, uplink))

        if self.controllerDL and self.controllerUL:
            try:
                self.socket_pub.disconnect(self.controllerDL)
                self.socket_sub.disconnect(self.controllerUL)
            except:
                pass

        self.controllerDL = dlink
        self.controllerUL = uplink
        self.socket_pub.connect(self.controllerDL)
        self.socket_sub.connect(self.controllerUL)

        group = "NEW_NODE"
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.NewNodeMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.NewNodeMsg)
        msg = msgs.NewNodeMsg()
        msg.agent_uuid =  self.uuid
        msg.ip = self.ip
        msg.name = self.agent_info['name']
        msg.info = self.agent_info['info']
        
        for mid, module in self.moduleManager.modules.iteritems():
            moduleMsg = msg.modules.add()
            moduleMsg.id = mid
            moduleMsg.name = module.name
            for f in module.get_capabilities():
                function = moduleMsg.functions.add()
                function.name = f

        for ifaceId, modules in self.moduleManager.iface_to_module_mapping.iteritems():              
            iface = msg.interfaces.add()
            iface.id = int(ifaceId)
            iface.name = self.moduleManager.interfaces[ifaceId]
            for module in modules:
                imodule = iface.modules.add()
                imodule.id = module.id
                imodule.name = module.name

        msgContainer = [group, cmdDesc.SerializeToString(), msg.SerializeToString()]

        self.log.debug("Agent sends context-setup request to controller")
        time.sleep(1) # TODO: are we waiting for connection?
        self.send_msg_to_controller(msgContainer)

    def setup_connection_to_controller_complete(self, msgContainer):
        cmdDesc = msgs.CmdDesc()
        cmdDesc.ParseFromString(msgContainer[1])
        msg = msgs.NewNodeAck()
        msg.ParseFromString(msgContainer[2])

        self.log.debug("Controller received msgType: {} with status: {}".format(cmdDesc.type, msg.status))

        self.log.debug("Agent connects to controller and subscribes to received topics")
        self.socket_sub.setsockopt(zmq.SUBSCRIBE,  self.uuid)
        for topic in msg.topics:
            self.log.debug("Agent subscribes to topic: {}".format(topic))
            self.socket_sub.setsockopt(zmq.SUBSCRIBE, str(topic))

        #stop discovery module:
        self.connectedToController = True

        #start sending hello msgs
        execTime =  str(datetime.datetime.now() + datetime.timedelta(seconds=self.echoMsgInterval))
        self.log.debug("Agent schedule sending of Hello message".format())
        self.echoSendJob = self.jobScheduler.add_job(self.send_hello_msg_to_controller, 'date', run_date=execTime)

        execTime = datetime.datetime.now() + datetime.timedelta(seconds=self.echoTimeOut)
        self.connectionLostJob = self.jobScheduler.add_job(self.connection_to_controller_lost, 'date', run_date=execTime)

    def send_hello_msg_to_controller(self):
        self.log.debug("Agent sends HelloMsg to controller")
        group = self.uuid
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.HelloMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.HelloMsg)
        msg = msgs.HelloMsg()
        msg.uuid = str(self.uuid)
        msg.timeout = 3 * self.echoMsgInterval
        msgContainer = [group, cmdDesc.SerializeToString(), msg.SerializeToString()]
        self.send_msg_to_controller(msgContainer)

        #reschedule hello msg
        self.log.debug("Agent schedule sending of Hello message".format())
        execTime =  datetime.datetime.now() + datetime.timedelta(seconds=self.echoMsgInterval)
        self.echoSendJob = self.jobScheduler.add_job(self.send_hello_msg_to_controller, 'date', run_date=execTime)


    def connection_to_controller_lost(self):
        self.log.debug("Agent lost connection with controller, stop sending EchoMsg".format())
        self.echoSendJob.remove()

        #disconnect
        if self.controllerDL and self.controllerUL:
            try:
                self.socket_pub.disconnect(self.controllerDL)
                self.socket_sub.disconnect(self.controllerUL)
            except:
                pass

        self.connectedToController = False

        self.log.debug("Agent restarts discovery procedure".format())
        self.start_discovery_procedure()

    def serve_hello_msg(self, msgContainer):
        self.log.debug("Agent received HELLO MESSAGE from controller".format())
        self.connectionLostJob.remove()
        execTime = datetime.datetime.now() + datetime.timedelta(seconds=self.echoTimeOut)
        self.connectionLostJob = self.jobScheduler.add_job(self.connection_to_controller_lost, 'date', run_date=execTime)


    def terminate_connection_to_controller(self):
        self.log.debug("Agend sends NodeExitMsg to Controller".format())
        group = "NODE_EXIT"
        cmdDesc= msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.NodeExitMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.NodeExitMsg)
        msg = msgs.NodeExitMsg()
        msg.agent_uuid =  self.uuid
        msg.reason = "Process terminated"

        msgContainer = [group, cmdDesc.SerializeToString(), msg.SerializeToString()]
        self.send_msg_to_controller(msgContainer)


    def start_discovery_procedure(self):
        self.discoveryThread = threading.Thread(target=self.discover_controller)
        self.discoveryThread.setDaemon(True)
        self.discoveryThread.start()

    def discover_controller(self):
        while not self.connectedToController:
            discoveryModule = self.moduleManager.discoveryModule
            assert discoveryModule

            [dlink, uplink] = discoveryModule.get_controller()

            if dlink and uplink:
                self.setup_connection_to_controller(dlink,uplink)
            time.sleep(3)

        self.moduleManager.discoveryModule.connected()

    def process_msgs(self):
        # Work on requests from both controller and modules
        while True:
            socks = dict(self.poller.poll())
            if self.socket_sub in socks and socks[self.socket_sub] == zmq.POLLIN:
                msgContainer = self.socket_sub.recv_multipart()

                assert len(msgContainer) == 3
                group = msgContainer[0]
                cmdDesc = msgs.CmdDesc()
                cmdDesc.ParseFromString(msgContainer[1])
                msg = msgContainer[2]
                
                self.log.debug("Agent received message: {} from controller".format(cmdDesc.type))

                if cmdDesc.type == msgs.get_msg_type(msgs.NewNodeAck):
                    self.setup_connection_to_controller_complete(msgContainer)
                elif cmdDesc.type == msgs.get_msg_type(msgs.HelloMsg):
                    self.serve_hello_msg(msgContainer)
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
            self.start_discovery_procedure()
            #nofity START to modules
            self.moduleManager.start()
            self.process_msgs()

        except KeyboardInterrupt:
            self.log.debug("Agent exits")

        finally:
            self.terminate_connection_to_controller()
            self.log.debug("Exit all modules' subprocesses")
            #nofity EXIT to modules
            self.moduleManager.exit()
            self.jobScheduler.shutdown()
            self.socket_sub.setsockopt(zmq.LINGER, 0)
            self.socket_sub.setsockopt(zmq.LINGER, 0)
            self.socket_sub.close()
            self.socket_pub.close()
            self.context.term()