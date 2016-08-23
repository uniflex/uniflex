import sys
import zmq
import time
import logging
import threading
import dill  # for pickling what standard pickle can’t cope with
try:
    import cPickle as pickle
except:
    import pickle

from .timer import TimerEventSender
import wishful_framework as msgs
import wishful_framework as wishful_module
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
class SlaveTransportChannel(wishful_module.AgentModule):
    def __init__(self, agent):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self.forceStop = False

        self.connectedToController = False
        self.echoMsgInterval = 3
        self.echoTimeOut = 10
        self.helloMsgTimer = TimerEventSender(self, SendHelloMsgTimeEvent)
        self.helloMsgTimeoutTimer = TimerEventSender(self,
                                                     HelloMsgTimeoutEvent)

        self.controllerDL = None
        self.controllerUL = None
        self.controllerUuid = None

        self.uplinkSocketLock = threading.Lock()
        self.poller = zmq.Poller()
        self.context = zmq.Context()

        # for downlink communication with controller
        self.dl_socket = self.context.socket(zmq.SUB)
        if sys.version_info.major >= 3:
            self.dl_socket.setsockopt_string(zmq.SUBSCRIBE, self.agent.uuid)
        else:
            self.dl_socket.setsockopt(zmq.SUBSCRIBE, self.agent.uuid)
        self.dl_socket.setsockopt(zmq.LINGER, 100)

        # for uplink communication with controller
        self.ul_socket = self.context.socket(zmq.PUB)

        # register module socket in poller
        self.poller.register(self.dl_socket, zmq.POLLIN)

    @wishful_module.on_start()
    def start_module(self):
        thread = threading.Thread(target=self.recv_msgs)
        thread.setDaemon(True)
        thread.start()

    @wishful_module.on_exit()
    def stop_module(self):
        self.forceStop = True
        self.terminate_connection_to_controller()
        try:
            self.dl_socket.setsockopt(zmq.LINGER, 0)
            self.ul_socket.setsockopt(zmq.LINGER, 0)
            self.dl_socket.close()
            self.ul_socket.close()
            self.context.term()
        except:
            pass

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
        self.connect(dlink, uplink)

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

            if module.device:
                deviceDesc = msgs.Device()
                deviceDesc.id = 0  # TODO: set it properly
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

        self.log.debug("Agent sends context-setup request to controller")
        time.sleep(1)  # wait for zmq to exchange topics
        self.send_ctr_to_controller(msgContainer)

    def connect(self, dlink, ulink):
        if self.controllerDL and self.controllerUL:
            try:
                self.ul_socket.disconnect(self.controllerUL)
                self.dl_socket.disconnect(self.controllerDL)
            except:
                pass

        self.controllerDL = dlink
        self.controllerUL = ulink
        self.ul_socket.connect(self.controllerUL)
        self.dl_socket.connect(self.controllerDL)

    def setup_connection_to_controller_complete(self, cmdDesc, data):
        msg = msgs.NewNodeAck()
        msg.ParseFromString(data)

        self.log.debug("Agent received msgType: {} with status: {}".format(
            cmdDesc.type, msg.status))

        self.log.debug(
            "Agent connects to controller and subscribes to received topics")
        self.subscribe_to(self.agent.uuid)

        for topic in msg.topics:
            self.subscribe_to(topic)

        self.connectedToController = True
        self.controllerUuid = msg.controller_uuid
        # stop discovery module
        # and notify CONNECTED to modules
        event = upis.mgmt.ControllerConnectedEvent(msg.controller_uuid)
        self.send_event(event)

        # start sending hello msgs
        self.helloMsgTimer.start(self.echoMsgInterval)
        self.helloMsgTimeoutTimer.start(self.echoTimeOut)

    def disconnect(self):
        if self.controllerDL and self.controllerUL:
            try:
                self.ul_socket.disconnect(self.controllerUL)
                self.dl_socket.disconnect(self.controllerDL)
            except:
                pass

    def subscribe_to(self, topic):
        self.log.debug("Agent subscribes to topic: {}".format(topic))
        if sys.version_info.major >= 3:
            self.dl_socket.setsockopt_string(zmq.SUBSCRIBE, str(topic))
        else:
            self.dl_socket.setsockopt(zmq.SUBSCRIBE, str(topic))

    def send_uplink(self, msgContainer):
        # TODO: it is quick fix; find better solution with socket per thread
        self.uplinkSocketLock.acquire()
        try:
            self.ul_socket.send_multipart(msgContainer)
        finally:
            self.uplinkSocketLock.release()

    def send_ctr_to_controller(self, msgContainer):
        msgContainer[0] = msgContainer[0].encode('utf-8')
        # stamp with my uuid
        cmdDesc = msgContainer[1]
        msg = msgContainer[2]

        cmdDesc.caller_id = self.agent.uuid
        msgContainer[1] = cmdDesc.SerializeToString()

        if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
            try:
                msg = pickle.dumps(msg)
            except:
                msg = dill.dumps(msg)
        elif cmdDesc.serialization_type == msgs.CmdDesc.PROTOBUF:
            msg = msg.SerializeToString()

        msgContainer[2] = msg

        self.send_uplink(msgContainer)

    def send_to_controller(self, msgContainer):
        msgContainer[0] = str(self.controllerUuid)
        msgContainer[0] = msgContainer[0].encode('utf-8')
        # stamp with my uuid
        cmdDesc = msgContainer[1]
        msg = msgContainer[2]

        cmdDesc.caller_id = self.agent.uuid
        msgContainer[1] = cmdDesc.SerializeToString()

        if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
            try:
                msg = pickle.dumps(msg)
            except:
                msg = dill.dumps(msg)
        elif cmdDesc.serialization_type == msgs.CmdDesc.PROTOBUF:
            msg = msg.SerializeToString()

        msgContainer[2] = msg

        self.send_uplink(msgContainer)

    @wishful_module.on_event(SendHelloMsgTimeEvent)
    def send_hello_msg_to_controller(self, event):
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
        self.send_to_controller(msgContainer)

        # reschedule hello msg
        self.helloMsgTimer.start(self.echoMsgInterval)

    @wishful_module.on_event(HelloMsgTimeoutEvent)
    def connection_to_controller_lost(self, event):
        self.log.debug(
            "Agent lost connection with controller,"
            " stop sending EchoMsg".format())
        self.helloMsgTimer.cancel()

        self.connectedToController = False
        self.controllerUuid = None
        # notify Connection Lost
        event = upis.mgmt.ControllerLostEvent(0)
        self.send_event(event)
        # notify DISCONNECTED
        self.disconnect()
        event = upis.mgmt.DisconnectControllerEvent()
        self.send_event(event)

    def serve_hello_msg(self, event):
        self.log.debug("Agent received HELLO MESSAGE from controller".format())
        self.helloMsgTimeoutTimer.cancel()
        self.helloMsgTimeoutTimer.start(self.echoTimeOut)

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
        self.send_ctr_to_controller(msgContainer)

    def process_msgs(self, msgContainer):
        cmdDesc = msgContainer[1]
        msg = msgContainer[2]
        self.log.debug(
            "Agent received message: {} from controller".format(cmdDesc.type))

        if cmdDesc.type == msgs.get_msg_type(msgs.NewNodeAck):
            self.setup_connection_to_controller_complete(cmdDesc, msg)

        elif cmdDesc.type == msgs.get_msg_type(msgs.HelloMsg):
            self.serve_hello_msg(upis.mgmt.HelloMsgEvent())

        else:
            event = upis.mgmt.CommandEvent(msgContainer[0],
                                           msgContainer[1], msgContainer[2])
            # self.send_event(event)
            # TODO: perform translation/serialization

    def recv_msgs(self):
        while not self.forceStop:
            socks = dict(self.poller.poll())
            if self.dl_socket in socks and socks[self.dl_socket] == zmq.POLLIN:
                msgContainer = self.dl_socket.recv_multipart()
                assert len(msgContainer) == 3, msgContainer
                dest = msgContainer[0]
                cmdDesc = msgs.CmdDesc()
                cmdDesc.ParseFromString(msgContainer[1])
                msg = msgContainer[2]

                if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
                    msg = pickle.loads(msg)

                msgContainer[0] = dest.decode('utf-8')
                msgContainer[1] = cmdDesc
                msgContainer[2] = msg
                self.process_msgs(msgContainer)


