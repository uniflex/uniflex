import logging
import time
from datetime import datetime
from datetime import timedelta
import wishful_framework as msgs
import wishful_framework as wishful_module
import wishful_upis as upis


__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


@wishful_module.build_module
class ControllerMonitor(wishful_module.AgentModule):
    def __init__(self, agent):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self.forceStop = False

        self.discoveryThread = None
        self.connectedToController = False
        self.echoMsgInterval = 3
        self.echoTimeOut = 10
        self.echoSendJob = None
        self.connectionLostJob = None

    @wishful_module.on_exit()
    def stop_module(self):
        self.forceStop = True
        self.terminate_connection_to_controller()

    @wishful_module.on_event(upis.mgmt.ControllerDiscoveredEvent)
    def setup_connection_to_controller(self, event):
        if self.connectedToController or self.forceStop:
            self.log.debug("Agent already connected to controller".format())
            return

        if event.dlink is None or event.ulink is None:
            return

        dlink = event.dlink
        uplink = event.ulink

        self.log.debug(
            "Agent connects controller: DL:{}, UL:{}".format(dlink, uplink))
        self.agent.transport.connect(dlink, uplink)

        topic = "NEW_NODE"
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.NewNodeMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.NewNodeMsg)
        cmdDesc.serialization_type = msgs.CmdDesc.PROTOBUF

        msg = msgs.NewNodeMsg()
        msg.agent_uuid = self.agent.uuid
        msg.ip = self.agent.ip
        msg.name = self.agent.name
        msg.info = self.agent.info

        for mid, module in self.agent.moduleManager.modules.items():
            moduleMsg = msg.modules.add()
            moduleMsg.id = mid
            moduleMsg.name = module.name
            for f in module.get_functions():
                function = moduleMsg.functions.add()
                function.name = f

            for g in module.get_generators():
                generator = moduleMsg.generators.add()
                generator.name = g

        for ifaceId, modules in self.agent.moduleManager.iface_to_module_mapping.items():
            iface = msg.interfaces.add()
            iface.id = int(ifaceId)
            iface.name = self.agent.moduleManager.interfaces[ifaceId]
            for module in modules:
                imodule = iface.modules.add()
                imodule.id = module.id
                imodule.name = module.name

        msgContainer = [topic, cmdDesc, msg]

        self.log.debug("Agent sends context-setup request to controller")
        time.sleep(1)  # TODO: are we waiting for connection?
        self.agent.transport.send_ctr_to_controller(msgContainer)

    @wishful_module.on_event(upis.mgmt.ControllerConnectionCompletedEvent)
    def setup_connection_to_controller_complete(self, event):
        cmdDesc = event.cmdDesc
        msg = msgs.NewNodeAck()
        msg.ParseFromString(event.msg)

        self.log.debug("Agent received msgType: {} with status: {}".format(
            cmdDesc.type, msg.status))

        self.log.debug(
            "Agent connects to controller and subscribes to received topics")
        self.agent.transport.subscribe_to(self.agent.uuid)
        for topic in msg.topics:
            self.agent.transport.subscribe_to(topic)

        # stop discovery module:
        self.connectedToController = True
        self.agent.controllerUuid = msg.controller_uuid

        # notify CONNECTED to modules
        self.agent.moduleManager.connected()

        # start sending hello msgs
        execTime = str(datetime.now() +
                       timedelta(seconds=self.echoMsgInterval))
        self.log.debug("Agent schedule sending of Hello message".format())
        self.echoSendJob = self.agent.jobScheduler.add_job(
            self.send_hello_msg_to_controller, 'date', run_date=execTime)

        execTime = (datetime.now() +
                    timedelta(seconds=self.echoTimeOut))
        self.connectionLostJob = self.agent.jobScheduler.add_job(
            self.connection_to_controller_lost, 'date', run_date=execTime)

    def send_hello_msg_to_controller(self):
        self.log.debug("Agent sends HelloMsg to controller")
        topic = self.agent.uuid
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.HelloMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.HelloMsg)
        cmdDesc.serialization_type = msgs.CmdDesc.PROTOBUF

        msg = msgs.HelloMsg()
        msg.uuid = str(self.agent.uuid)
        msg.timeout = 3 * self.echoMsgInterval
        msgContainer = [topic, cmdDesc, msg]
        self.agent.transport.send_to_controller(msgContainer)

        # reschedule hello msg
        self.log.debug("Agent schedule sending of Hello message".format())
        execTime = (datetime.now() +
                    timedelta(seconds=self.echoMsgInterval))
        self.echoSendJob = self.agent.jobScheduler.add_job(
            self.send_hello_msg_to_controller, 'date', run_date=execTime)

    def connection_to_controller_lost(self):
        self.log.debug(
            "Agent lost connection with controller,"
            " stop sending EchoMsg".format())
        self.echoSendJob.remove()

        self.agent.transport.disconnect()
        self.connectedToController = False
        self.agent.controllerUuid = None

        # notify DISCONNECTED to modules
        self.agent.moduleManager.disconnected()

        self.log.debug("Agent restarts discovery procedure".format())
        self.start_discovery_procedure()

    @wishful_module.on_event(upis.mgmt.HelloMsgEvent)
    def serve_hello_msg(self, event):
        self.log.debug("Agent received HELLO MESSAGE from controller".format())
        self.connectionLostJob.remove()
        execTime = (datetime.now() +
                    timedelta(seconds=self.echoTimeOut))
        self.connectionLostJob = self.agent.jobScheduler.add_job(
            self.connection_to_controller_lost, 'date', run_date=execTime)

    def terminate_connection_to_controller(self):
        self.log.debug("Agend sends NodeExitMsg to Controller".format())
        topic = "NODE_EXIT"
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msgs.get_msg_type(msgs.NodeExitMsg)
        cmdDesc.func_name = msgs.get_msg_type(msgs.NodeExitMsg)
        cmdDesc.serialization_type = msgs.CmdDesc.PROTOBUF

        msg = msgs.NodeExitMsg()
        msg.agent_uuid = self.agent.uuid
        msg.reason = "Process terminated"

        msgContainer = [topic, cmdDesc, msg]
        self.agent.transport.send_ctr_to_controller(msgContainer)
