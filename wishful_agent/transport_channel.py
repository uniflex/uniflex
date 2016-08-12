import logging
import sys
import zmq.green as zmq
import threading
import dill  # for pickling what standard pickle can’t cope with
try:
    import cPickle as pickle
except:
    import pickle

import wishful_framework as msgs
import wishful_framework as wishful_module
import wishful_upis as upis

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


@wishful_module.build_module
class TransportChannel(wishful_module.AgentModule):
    def __init__(self, agent):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self.controllerDL = None
        self.controllerUL = None

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

    @wishful_module.on_event(upis.mgmt.ConnectToControllerEvent)
    def connect(self, event):
        if self.controllerDL and self.controllerUL:
            try:
                self.ul_socket.disconnect(self.controllerUL)
                self.dl_socket.disconnect(self.controllerDL)
            except:
                pass

        self.controllerDL = event.dlink
        self.controllerUL = event.ulink
        self.ul_socket.connect(self.controllerUL)
        self.dl_socket.connect(self.controllerDL)

    @wishful_module.on_event(upis.mgmt.DisconnectControllerEvent)
    def disconnect(self, event):
        # disconnect
        if self.controllerDL and self.controllerUL:
            try:
                self.ul_socket.disconnect(self.controllerUL)
                self.dl_socket.disconnect(self.controllerDL)
            except:
                pass

    @wishful_module.on_event(upis.mgmt.SubscribeTopicEvent)
    def subscribe_to(self, event):
        topic = event.topic
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

    @wishful_module.on_event(upis.mgmt.SendControllMgsEvent)
    def send_ctr_to_controller_event(self, event):
        self.send_ctr_to_controller(event.msg)

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

    @wishful_module.on_event(upis.mgmt.SendMgsEvent)
    def send_to_controller_event(self, event):
        self.send_to_controller(event.msg)

    @wishful_module.on_event(upis.mgmt.ReturnValueEvent)
    def serve_return_value_event(self, event):
        dest = event.dest
        cmdDesc = event.cmdDesc
        value = event.msg
        self.log.debug("Received ReturnValueEvent with dest: {}"
                       " cmd: {}, value: {}". format(dest,
                                                     cmdDesc.func_name, value))
        self.send_to_controller([dest, cmdDesc, value])

    def send_to_controller(self, msgContainer):
        msgContainer[0] = str(self.agent.controllerUuid)
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

    def process_msgs(self, msgContainer):
        cmdDesc = msgContainer[1]
        msg = msgContainer[2]
        self.log.debug(
            "Agent received message: {} from controller".format(cmdDesc.type))

        if cmdDesc.type == msgs.get_msg_type(msgs.NewNodeAck):
            event = upis.mgmt.ControllerConnectionCompletedEvent(cmdDesc, msg)
            self.send_event(event)

        elif cmdDesc.type == msgs.get_msg_type(msgs.HelloMsg):
            self.send_event(upis.mgmt.HelloMsgEvent())

        # TODO: move it to executor
        # elif cmdDesc.type == msgs.get_msg_type(msgs.RuleDesc):
        #    self.serve_rule(msgContainer)
        else:
            event = upis.mgmt.CommandEvent(msgContainer[0],
                                           msgContainer[1], msgContainer[2])
            self.send_event(event)

    def my_start(self):
        while True:
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

    def my_stop(self):
        try:
            self.dl_socket.setsockopt(zmq.LINGER, 0)
            self.ul_socket.setsockopt(zmq.LINGER, 0)
            self.dl_socket.close()
            self.ul_socket.close()
            self.context.term()
        except:
            pass
