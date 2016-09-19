import sys
import zmq
import socket
import logging
import threading
import json
import dill  # for pickling what standard pickle can’t cope with
try:
    import cPickle as pickle
except:
    import pickle

import wishful_agent.msgs as msgs
from .timer import TimerEventSender
from .core import wishful_module
from .common import get_inheritors
from .node import Node, Device
import wishful_upis as upis

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class SendHelloMsgTimeEvent(upis.mgmt.TimeEvent):
    def __init__(self):
        super().__init__()


class HelloMsgTimeoutEvent(upis.mgmt.TimeEvent):
    def __init__(self):
        super().__init__()


@wishful_module.build_module
class TransportChannel(wishful_module.AgentModule):
    def __init__(self, agent):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self._nodeManager = None
        self.xpub_url = None
        self.xsub_url = None
        self.timeout = 500  # ms
        self.forceStop = False

        self.eventClasses = None

        self.connected = False
        self.helloMsgInterval = 3
        self.helloTimeOut = 10
        self.helloMsgTimer = TimerEventSender(self, SendHelloMsgTimeEvent)
        self.helloMsgTimeoutTimer = TimerEventSender(self,
                                                     HelloMsgTimeoutEvent)

        self.pubSocketLock = threading.Lock()
        self.poller = zmq.Poller()
        self.context = zmq.Context()

        # for downlink communication with controller
        self.sub = self.context.socket(zmq.SUB)
        self.log.debug(
            "Agent connects subscribes to topics")
        self.subscribe_to(self.agent.uuid)
        self.subscribe_to("ALL")
        self.subscribe_to("NODE_INFO")
        self.subscribe_to("NODE_EXIT")
        self.subscribe_to("HELLO_MSG")
        self.sub.setsockopt(zmq.LINGER, 100)

        # for uplink communication with controller
        self.pub = self.context.socket(zmq.PUB)

        # register module socket in poller
        self.poller.register(self.sub, zmq.POLLIN)

    def set_downlink(self, xpub_url):
        self.log.debug("Set Downlink: {}".format(xpub_url))
        self.xpub_url = xpub_url

    def set_uplink(self, xsub_url):
        self.log.debug("Set Uplink: {}".format(xsub_url))
        self.xsub_url = xsub_url

    def subscribe_to(self, topic):
        self.log.debug("Agent subscribes to topic: {}".format(topic))
        if sys.version_info.major >= 3:
            self.sub.setsockopt_string(zmq.SUBSCRIBE, str(topic))
        else:
            self.sub.setsockopt(zmq.SUBSCRIBE, str(topic))

    @wishful_module.on_start()
    def start_module(self):
        if self.xpub_url and self.xsub_url:
            self.connect(self.xpub_url, self.xsub_url)

        thread = threading.Thread(target=self.recv_msgs)
        thread.setDaemon(True)
        thread.start()

        self.eventClasses = get_inheritors(upis.upi.EventBase)

    @wishful_module.on_exit()
    def stop_module(self):
        self.forceStop = True
        self.notify_node_exit()
        try:
            self.sub.setsockopt(zmq.LINGER, 0)
            self.pub.setsockopt(zmq.LINGER, 0)
            self.sub.close()
            self.pub.close()
            self.context.term()
        except:
            pass

    @wishful_module.on_event(upis.mgmt.ControllerDiscoveredEvent)
    def connect_to_broker(self, event):
        if self.connected or self.forceStop:
            self.log.debug("Agent already connected to broker".format())
            return

        if event.dlink is None or event.ulink is None:
            return

        dlink = event.dlink
        uplink = event.ulink
        self.connect(dlink, uplink)

    def disconnect(self):
        if self.xpub_url and self.xsub_url:
            try:
                self.pub.disconnect(self.xsub_url)
                self.sub.disconnect(self.xpub_url)
                self.connected = False
            except:
                pass

    def connect(self, xpub_url, xsub_url):
        if not xpub_url and not xsub_url:
            return

        self.disconnect()
        self.xpub_url = xpub_url
        self.xsub_url = xsub_url
        self.log.debug("Connect to Broker on XPUB-{},"
                       " XSUB-{}".format(self.xpub_url, self.xsub_url))
        self.pub.connect(self.xsub_url)
        self.sub.connect(self.xpub_url)
        self.connected = True
        # stop discovery module
        # and notify CONNECTED to modules
        self.log.debug("Notify controller connected")
        event = upis.mgmt.ControllerConnectedEvent()
        self.send_event(event)

        # start sending hello msgs
        self.helloMsgTimer.start(self.helloMsgInterval)

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

        for mid, module in self.agent.moduleManager.modules.items():
            moduleMsg = msg.modules.add()
            moduleMsg.id = mid
            moduleMsg.name = module.name

            if module.device:
                deviceDesc = msgs.Device()
                deviceDesc.id = module.device._id
                deviceDesc.name = module.device.name
                moduleMsg.device.CopyFrom(deviceDesc)

            for name in module.get_attributes():
                attribute = moduleMsg.attributes.add()
                attribute.name = name
            for name in module.get_functions():
                function = moduleMsg.functions.add()
                function.name = name
            for name in module.get_events():
                event = moduleMsg.events.add()
                event.name = name
            for name in module.get_services():
                service = moduleMsg.services.add()
                service.name = name
        msgContainer = [topic, msgDesc, msg]

        self.log.debug("Agent sends node info")
        self.send(msgContainer)

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
        self.send(msgContainer)

    def send_node_add_notification(self, dest):
        topic = dest
        msgDesc = msgs.MessageDescription()
        msgDesc.msgType = msgs.get_msg_type(msgs.NodeAddNotification)
        msgDesc.serializationType = msgs.SerializationType.PROTOBUF

        msg = msgs.NodeAddNotification()
        msg.agent_uuid = self.agent.uuid
        msgContainer = [topic, msgDesc, msg]
        self.log.debug("Agent sends node add notification")
        self.send(msgContainer)

    def send(self, msgContainer):
        topic = msgContainer[0].encode('utf-8')
        msgDesc = msgContainer[1]
        msg = msgContainer[2]

        msgDesc.sourceUuid = self.agent.uuid
        msgContainer[0] = topic

        serialized = False
        if hasattr(msg, 'serialize'):
            msgDesc.serializationType = msgs.SerializationType.JSON
            msg = json.dumps(msg.serialize())
            msg = msg.encode('utf-8')
            serialized = True

        if not serialized:
            if msgDesc.serializationType == msgs.SerializationType.PROTOBUF:
                msg = msg.SerializeToString()

            # if serialization not set, pickle it
            else:
                msgDesc.serializationType = msgs.SerializationType.PICKLE
                try:
                    msg = pickle.dumps(msg)
                except:
                    msg = dill.dumps(msg)

        msgDesc = json.dumps(msgDesc.serialize())
        msgContainer[1] = msgDesc.encode('utf-8')

        msgContainer[2] = msg

        # TODO: it is quick fix; find better solution with socket per thread
        self.pubSocketLock.acquire()
        try:
            self.pub.send_multipart(msgContainer)
        finally:
            self.pubSocketLock.release()

    @wishful_module.on_event(SendHelloMsgTimeEvent)
    def send_hello_msg(self, event):
        self.log.debug("Agent sends HelloMsg")
        topic = "HELLO_MSG"
        msgDesc = msgs.MessageDescription()
        msgDesc.msgType = msgs.get_msg_type(msgs.HelloMsg)
        msgDesc.serializationType = msgs.SerializationType.PROTOBUF

        msg = msgs.HelloMsg()
        msg.uuid = str(self.agent.uuid)
        msg.timeout = self.helloTimeOut
        msgContainer = [topic, msgDesc, msg]
        self.send(msgContainer)

        # reschedule hello msg
        self.helloMsgTimer.start(self.helloMsgInterval)

    @wishful_module.on_event(HelloMsgTimeoutEvent)
    def connection_with_broker_lost(self, event):
        self.log.debug(
            "Agent lost connection with broker".format())
        self.helloMsgTimer.cancel()

        # notify Connection Lost
        event = upis.mgmt.ControllerLostEvent(0)
        self.send_event(event)
        # notify DISCONNECTED
        event = upis.mgmt.ControllerDisconnectedEvent()
        self.disconnect()
        self.send_event(event)

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
        self.send(msgContainer)

    def process_msgs(self, msgContainer):
        msgDesc = msgContainer[1]
        src = msgDesc.sourceUuid
        self.log.debug(
            "Transport Channel received message: {} from: {}, myUuid: {}"
            .format(msgDesc.msgType, src, self.agent.uuid))

        if src == self.agent.uuid:
            self.log.debug("OWN msg -> discard")
            return

        if msgDesc.msgType == msgs.get_msg_type(msgs.NodeInfoMsg):
            self._nodeManager.serve_node_info_msg(msgContainer)

        elif msgDesc.msgType == msgs.get_msg_type(msgs.NodeInfoRequest):
            self.send_node_info(src)

        elif msgDesc.msgType == msgs.get_msg_type(msgs.NodeAddNotification):
            self._nodeManager.serve_node_add_notification(msgContainer)

        elif msgDesc.msgType == msgs.get_msg_type(msgs.NodeExitMsg):
            self._nodeManager.serve_node_exit_msg(msgContainer)

        elif msgDesc.msgType == msgs.get_msg_type(msgs.HelloMsg):
            self._nodeManager.serve_hello_msg(msgContainer)

        else:
            self._nodeManager.serve_event_msg(msgContainer)

    def recv_msgs(self):
        while not self.forceStop:
            socks = dict(self.poller.poll(self.timeout))
            if self.sub in socks and socks[self.sub] == zmq.POLLIN:
                msgContainer = self.sub.recv_multipart()
                assert len(msgContainer) == 3, msgContainer
                topic = msgContainer[0].decode('utf-8')
                msgDesc = msgContainer[1].decode('utf-8')
                msgDesc = json.loads(msgDesc)
                msgDesc = msgs.MessageDescription.parse(msgDesc)
                msg = msgContainer[2]

                if msgDesc.serializationType == msgs.SerializationType.PICKLE:
                    try:
                        msg = pickle.loads(msg)
                    except:
                        msg = dill.loads(msg)
                elif msgDesc.serializationType == msgs.SerializationType.PROTOBUF:
                    # TODO: move all protobuf serialization here
                    pass
                elif msgDesc.serializationType == msgs.SerializationType.JSON:
                    msg = msg.decode('utf-8')
                    msg = json.loads(msg)
                    eventType = str(topic)
                    # get event class and create it
                    myClass = self.eventClasses.get(eventType, None)
                    if myClass and hasattr(myClass, 'parse'):
                        myEvent = myClass.parse(msg)
                        myEvent.node = msgDesc.sourceUuid
                        myEvent.device = None
                        msg = myEvent
                    else:
                        # discard message that cannot be parsed
                        continue

                msgContainer[0] = topic
                msgContainer[1] = msgDesc
                msgContainer[2] = msg

                self.process_msgs(msgContainer)

    def send_event_outside(self, event, dstNode=None):
        filterEvents = ["NewNodeEvent", "AgentStartEvent",
                        "ControllerDiscoveredEvent", "AgentExitEvent",
                        "NodeExitEvent", "NodeLostEvent",
                        "SendHelloMsgTimeEvent", "HelloMsgTimeoutEvent",
                        "ControllerConnectedEvent"]
        if event.__class__.__name__ in filterEvents:
            return

        # flatten event
        self.log.debug("Event name: {}".format(event.__class__.__name__))
        if event.node and isinstance(event.node, Node):
            event.node = event.node.uuid
        if event.device and isinstance(event.device, Device):
            event.device = event.device._id

        topic = event.__class__.__name__

        # TODO: improve below, call function with dstNode!!!
        if event.__class__.__name__ == 'CtxReturnValueEvent':
            topic = event.dest

        if dstNode:
            topic = dstNode.uuid

        self.log.debug("sends cmd event : {} on topic: {}"
                       .format(event.__class__.__name__, topic))

        msgDesc = msgs.MessageDescription()
        msgDesc.msgType = event.__class__.__name__
        msgDesc.serializationType = msgs.SerializationType.PICKLE

        data = event
        msgContainer = [topic, msgDesc, data]
        self.send(msgContainer)


