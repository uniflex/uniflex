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

import wishful_framework as msgs

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
        self.myUuid = uuid.uuid4()
        self.myId = str(self.myUuid)
        self.agent_info = {}
        self.ip = None

        self.connectedToController = False
        self.controllerDL = None
        self.controllerUL = None

        self.echoMsgInterval = 3
        self.echoTimeOut = 10
        self.echoSendJob = None
        self.connectionLostJob = None

        apscheduler_logger = logging.getLogger('apscheduler')
        apscheduler_logger.setLevel(logging.CRITICAL)
        self.jobScheduler = BackgroundScheduler()
        self.jobScheduler.start()

        self.ruleManager = RuleManager(self)

        self.poller = zmq.Poller()
        self.context = zmq.Context()
        self.socket_sub = self.context.socket(zmq.SUB) # for downlink communication with controller
        self.socket_sub.setsockopt(zmq.SUBSCRIBE,  self.myId)
        self.socket_sub.setsockopt(zmq.LINGER, 100)
        self.socket_pub = self.context.socket(zmq.PUB) # for uplink communication with controller

        #register module socket in poller
        self.poller.register(self.socket_sub, zmq.POLLIN)

    modules = {}
    system_modules = {}

    moduleIdGen = 0
    moduleIds = {}
    ifaceIdGen = 0
    interfaces = {}
    r_interfaces = {}
    iface_to_module_mapping = {}

    def generate_new_module_id(self):
        newId = self.moduleIdGen
        self.moduleIdGen = self.moduleIdGen + 1
        return newId

    def generate_new_iface_id(self):
        newId = self.ifaceIdGen
        self.ifaceIdGen = self.ifaceIdGen + 1
        return newId

    def get_iface_id(self, name):
        for k,v in self.interfaces.iteritems():
            if v == name:
                return k

        return None

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

        #load upi modules
        inproc_modules = config['upi_modules']
        for module_name, module_parameters in inproc_modules.iteritems():
            
            supported_interfaces = ["ALL"]
            if 'interfaces' in module_parameters:
                supported_interfaces=module_parameters['interfaces'] 
            
            self.add_upi_module(
                supported_interfaces,
                AgentInProcModule(self.generate_new_module_id(), module_name, module_parameters['module'],
                                  module_parameters['class_name'],
                                  supported_interfaces))

        #load system modules
        modules = config['system_modules']
        for module_name, module_parameters in modules.iteritems():

            supported_interfaces = ["ALL"]
            if 'interfaces' in module_parameters:
                supported_interfaces=module_parameters['interfaces'] 

            self.add_system_module(
                module_name,
                AgentModule(self.generate_new_module_id(), module_name, module_parameters['path'], 
                            module_parameters['args'], supported_interfaces))



    def add_upi_module(self, interfaces, module):
        self.log.debug("Adding new inproc module: {0}".format(module))
        
        capabilities = module.module.get_capabilities()
        module.capabilities = capabilities
        self.modules[module.name] = module
        self.moduleIds[module.id] = module

        for iface in interfaces:
            if iface not in self.interfaces.values():
                iface_id = self.generate_new_iface_id()
                self.interfaces[iface_id] = str(iface)

                if not iface_id in self.iface_to_module_mapping:
                    self.iface_to_module_mapping[iface_id] = [module]
                else:
                    self.iface_to_module_mapping[iface_id].append(module)


    def add_system_module(self, name, module):
        self.log.debug("Adding new module: {0}".format(module))
        self.modules[module.name] = module
        self.system_modules[name] = module

        #register module socket in poller
        self.poller.register(module.socket, zmq.POLLIN)
        pass

    def send_msg_to_controller(self, msgContainer):
        ## stamp with my uuid
        cmdDesc = msgs.CmdDesc()
        cmdDesc.ParseFromString(msgContainer[1])
        cmdDesc.caller_id = self.myId
        msgContainer[1] = cmdDesc.SerializeToString()
        self.socket_pub.send_multipart(msgContainer)

    def send_cmd_to_system_module(self, name, msgContainer):
        self.system_modules[name].send_msg_to_module(msgContainer)

    def send_cmd_to_upi_module(self, msgContainer):
        cmdDesc = msgs.CmdDesc()
        cmdDesc.ParseFromString(msgContainer[1])

        iface = "ALL"
        if cmdDesc.HasField('interface'):
            iface = cmdDesc.interface
        
        #find UPI module
        ifaceId = self.get_iface_id(str(iface))
        modules = self.iface_to_module_mapping[ifaceId]

        functionFound = False
        for module in modules:
            if cmdDesc.func_name in module.capabilities:
                functionFound = True
                retVal = module.send_msg_to_module(msgContainer)
                if retVal:
                    self.send_msg_to_controller(retVal)
                break
        
        if not functionFound:
            print "function not supported EXCEPTION", cmdDesc.func_name, cmdDesc.interface


    def serve_rule(self, msgContainer):
        ruleDesc = msgs.RuleDesc()
        ruleDesc.ParseFromString(msgContainer[2])
        ruleId = self.ruleManager.add_rule(ruleDesc)
        #TODO: return some rule ID to controller, so it is able to remove it


    def setup_connection_to_controller(self, msgContainer):
        cmdDesc= msgs.CmdDesc()
        cmdDesc.ParseFromString(msgContainer[1])
        msg = msgs.ControllerDiscoveredMsg()
        msg.ParseFromString(msgContainer[2])

        if self.connectedToController:
            self.log.debug("Agent already connected to controller, message {} discarded".format(cmdDesc.type))
            return

        self.log.debug("Agent connects controller: DL:{}, UL:{}".format(msg.down_link, msg.up_link))

        if self.controllerDL and self.controllerUL:
            try:
                self.socket_pub.disconnect(self.controllerDL)
                self.socket_sub.disconnect(self.controllerUL)
            except:
                pass

        self.controllerDL = msg.down_link
        self.controllerUL = msg.up_link
        self.socket_pub.connect(msg.down_link)
        self.socket_sub.connect(msg.up_link)

        group = "NEW_NODE"
        cmdDesc.Clear()
        cmdDesc.type = msgs.get_msg_type(msgs.NewNodeMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.NewNodeMsg)
        msg = msgs.NewNodeMsg()
        msg.agent_uuid =  self.myId
        msg.ip = self.ip
        msg.name = self.agent_info['name']
        msg.info = self.agent_info['info']
        
        for mid, module in self.moduleIds.iteritems():
            moduleMsg = msg.modules.add()
            moduleMsg.id = mid
            moduleMsg.name = module.name
            for f in module.capabilities:
                function = moduleMsg.functions.add()
                function.name = f

        for ifaceId, modules in self.iface_to_module_mapping.iteritems():
            if self.interfaces[ifaceId] == "ALL":
                continue
                
            iface = msg.interfaces.add()
            iface.id = int(ifaceId)
            iface.name = self.interfaces[ifaceId]
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
        self.socket_sub.setsockopt(zmq.SUBSCRIBE,  self.myId)
        for topic in msg.topics:
            self.log.debug("Agent subscribes to topic: {}".format(topic))
            self.socket_sub.setsockopt(zmq.SUBSCRIBE, str(topic))

        self.connectedToController = True

        #stop discovery module:
        self.log.debug("Agent stops discovery module")
        group = "LOCAL"
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.DiscoverySuccessMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.DiscoverySuccessMsg)
        msg = msgs.DiscoverySuccessMsg()
        msg.status = True
        msgContainer = [group, cmdDesc.SerializeToString(), msg.SerializeToString()]
        self.send_cmd_to_system_module("discovery", msgContainer)

        #start sending hello msgs
        execTime =  str(datetime.datetime.now() + datetime.timedelta(seconds=self.echoMsgInterval))
        self.log.debug("Agent schedule sending of Hello message".format())
        self.echoSendJob = self.jobScheduler.add_job(self.send_hello_msg_to_controller, 'date', run_date=execTime)

        execTime = datetime.datetime.now() + datetime.timedelta(seconds=self.echoTimeOut)
        self.connectionLostJob = self.jobScheduler.add_job(self.connection_to_controller_lost, 'date', run_date=execTime)

    def send_hello_msg_to_controller(self):
        self.log.debug("Agent sends HelloMsg to controller")
        group = self.myId
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.HelloMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.HelloMsg)
        msg = msgs.HelloMsg()
        msg.uuid = str(self.myId)
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
        group = "LOCAL"
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.DiscoveryRestartMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.DiscoveryRestartMsg)
        msg = msgs.DiscoveryRestartMsg()
        msg.reason = "CONTROLLER_LOST"
        msgContainer = [group, cmdDesc.SerializeToString(), msg.SerializeToString()]
        self.send_cmd_to_system_module("discovery", msgContainer)

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
        msg.agent_uuid =  self.myId
        msg.reason = "Process terminated"

        msgContainer = [group, cmdDesc.SerializeToString(), msg.SerializeToString()]
        self.send_msg_to_controller(msgContainer)

    def process_msgs(self):
        # Work on requests from both controller and modules
        while True:
            socks = dict(self.poller.poll())

            for name, module in self.modules.iteritems():
                if module.socket in socks and socks[module.socket] == zmq.POLLIN:
                    msgContainer = module.socket.recv_multipart()

                    assert len(msgContainer) == 3
                    group = msgContainer[0]
                    cmdDesc = msgs.CmdDesc()
                    cmdDesc.ParseFromString(msgContainer[1])
                    msg = msgContainer[2]

                    if not group:
                        self.log.debug("Field group not set -> stamp with my UUID".format())
                        msgContainer[0] = self.myId

                    self.log.debug("Agent received message of type: {}:{} from module: {}".format(cmdDesc.type, cmdDesc.func_name, name))

                    if cmdDesc.type == msgs.get_msg_type(msgs.ControllerDiscoveredMsg):
                        self.log.debug("Agent {} discovered controller".format(name))
                        self.setup_connection_to_controller(msgContainer)
                    elif self.connectedToController:
                        self.log.debug("Agent sends message to Controller: {}:{}".format(cmdDesc.type, cmdDesc.func_name))
                        self.send_msg_to_controller(msgContainer)
                    else:
                        self.log.debug("Agent drops message: {}:{} from one of modules".format(cmdDesc.type, cmdDesc.func_name))

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
                        self.send_cmd_to_upi_module(msgContainer)
                    else:
                        execTime = datetime.datetime.strptime(cmdDesc.exec_time, "%Y-%m-%d %H:%M:%S.%f")
                        self.log.debug("Agent schedule task for message: {}:{} at {}".format(cmdDesc.type, cmdDesc.func_name, execTime))
                        self.jobScheduler.add_job(self.send_cmd_to_upi_module, 'date', run_date=execTime, kwargs={'msgContainer' : msgContainer})


    def run(self):
        self.log.debug("Agent starting".format())

        try:
            self.process_msgs()

        except KeyboardInterrupt:
            self.log.debug("Agent exits")

        finally:
            self.terminate_connection_to_controller()
            self.log.debug("Exit all modules' subprocesses")
            for name, module in self.modules.iteritems():
                module.exit()
            self.jobScheduler.shutdown()
            self.socket_sub.setsockopt(zmq.LINGER, 0)
            self.socket_sub.setsockopt(zmq.LINGER, 0)
            self.socket_sub.close()
            self.socket_pub.close()
            self.context.term()