@wishful_module.build_module
class MasterTransportChannel(wishful_module.AgentModule):
    def __init__(self, agent):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self.forceStop = False
        self.downlink = None
        self.uplink = None

        self.context = zmq.Context()
        self.poller = zmq.Poller()

        # one SUB socket for uplink communication over topics
        self.ul_socket = self.context.socket(zmq.SUB)
        if sys.version_info.major >= 3:
            self.ul_socket.setsockopt_string(zmq.SUBSCRIBE, "NEW_NODE")
            self.ul_socket.setsockopt_string(zmq.SUBSCRIBE, "NODE_EXIT")
        else:
            self.ul_socket.setsockopt(zmq.SUBSCRIBE, "NEW_NODE")
            self.ul_socket.setsockopt(zmq.SUBSCRIBE, "NODE_EXIT")

        self.downlinkSocketLock = threading.Lock()
        # one PUB socket for downlink communication over topics
        self.dl_socket = self.context.socket(zmq.PUB)

        # register UL socket in poller
        self.poller.register(self.ul_socket, zmq.POLLIN)

    @wishful_module.on_start()
    def start_module(self):
        self.log.debug(
            "Controller on DL-{}, UP-{}".format(self.downlink, self.uplink))
        self.dl_socket.bind(self.downlink)
        self.ul_socket.bind(self.uplink)

        thread = threading.Thread(target=self.recv_msgs)
        thread.setDaemon(True)
        thread.start()

    @wishful_module.on_exit()
    def stop_module(self):
        self.forceStop = True
        self.ul_socket.setsockopt(zmq.LINGER, 0)
        self.dl_socket.setsockopt(zmq.LINGER, 0)
        self.ul_socket.close()
        self.dl_socket.close()
        self.context.term()

    def set_downlink(self, downlink):
        self.log.debug("Set Downlink: {}".format(downlink))
        self.downlink = downlink

    def set_uplink(self, uplink):
        self.log.debug("Set Uplink: {}".format(uplink))
        self.uplink = uplink

    def subscribe_to(self, event):
        topic = event.topic
        self.log.info("Transport Channel subscribes to topic: {}"
                      .format(topic))
        if sys.version_info.major >= 3:
            self.ul_socket.setsockopt_string(zmq.SUBSCRIBE, str(topic))
        else:
            self.ul_socket.setsockopt(zmq.SUBSCRIBE, str(topic))

    def send_downlink_msg(self, event):
        msgContainer = event.msg
        msgContainer[0] = msgContainer[0].encode('utf-8')
        cmdDesc = msgContainer[1]
        msg = msgContainer[2]

        if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
            try:
                msg = pickle.dumps(msg)
            except:
                msg = dill.dumps(msg)
        elif cmdDesc.serialization_type == msgs.CmdDesc.PROTOBUF:
            msg = msg.SerializeToString()

        msgContainer[1] = cmdDesc.SerializeToString()
        msgContainer[2] = msg

        self.downlinkSocketLock.acquire()
        try:
            self.dl_socket.send_multipart(msgContainer)
        finally:
            self.downlinkSocketLock.release()

    def process_msgs(self, msgContainer):
        cmdDesc = msgContainer[1]
        msg = msgContainer[2]
        self.log.info(
            "Transport Channel received message: {} "
            "from node".format(cmdDesc.type))

        if cmdDesc.type == msgs.get_msg_type(msgs.NewNodeMsg):
            event = upis.mgmt.NewNodeDiscoveredEvent(cmdDesc, msg)
            self.send_event(event)

        elif cmdDesc.type == msgs.get_msg_type(msgs.HelloMsg):
            self.send_event(upis.mgmt.HelloMsgEvent())

        elif cmdDesc.type == msgs.get_msg_type(msgs.NodeExitMsg):
            self.send_event(upis.mgmt.NodeExitEvent())

        else:
            event = upis.mgmt.CommandEvent(msgContainer[0],
                                           msgContainer[1], msgContainer[2])
            # self.send_event(event)
            # perform translation to event

    def recv_msgs(self):
        while not self.forceStop:
            socks = dict(self.poller.poll())
            if self.ul_socket in socks and socks[self.ul_socket] == zmq.POLLIN:
                try:
                    msgContainer = self.ul_socket.recv_multipart(zmq.NOBLOCK)
                except zmq.ZMQError:
                    raise zmq.ZMQError

                assert len(msgContainer) == 3, msgContainer

                dest = msgContainer[0]
                cmdDesc = msgs.CmdDesc()
                cmdDesc.ParseFromString(msgContainer[1])
                msg = msgContainer[2]
                if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
                    try:
                        msg = pickle.loads(msg)
                    except:
                        msg = dill.loads(msg)

                msgContainer[0] = dest.decode('utf-8')
                msgContainer[1] = cmdDesc
                msgContainer[2] = msg

                self.process_msgs(msgContainer)
