import sys
import zmq
import logging
import threading
import json
import dill  # for pickling what standard pickle can’t cope with
try:
    import cPickle as pickle
except:
    import pickle

from .timer import TimerEventSender
from .msgs import management_pb2 as msgs
from .msgs import msg_helper as msghelper
from .core import wishful_module
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

        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msghelper.get_msg_type(msgs.NodeInfoMsg)
        cmdDesc.func_name = msghelper.get_msg_type(msgs.NodeInfoMsg)
        cmdDesc.serialization_type = msgs.CmdDesc.PROTOBUF

        msg = msgs.NodeInfoMsg()
        msg.agent_uuid = self.agent.uuid
        msg.ip = self.agent.ip
        msg.name = self.agent.name
        msg.info = self.agent.info

        for mid, module in self.agent.moduleManager.modules.items():
            moduleMsg = msg.modules.add()
            moduleMsg.id = mid
            moduleMsg.name = module.name

            if module.device:
                deviceDesc = msgs.Device()
                deviceDesc.id = module.deviceId
                deviceDesc.name = module.device
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
        msgContainer = [topic, cmdDesc, msg]

        self.log.debug("Agent sends node info")
        self.send(msgContainer)

    def send_node_info_request(self, dest=None):
        topic = "ALL"
        if dest:
            topic = dest
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msghelper.get_msg_type(msgs.NodeInfoRequest)
        cmdDesc.func_name = msghelper.get_msg_type(msgs.NodeInfoRequest)
        cmdDesc.serialization_type = msgs.CmdDesc.PROTOBUF

        msg = msgs.NodeInfoRequest()
        msg.agent_uuid = self.agent.uuid
        msgContainer = [topic, cmdDesc, msg]
        self.log.debug("Agent sends node info request")
        self.send(msgContainer)

    def send_node_add_notification(self, dest):
        topic = dest
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msghelper.get_msg_type(msgs.NodeAddNotification)
        cmdDesc.func_name = msghelper.get_msg_type(msgs.NodeAddNotification)
        cmdDesc.serialization_type = msgs.CmdDesc.PROTOBUF

        msg = msgs.NodeAddNotification()
        msg.agent_uuid = self.agent.uuid
        msgContainer = [topic, cmdDesc, msg]
        self.log.debug("Agent sends node add notification")
        self.send(msgContainer)

    def send(self, msgContainer):
        topic = msgContainer[0].encode('utf-8')
        cmdDesc = msgContainer[1]
        msg = msgContainer[2]

        cmdDesc.caller_id = self.agent.uuid
        msgContainer[0] = topic

        serialized = False
        if hasattr(msg, 'serialize'):
            cmdDesc.serialization_type = msgs.CmdDesc.JSON
            msg = json.dumps(msg.serialize())
            msg = msg.encode('utf-8')
            serialized = True

        msgContainer[1] = cmdDesc.SerializeToString()

        if not serialized:
            if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
                try:
                    msg = pickle.dumps(msg)
                except:
                    msg = dill.dumps(msg)
            elif cmdDesc.serialization_type == msgs.CmdDesc.PROTOBUF:
                msg = msg.SerializeToString()

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
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msghelper.get_msg_type(msgs.HelloMsg)
        cmdDesc.func_name = msghelper.get_msg_type(msgs.HelloMsg)
        cmdDesc.serialization_type = msgs.CmdDesc.PROTOBUF

        msg = msgs.HelloMsg()
        msg.uuid = str(self.agent.uuid)
        msg.timeout = self.helloTimeOut
        msgContainer = [topic, cmdDesc, msg]
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
        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = msghelper.get_msg_type(msgs.NodeExitMsg)
        cmdDesc.func_name = msghelper.get_msg_type(msgs.NodeExitMsg)
        cmdDesc.serialization_type = msgs.CmdDesc.PROTOBUF

        msg = msgs.NodeExitMsg()
        msg.agent_uuid = self.agent.uuid
        msg.reason = "Process terminated"

        msgContainer = [topic, cmdDesc, msg]
        self.send(msgContainer)

    def process_msgs(self, msgContainer):
        cmdDesc = msgContainer[1]
        src = cmdDesc.caller_id
        self.log.debug(
            "Transport Channel received message: {} from: {}"
            .format(cmdDesc.type, src))

        if src == self.agent.uuid:
            self.log.debug("OWN msg -> discard")
            return

        if cmdDesc.type == msghelper.get_msg_type(msgs.NodeInfoMsg):
            self._nodeManager.serve_node_info_msg(msgContainer)

        elif cmdDesc.type == msghelper.get_msg_type(msgs.NodeInfoRequest):
            self.send_node_info(src)

        elif cmdDesc.type == msghelper.get_msg_type(msgs.NodeAddNotification):
            self._nodeManager.serve_node_add_notification(msgContainer)

        elif cmdDesc.type == msghelper.get_msg_type(msgs.NodeExitMsg):
            self._nodeManager.serve_node_exit_msg(msgContainer)

        elif cmdDesc.type == msghelper.get_msg_type(msgs.HelloMsg):
            self._nodeManager.serve_hello_msg(msgContainer)

        else:
            self._nodeManager.serve_event_msg(msgContainer)

    def recv_msgs(self):
        while not self.forceStop:
            socks = dict(self.poller.poll(self.timeout))
            if self.sub in socks and socks[self.sub] == zmq.POLLIN:
                msgContainer = self.sub.recv_multipart()
                print(msgContainer)
                assert len(msgContainer) == 3, msgContainer
                dest = msgContainer[0]
                cmdDesc = msgs.CmdDesc()
                # TODO: workaround FIX IT!!
                try:
                    cmdDesc.ParseFromString(msgContainer[1])
                except:
                    pass

                msg = msgContainer[2]

                if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
                    try:
                        msg = pickle.loads(msg)
                    except:
                        msg = dill.loads(msg)
                elif cmdDesc.serialization_type == msgs.CmdDesc.JSON:
                    msg = msg.decode('utf-8')
                    msg = json.loads(msg)
                    # get event class and create it

                msgContainer[0] = dest.decode('utf-8')
                msgContainer[1] = cmdDesc
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
        if event.node and not isinstance(event.node, str):
            event.node = event.node.uuid
        if event.device and not isinstance(event.device, str):
            event.device = event.device._id

        topic = event.__class__.__name__

        # TODO: improve below, call function with dstNode!!!
        if event.__class__.__name__ == 'CtxReturnValueEvent':
            topic = event.dest

        if dstNode:
            topic = dstNode.uuid

        self.log.debug("sends cmd event : {} on topic: {}"
                       .format(event.__class__.__name__, topic))

        cmdDesc = msgs.CmdDesc()
        cmdDesc.type = "event"
        cmdDesc.func_name = "event"
        cmdDesc.serialization_type = msgs.CmdDesc.PICKLE

        data = event
        msgContainer = [topic, cmdDesc, data]
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
