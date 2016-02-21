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

import wishful_framework as msgs

__author__ = "Piotr Gawlowicz, Mikolaj Chwalisz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz, chwalisz}@tkn.tu-berlin.de"


class Agent(object):
    def __init__(self, controller):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.log.debug("Controller: {0}".format(controller))
        self.config = None
        self.myUuid = uuid.uuid4()
        self.myId = str(self.myUuid)
        self.agent_info = {}

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
    module_groups = {}

    def read_config_file(self, path=None):
        self.log.debug("Path to module: {0}".format(path))

        with open(path, 'r') as f:
           config = yaml.load(f)

        return config

    def load_modules(self, config):
        self.log.debug("Config: {0}".format(config))
        self.agent_info = config['agent_info']

        #in process modules
        inproc_modules = config['inproc_modules']
        for module_name, module_parameters in inproc_modules.iteritems():
            
            supported_interfaces = "ALL"
            if 'interfaces' in module_parameters:
                supported_interfaces=module_parameters['interfaces'] 
            
            self.add_inproc_module(
                module_parameters['message_type'],
                AgentInProcModule(module_name, module_parameters['module'],
                                  module_parameters['class_name'],
                                  supported_interfaces))

        #self process modules
        modules = config['modules']
        for module_name, module_parameters in modules.iteritems():
            
            supported_interfaces = "ALL"
            if 'interfaces' in module_parameters:
                supported_interfaces=module_parameters['interfaces'] 
            
            self.add_module(
                module_parameters['message_type'],
                AgentModule(module_name, module_parameters['path'], 
                            module_parameters['args'], supported_interfaces))


    def add_inproc_module(self, message_types, module):
        self.log.debug("Adding new inproc module: {0}".format(module))
        self.modules[module.name] = module

        print "Module capabilities: ", module.module.get_capabilities()
        print ""
        for message_type in message_types:
            if message_type in self.module_groups.keys():
                self.module_groups[message_type].append(module.name)
            else:
                self.module_groups[message_type] = [module.name]

    def add_module(self, message_types, module):
        self.log.debug("Adding new module: {0}".format(module))
        self.modules[module.name] = module

        #TODO: discover UPI functions suported by module, get it from module
        for message_type in message_types:
            if message_type in self.module_groups.keys():
                self.module_groups[message_type].append(module.name)
            else:
                self.module_groups[message_type] = [module.name]

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

    def send_msg_to_module(self, module_name, msgContainer):
        return self.modules[module_name].send_msg_to_module(msgContainer)

    def get_module_name_by_type(self, msg_type):
        return self.module_groups[str(msg_type)]
 
    def send_msg_to_module_group(self, msgContainer):
        cmdDesc = msgs.CmdDesc()
        cmdDesc.ParseFromString(msgContainer[1])

        module_name_list = self.module_groups[str(cmdDesc.type)]
        for module_name in module_name_list:
            retVal = self.send_msg_to_module(module_name, msgContainer)
            if retVal:
                self.send_msg_to_controller(retVal)


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
        msg.name = self.agent_info['name']
        msg.info = self.agent_info['info']

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
        self.send_msg_to_module_group(msgContainer)

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
        self.send_msg_to_module_group(msgContainer)

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
                        self.send_msg_to_module_group(msgContainer)
                    else:
                        execTime = datetime.datetime.strptime(cmdDesc.exec_time, "%Y-%m-%d %H:%M:%S.%f")
                        self.log.debug("Agent schedule task for message: {}:{} at {}".format(cmdDesc.type, cmdDesc.func_name, execTime))
                        self.jobScheduler.add_job(self.send_msg_to_module_group, 'date', run_date=execTime, kwargs={'msgContainer' : msgContainer})


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