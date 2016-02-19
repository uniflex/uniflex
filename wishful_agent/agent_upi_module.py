import logging
import zmq
import random
import sys
import time
import wishful_framework as msgs
try:
   import cPickle as pickle
except:
   import pickle

__author__ = "Piotr Gawlowicz, Mikolaj Chwalisz"
__copyright__ = "Copyright (c) 2015, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz, chwalisz}@tkn.tu-berlin.de"


class bind_function(object):
    def __init__(self, upiFunc):
        fname = upiFunc.__name__
        self.upi_fname = set([fname])

    def __call__(self, f):
        f._upi_fname = self.upi_fname
        return f


class on_start(object):
    def __init__(self):
        self.onStart = True

    def __call__(self, f):
        f._onStart = self.onStart
        return f


class on_exit(object):
    def __init__(self):
        self.onExit = True

    def __call__(self, f):
        f._onExit = self.onExit
        return f


class on_connect(object):
    def __init__(self):
        self.onExit = True

    def __call__(self, f):
        f._onExit = self.onExit
        return f


class on_connected(object):
    def __init__(self):
        self.onExit = True

    def __call__(self, f):
        f._onExit = self.onExit
        return f


class on_disconnect(object):
    def __init__(self):
        self.onExit = True

    def __call__(self, f):
        f._onExit = self.onExit
        return f


def build_module(module_class):
    original_methods = module_class.__dict__.copy()
    for name, method in original_methods.iteritems():
        if hasattr(method, '_upi_fname'):
            #if alias is the same as UPI function name do nothing
            #create alias
            for falias in method._upi_fname - set(original_methods):
                setattr(module_class, falias, method)
    return module_class


class AgentUpiModule(object):
    def __init__(self, port=None):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        if port:
            self.port = port
            self.log.debug("Connect to Agent on port: {0}".format(port))

            # Connect to WiSHFUL Agent
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.PAIR)
            self.socket.setsockopt(zmq.LINGER, 100)
            self.socket.connect("tcp://localhost:%s" % port)

    def process_msgs(self, msgContainer):
        assert len(msgContainer) == 3
        group = msgContainer[0]
        cmdDesc = msgs.CmdDesc()
        cmdDesc.ParseFromString(msgContainer[1])
        msg = msgContainer[2]
        
        if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
            kwargs = pickle.loads(msg)

        self.log.debug("Process msg: {}:{}".format(cmdDesc.type, cmdDesc.func_name))
        command = cmdDesc.func_name

        response = None
        #TODO: check if function is available
        func = getattr(self, command)

        my_args = ()
        if kwargs:
            my_args = kwargs['args']
            my_kwargs = kwargs['kwargs']

        retVal = func(*my_args)

        #TODO: add exception handling
        #try:
        #    retVal = func(*my_args)
        #except Exception as e:
        #    retVal = e

        if retVal is not None:
            group = "RESPONSE"
            respDesc = msgs.CmdDesc()
            respDesc.type = cmdDesc.type
            respDesc.func_name = cmdDesc.func_name
            respDesc.call_id = cmdDesc.call_id
            
            #Serialize return value
            respDesc.serialization_type = msgs.CmdDesc.PICKLE
            serialized_retVal = pickle.dumps(retVal)
            response = [group, respDesc.SerializeToString(), serialized_retVal]

        return response

    def start_receive_msgs(self, socket):
        while True:
            msgContainer = socket.recv_multipart()

            assert len(msgContainer) == 3
            group = msgContainer[0]
            cmdDesc = msgs.CmdDesc()
            cmdDesc.ParseFromString(msgContainer[1])
            msg = msgContainer[2]

            self.log.debug("Recived msg: {}:{}:{}".format(group, cmdDesc.type, cmdDesc.func_name))

            response = self.process_msgs(msgContainer)

            if response:
                self.log.debug("Sending response: {0}".format(response))
                socket.send_multipart(response)

    def run(self):
        self.log.debug("Module starts".format())
        try:
            self.start_receive_msgs(self.socket)
        except KeyboardInterrupt:
            self.log.debug("Module exits")