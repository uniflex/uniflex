import logging
import socket
import threading

from . import modules
from . import events

import uniflex.msgs as msgs
from .node import Node

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class NodeManager(object):
    def __init__(self, agent):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self._transportChannel = None
        self._moduleManager = None

        self.local_node = None
        self.nodes = []
        self.receivedAddNotifications = []

        self.helloMsgInterval = 3
        self.helloTimeout = 3 * self.helloMsgInterval

    def get_node_by_uuid(self, uuid):
        node = None
        for n in self.nodes:
            if n.uuid == uuid:
                node = n
                break
        return node

    def create_local_node(self, agent):
        self.local_node = Node(agent.uuid)
        self.nodes.append(self.local_node)
        self.local_node.hostname = socket.gethostname()
        self.local_node.nodeManager = self

    def get_local_node(self):
        return self.local_node

    def serve_node_info_msg(self, msgContainer):
        msg = msgs.NodeInfoMsg()
        msg.ParseFromString(msgContainer[2])
        agentUuid = str(msg.agent_uuid)
        agentName = msg.name
        agentInfo = msg.info

        for n in self.nodes:
            if agentUuid == n.uuid:
                self.log.debug("Already known Node UUID: {},"
                               " Name: {}, Info: {}"
                               .format(agentUuid, agentName, agentInfo))
                return

        node = Node.create_node_from_msg(msg)
        node.nodeManager = self
        node._currentNode = self.local_node
        for m in node.all_modules.values():
            m._currentNode = self.local_node

        self.nodes.append(node)
        self.log.debug("New node with UUID: {}, Name: {},"
                       " Info: {}".format(agentUuid, agentName, agentInfo))
        # start hello timeout timer
        node._set_timer_callback(self.remove_node_hello_timer)
        d = threading.Thread(target=node._hello_timer)
        d.setDaemon(True)
        d.start()

        # if he already knows me
        if node.uuid in self.receivedAddNotifications:
            self.notify_new_node_event(node)

        # tell node that I know him
        self.send_node_add_notification(node.uuid)
        return node

    def serve_node_add_notification(self, msgContainer):
        self.log.debug("add node notification")
        msg = msgs.NodeAddNotification()
        msg.ParseFromString(msgContainer[2])
        srcUuid = str(msg.agent_uuid)

        self.receivedAddNotifications.append(srcUuid)
        node = self.get_node_by_uuid(srcUuid)

        if not node:
            return
        self.notify_new_node_event(node)

    def notify_new_node_event(self, node):
        event = events.NewNodeEvent()
        event.node = node
        self._moduleManager.send_event(event)
        self.log.info("New node event sent")

    def remove_node_hello_timer(self, node):
        reason = "HelloTimeout"
        self.log.debug("Remove node with UUID: {},"
                       " Reason: {}".format(node.uuid, reason))

        if node and node in self.nodes:
            self.nodes.remove(node)

            event = events.NodeLostEvent(reason)
            event.node = node
            self._moduleManager.send_event(event)

    def serve_node_exit_msg(self, msgContainer):
        msg = msgs.NodeExitMsg()
        msg.ParseFromString(msgContainer[2])
        agentId = str(msg.agent_uuid)
        reason = msg.reason

        node = self.get_node_by_uuid(agentId)

        if not node:
            return

        self.log.debug("Remove node with UUID: {},"
                       " Reason: {}".format(agentId, reason))

        if node and node in self.nodes:
            self.nodes.remove(node)

            event = events.NodeExitEvent(reason)
            event.node = node
            self._moduleManager.send_event(event)

    def serve_hello_msg(self, msgContainer):
        msgDesc = msgContainer[1]
        sourceUuid = msgDesc.sourceUuid
        if sourceUuid == self.agent.uuid:
            self.log.debug("Received own HELLO MESSAGE; discard"
                           .format())
            return
        else:
            self.log.debug("Received HELLO MESSAGE from node: {}"
                           .format(sourceUuid))
        msg = msgs.HelloMsg()
        msg.ParseFromString(msgContainer[2])

        node = self.get_node_by_uuid(str(msg.uuid))
        if node is None:
            self.log.debug("Unknown node: {}"
                           .format(sourceUuid))
            self.send_node_info_request(sourceUuid)
            return
        node._refresh_hello_timer()

    def send_event_cmd(self, event, dstNode):
        self._moduleManager.send_cmd_event(event, dstNode)

    def send_hello_msg(self, timeout=10):
        self.log.debug("Agent sends HelloMsg")
        topic = "HELLO_MSG"
        msgDesc = msgs.MessageDescription()
        msgDesc.msgType = msgs.get_msg_type(msgs.HelloMsg)
        msgDesc.serializationType = msgs.SerializationType.PROTOBUF

        msg = msgs.HelloMsg()
        msg.uuid = str(self.agent.uuid)
        msg.timeout = timeout
        msgContainer = [topic, msgDesc, msg]
        self._transportChannel.send(msgContainer)

    def send_node_info_request(self, dest=None):
        topic = "ALL"
        if dest:
            topic = dest
        msgDesc = msgs.MessageDescription()
        msgDesc.msgType = msgs.get_msg_type(msgs.NodeInfoRequest)
        msgDesc.serializationType = msgs.SerializationType.PROTOBUF

        msg = msgs.NodeInfoRequest()
        msg.agent_uuid = self.agent.uuid
        msgContainer = [topic, msgDesc, msg]
        self.log.debug("Agent sends node info request")
        self._transportChannel.send(msgContainer)

    def send_node_info(self, dest=None):
        topic = "NODE_INFO"
        if dest:
            topic = dest

        msgDesc = msgs.MessageDescription()
        msgDesc.msgType = msgs.get_msg_type(msgs.NodeInfoMsg)
        msgDesc.serializationType = msgs.SerializationType.PROTOBUF

        msg = msgs.NodeInfoMsg()
        msg.agent_uuid = self.agent.uuid
        msg.ip = self.agent.ip
        msg.name = self.agent.name
        msg.hostname = socket.gethostname()
        msg.info = self.agent.info

        for uuid, module in self.agent.moduleManager.modules.items():
            if isinstance(module, modules.CoreModule):
                continue

            moduleMsg = msg.modules.add()
            moduleMsg.uuid = module.uuid
            moduleMsg.name = module.name
            moduleMsg.type = msgs.Module.MODULE

            if isinstance(module, modules.ControlApplication):
                moduleMsg.type = msgs.Module.APPLICATION
            else:
                moduleMsg.type = msgs.Module.MODULE

            if module.device:
                moduleMsg.type = msgs.Module.DEVICE
                deviceDesc = msgs.Device()
                deviceDesc.name = module.device
                moduleMsg.device.CopyFrom(deviceDesc)

            for name in module.get_functions():
                function = moduleMsg.functions.add()
                function.name = name
            for name in module.get_in_events():
                event = moduleMsg.in_events.add()
                event.name = name
            for name in module.get_out_events():
                event = moduleMsg.out_events.add()
                event.name = name

        msgContainer = [topic, msgDesc, msg]

        self.log.debug("Agent sends node info")
        self._transportChannel.send(msgContainer)

    def send_node_add_notification(self, dest):
        topic = dest
        msgDesc = msgs.MessageDescription()
        msgDesc.msgType = msgs.get_msg_type(msgs.NodeAddNotification)
        msgDesc.serializationType = msgs.SerializationType.PROTOBUF

        msg = msgs.NodeAddNotification()
        msg.agent_uuid = self.agent.uuid
        msgContainer = [topic, msgDesc, msg]
        self.log.debug("Agent sends node add notification")
        self._transportChannel.send(msgContainer)

    def notify_node_exit(self):
        self.log.debug("Agend sends NodeExitMsg".format())
        topic = "NODE_EXIT"
        msgDesc = msgs.MessageDescription()
        msgDesc.msgType = msgs.get_msg_type(msgs.NodeExitMsg)
        msgDesc.serializationType = msgs.SerializationType.PROTOBUF

        msg = msgs.NodeExitMsg()
        msg.agent_uuid = self.agent.uuid
        msg.reason = "Process terminated"

        msgContainer = [topic, msgDesc, msg]
        self._transportChannel.send(msgContainer)
