import logging
import socket
import threading

from .core import events
from .msgs import messages_pb2 as msgs
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
        if self.local_node:
            if self.local_node.uuid == uuid:
                return self.local_node

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
        node.set_timer_callback(self.remove_node_hello_timer)
        d = threading.Thread(target=node.hello_timer)
        d.setDaemon(True)
        d.start()

        # if he already knows me
        if node.uuid in self.receivedAddNotifications:
            self.notify_new_node_event(node)

        # tell node that I know him
        self._transportChannel.send_node_add_notification(node.uuid)
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
            self._transportChannel.send_node_info_request(sourceUuid)
            return
        node.refresh_hello_timer()

    def send_event_cmd(self, event, dstNode):
        self._moduleManager.send_cmd_event(event, dstNode)
