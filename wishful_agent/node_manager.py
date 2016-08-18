import logging
import wishful_upis as upis
import wishful_framework as wishful_module
from .node import Node


__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz}@tkn.tu-berlin.de"


@wishful_module.build_module
class LocalNodeManager(wishful_module.AgentModule):
    def __init__(self, agent):
        super(LocalNodeManager, self).__init__()
        self.log = logging.getLogger('LocalNodeManager')
        self.agent = agent
        self.moduleManager = []
        self.node = None

    def my_start(self):
        self.node = Node()
        self.node.id = self.agent.uuid
        self.node.modules = self.agent.moduleManager.modules
        self.send_event(upis.mgmt.NewNodeEvent(self.node))

    def my_stop(self):
        self.send_event(upis.mgmt.NodeExitEvent(self.node, 0))
