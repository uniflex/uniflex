import logging
import time
import sys
import zmq.green as zmq
import wishful_framework as msgs
try:
   import cPickle as pickle
except:
   import pickle

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class TransportChannel(object):
    def __init__(self, agent):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self.poller = zmq.Poller()
        self.context = zmq.Context()
        self.socket_sub = self.context.socket(zmq.SUB) # for downlink communication with controller
        self.socket_sub.setsockopt(zmq.SUBSCRIBE,  self.agent.uuid)
        self.socket_sub.setsockopt(zmq.LINGER, 100)
        self.socket_pub = self.context.socket(zmq.PUB) # for uplink communication with controller

        #register module socket in poller
        self.poller.register(self.socket_sub, zmq.POLLIN)


    def subscribe_to(self, topic):
        self.ul_socket.setsockopt(zmq.SUBSCRIBE, topic)
 
    def set_recv_callback(self, callback):
        self.recv_callback = callback

    def send_msg_to_controller(self, msgContainer):
        ## stamp with my uuid
        cmdDesc = msgs.CmdDesc()
        cmdDesc.ParseFromString(msgContainer[1])
        cmdDesc.caller_id = self.uuid
        msgContainer[1] = cmdDesc.SerializeToString()
        self.socket_pub.send_multipart(msgContainer)

    def start(self):
        socks = dict(self.poller.poll())
        if self.ul_socket in socks and socks[self.ul_socket] == zmq.POLLIN:
            try:
                msgContainer = self.ul_socket.recv_multipart(zmq.NOBLOCK)
            except zmq.ZMQError:
                raise zmq.ZMQError

            assert len(msgContainer) == 3
            group = msgContainer[0]
            cmdDesc = msgs.CmdDesc()
            cmdDesc.ParseFromString(msgContainer[1])
            msg = msgContainer[2]
            if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
                msg = pickle.loads(msg)

            msgContainer[0] = group
            msgContainer[1] = cmdDesc
            msgContainer[2] = msg
            self.recv_callback(msgContainer)


    def stop(self):
        self.ul_socket.setsockopt(zmq.LINGER, 0)
        self.dl_socket.setsockopt(zmq.LINGER, 0)
        self.ul_socket.close()
        self.dl_socket.close()
        self.context.term() 