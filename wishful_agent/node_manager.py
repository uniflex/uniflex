import logging
import threading
from queue import Queue

import wishful_framework as msgs
import wishful_framework as wishful_module
import wishful_upis as upis
from .node import Node, Device

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class NodeManager(wishful_module.AgentModule):
    def __init__(self, agent):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self._transportChannel = None
        self.local_node = None
        self.nodes = []
        self.receivedAddNotifications = []

        self._callIdGen = 0
        self.synchronousCalls = {}
        self.callCallbacks = {}

        self.helloMsgInterval = 3
        self.helloTimeout = 3 * self.helloMsgInterval

    def generate_call_id(self):
        self._callIdGen = self._callIdGen + 1
        return self._callIdGen

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

    def get_node_by_ip(self, ip):
        node = None
        for n in self.nodes:
            if n.ip == ip:
                node = n
                break
        return node

    def get_node_by_str(self, string):
        if isinstance(string, Node):
            return string

        node = None
        node = self.get_node_by_ip(string)
        if node:
            return node

        node = self.get_node_by_uuid(string)
        return node

    def create_local_node(self, agent):
        self.local_node = Node(agent.uuid)
        self.local_node.nodeManager = self
        self.nodes.append(self.local_node)
        event = upis.mgmt.NewNodeEvent()
        event.node = self.local_node
        self.moduleManager.send_event(event)

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
        event = upis.mgmt.NewNodeEvent()
        event.node = node
        self.send_event(event)
        self.log.info("New node event sent")

    def remove_node_hello_timer(self, node):
        reason = "HelloTimeout"
        self.log.debug("Remove node with UUID: {},"
                       " Reason: {}".format(node.uuid, reason))

        if node and node in self.nodes:
            self.nodes.remove(node)

            event = upis.mgmt.NodeLostEvent(reason)
            event.node = node
            self.send_event(event)

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

            event = upis.mgmt.NodeExitEvent(reason)
            event.node = node
            self.send_event(event)

    def serve_hello_msg(self, msgContainer):
        cmd = msgContainer[1]
        sourceUuid = cmd.caller_id
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
        self.log.debug("{}:{}".format(event.ctx._upi_type, event.ctx._upi))

        responseQueue = None
        callback = None
        if dstNode.local:
            self.send_event(event)
        else:
            if event.ctx._blocking:
                # save reference to response queue
                callId = self.generate_call_id()
                event.ctx._callId = callId
                responseQueue = event.responseQueue
                self.synchronousCalls[callId] = responseQueue
                event.responseQueue = None
            elif event.ctx._callback:
                # save reference to callback
                callId = self.generate_call_id()
                event.ctx._callId = callId
                callback = event.ctx._callback
                self.callCallbacks[callId] = callback
                event.ctx._callback = None

            # flatten event
            if event.node and isinstance(event.node, Node):
                event.node = event.node.uuid
            if event.device and isinstance(event.device, Device):
                event.device = event.device._id

            self._transportChannel.send_event_outside(event, dstNode)
            if event.ctx._blocking:
                event.responseQueue = responseQueue
            elif event.ctx._callback:
                event.ctx._callback = callback

    def serve_event_msg(self, msgContainer):
        event = msgContainer[2]
        node = self.get_node_by_uuid(event.node)
        self.log.debug("received event from node: {}".format(event.node))
        event.node = node
        if not event.node:
            return
        event.device = event.node.get_device(event.device)

        if isinstance(event, upis.mgmt.CtxCommandEvent):
            if event.ctx._blocking:
                event.responseQueue = Queue()
                self.moduleManager.send_event_locally(event)
                response = event.responseQueue.get()
                retEvent = upis.mgmt.CtxReturnValueEvent(event.ctx, response)
                retEvent.node = self.agent.nodeManager.get_local_node()
                retEvent.device = event.ctx._device
                self.log.debug("send response for blocking call")
                self._transportChannel.send_event_outside(retEvent)
            else:
                self.moduleManager.send_event_locally(event)

        elif isinstance(event, upis.mgmt.CtxReturnValueEvent):
            if event.ctx._callId in self.synchronousCalls:
                queue = self.synchronousCalls[event.ctx._callId]
                queue.put(event.msg)
            elif event.ctx._callId in self.callCallbacks:
                pass
            else:
                self.moduleManager.send_event_locally(event)
        else:
            self.moduleManager.send_event_locally(event)

        # returnValue = event.responseQueue.get()
        # event.responseQueue.put(returnValue)
        pass
