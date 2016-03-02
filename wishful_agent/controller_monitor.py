import logging
import time
import sys
import datetime
import threading
try:
   import cPickle as pickle
except:
   import pickle

import wishful_framework as msgs

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class ControllerMonitor(object):
    def __init__(self, agent):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent

        self.controller_uuid = None
        self.discoveryThread = None
        self.connectedToController = False
        self.echoMsgInterval = 3
        self.echoTimeOut = 10
        self.echoSendJob = None
        self.connectionLostJob = None

        self.connectionTimeout = 10
        self.connectionTimeoutJob = None


    def start(self):
        self.start_discovery_procedure()


    def stop(self):
        self.terminate_connection_to_controller()


    def start_discovery_procedure(self):
        self.discoveryThread = threading.Thread(target=self.discover_controller)
        self.discoveryThread.setDaemon(True)
        self.discoveryThread.start()


    def discover_controller(self):
        while not self.connectedToController:
            discoveryModule = self.agent.moduleManager.discoveryModule
            assert discoveryModule

            [dlink, uplink] = discoveryModule.get_controller()

            if dlink and uplink:
                self.setup_connection_to_controller(dlink,uplink)
                execTime = datetime.datetime.now() + datetime.timedelta(seconds=self.connectionTimeout)
                self.connectionTimeoutJob = self.agent.jobScheduler.add_job(self.start_discovery_procedure, 'date', run_date=execTime)
                break

            time.sleep(5)



    def setup_connection_to_controller(self, dlink, uplink):
        if self.connectedToController:
            self.log.debug("Agent already connected to controller".format())
            return

        self.log.debug("Agent connects controller: DL-{}, UL-{}".format(dlink, uplink))
        self.agent.transport.connect(dlink, uplink)

        topic = "NEW_NODE"
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.NewNodeMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.NewNodeMsg)
        msg = msgs.NewNodeMsg()
        msg.agent_uuid =  self.agent.uuid
        msg.ip = self.agent.ip
        msg.name = self.agent.name
        msg.info = self.agent.info
        
        for mid, module in self.agent.moduleManager.modules.iteritems():
            moduleMsg = msg.modules.add()
            moduleMsg.id = mid
            moduleMsg.name = module.name
            for f in module.get_capabilities():
                function = moduleMsg.functions.add()
                function.name = f

        for ifaceId, modules in self.agent.moduleManager.iface_to_module_mapping.iteritems():              
            iface = msg.interfaces.add()
            iface.id = int(ifaceId)
            iface.name = self.agent.moduleManager.interfaces[ifaceId]
            for module in modules:
                imodule = iface.modules.add()
                imodule.id = module.id
                imodule.name = module.name

        msgContainer = [topic, cmdDesc.SerializeToString(), msg.SerializeToString()]

        self.log.debug("Agent sends context-setup request to controller")
        time.sleep(1) # TODO: are we waiting for connection?
        self.agent.transport.send_ctr_to_controller(msgContainer)


    def setup_connection_to_controller_complete(self, msgContainer):
        cmdDesc = msgContainer[1]
        msg = msgs.NewNodeAck()
        msg.ParseFromString(msgContainer[2])

        self.log.debug("Agent received msgType: {} with status: {}".format(cmdDesc.type, msg.status))

        self.log.debug("Agent connects to controller and subscribes to received topics")
        self.agent.transport.subscribe_to(self.agent.uuid)
        for topic in msg.topics:
            self.agent.transport.subscribe_to(topic)

        #stop discovery module:
        self.connectedToController = True
        self.controller_uuid = msg.controller_uuid

        #notify CONNECTED to modules
        self.agent.moduleManager.connected()

        #remove connection timeout job
        self.connectionTimeoutJob.remove()

        #start sending hello msgs
        execTime =  str(datetime.datetime.now() + datetime.timedelta(seconds=self.echoMsgInterval))
        self.log.debug("Agent schedule sending of Hello message".format())
        self.echoSendJob = self.agent.jobScheduler.add_job(self.send_hello_msg_to_controller, 'date', run_date=execTime)

        execTime = datetime.datetime.now() + datetime.timedelta(seconds=self.echoTimeOut)
        self.connectionLostJob = self.agent.jobScheduler.add_job(self.connection_to_controller_lost, 'date', run_date=execTime)

    def send_hello_msg_to_controller(self):
        self.log.debug("Agent sends HelloMsg to controller")
        topic = self.agent.uuid
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.HelloMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.HelloMsg)
        msg = msgs.HelloMsg()
        msg.uuid = str(self.agent.uuid)
        msg.timeout = 3 * self.echoMsgInterval
        msgContainer = [topic, cmdDesc.SerializeToString(), msg.SerializeToString()]
        self.agent.transport.send_to_controller(msgContainer)

        #reschedule hello msg
        self.log.debug("Agent schedule sending of Hello message".format())
        execTime =  datetime.datetime.now() + datetime.timedelta(seconds=self.echoMsgInterval)
        self.echoSendJob = self.agent.jobScheduler.add_job(self.send_hello_msg_to_controller, 'date', run_date=execTime)


    def connection_to_controller_lost(self):
        self.log.debug("Agent lost connection with controller, stop sending EchoMsg".format())
        self.echoSendJob.remove()

        self.agent.transport.disconnect()
        self.connectedToController = False
        self.controller_uuid = None

        #notify DISCONNECTED to modules
        self.agent.moduleManager.disconnected()

        self.log.debug("Agent restarts discovery procedure".format())
        self.start_discovery_procedure()

    def serve_hello_msg(self, msgContainer):
        self.log.debug("Agent received HELLO MESSAGE from controller".format())
        self.connectionLostJob.remove()
        execTime = datetime.datetime.now() + datetime.timedelta(seconds=self.echoTimeOut)
        self.connectionLostJob = self.agent.jobScheduler.add_job(self.connection_to_controller_lost, 'date', run_date=execTime)


    def terminate_connection_to_controller(self):
        self.log.debug("Agend sends NodeExitMsg to Controller".format())
        topic = "NODE_EXIT"
        cmdDesc= msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.NodeExitMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.NodeExitMsg)
        msg = msgs.NodeExitMsg()
        msg.agent_uuid =  self.agent.uuid
        msg.reason = "Process terminated"

        msgContainer = [topic, cmdDesc.SerializeToString(), msg.SerializeToString()]
        self.agent.transport.send_ctr_to_controller(msgContainer)