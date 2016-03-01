import logging
import zmq
import random
import sys
import time
import threading
try:
   import cPickle as pickle
except:
   import pickle

from wishful_framework.modules import *
from wishful_framework import msgs

__author__ = "Piotr Gawlowicz, Mikolaj Chwalisz"
__copyright__ = "Copyright (c) 2015, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz, chwalisz}@tkn.tu-berlin.de"


class AgentModule(WishfulModule):
    def __init__(self):
        super(AgentModule, self).__init__()


    def send_to_module(self, msgContainer):
        self.log.debug("Module {} received cmd".format(self.__class__.__name__))
        result = self.process_cmds(msgContainer)
        self.log.debug("Module {} return value".format(self.__class__.__name__))
        return result


    def process_cmds(self, msgContainer):
        assert len(msgContainer) == 3
        dest = msgContainer[0]
        cmdDesc = msgContainer[1]
        kwargs = msgContainer[2]
        
        self.log.debug("Process msg: {}:{}".format(cmdDesc.type, cmdDesc.func_name))
        command = cmdDesc.func_name

        #set interface before UPI function call, so we can use self.interface in function
        self.interface = None
        if cmdDesc.HasField('interface'):
            self.interface = cmdDesc.interface

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
            dest = "controller"
            respDesc = msgs.CmdDesc()
            respDesc.type = cmdDesc.type
            respDesc.func_name = cmdDesc.func_name
            respDesc.call_id = cmdDesc.call_id
            
            #Serialize return value
            respDesc.serialization_type = msgs.CmdDesc.PICKLE
            serialized_retVal = pickle.dumps(retVal)
            response = [dest, respDesc.SerializeToString(), serialized_retVal]

        return response