class Broker(threading.Thread):
    """docstring for Broker"""

    def __init__(self, xpub="tcp://127.0.0.1:8990",
                 xsub="tcp://127.0.0.1:8989"):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        super(Broker, self).__init__()
        self.running = False
        self.xpub_url = xpub
        self.xsub_url = xsub
        self.ctx = zmq.Context()
        self.xpub = self.ctx.socket(zmq.XPUB)
        self.xpub.bind(self.xpub_url)
        self.xsub = self.ctx.socket(zmq.XSUB)
        self.xsub.bind(self.xsub_url)
        # self.proxy = zmq.proxy(xpub, xsub)

    def run(self):
        self.log.debug("Broker starts XPUB:{}, XSUB:{}"
                       .format(self.xpub_url, self.xsub_url))
        # self.proxy.start()
        poller = zmq.Poller()
        poller.register(self.xpub, zmq.POLLIN)
        poller.register(self.xsub, zmq.POLLIN)
        self.running = True
        while self.running:
            events = dict(poller.poll(1000))
            if self.xpub in events:
                message = self.xpub.recv_multipart()
                self.log.debug("subscription message: {}".format(message[0]))
                self.xsub.send_multipart(message)
            if self.xsub in events:
                message = self.xsub.recv_multipart()
                self.log.debug("publishing message: {}".format(message))
                self.xpub.send_multipart(message)

    def stop(self):
        self.running = False
