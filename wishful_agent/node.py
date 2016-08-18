import logging
from .common import ControllableUnit

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz}@tkn.tu-berlin.de"


class Device(ControllableUnit):
    def __init__(self, name, node):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.name = name
        self.node = node

    def send_msg(self, ctx):
        self.log.info("{}:{}".format(ctx._upi_type, ctx._upi))
        ctx._iface = self.name
        ctx._device = self.name
        response = self.node.send_msg(ctx)
        self._clear_call_context()
        return response


class Node(ControllableUnit):
    def __init__(self, uuid):
        super().__init__()
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.uuid = uuid
        self.moduleManager = None
        self.devices = []

    def get_devices(self):
        return self.devices

    def get_device(self, devId):
        if self.devices:
            return self.devices[devId]
        else:
            return None

    def send_msg(self, ctx):
        self.log.info("{}:{}".format(ctx._upi_type, ctx._upi))
        ctx._scope = self
        response = self.moduleManager.send_cmd(ctx)
        self._clear_call_context()
        return response


class NodeGroup(object):
    """docstring for NodeGroup"""

    def __init__(self):
        super(NodeGroup, self).__init__()
