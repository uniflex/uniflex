import sys
import time
import uuid
import logging

from .common import get_ip_address
from .module_manager import ModuleManager
from .transport_channel import TransportChannel
from .broker import Broker
from .node_manager import NodeManager

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class Agent(object):
    def __init__(self):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.config = None
        self.uuid = str(uuid.uuid4())
        self.name = None
        self.info = None
        self.iface = None
        self.ip = None

        self.broker = None

        # extention of event bus
        self.transport = None

        # module manager
        self.moduleManager = ModuleManager(self)

        # node manager
        self.nodeManager = NodeManager(self)

        self.moduleManager._nodeManager = self.nodeManager
        self.nodeManager._moduleManager = self.moduleManager

    def load_config(self, config, configPath=None):
        self.log.debug("Config: {}, path: {}".format(config, configPath))

        if configPath:
            sys.path.append(configPath)

        agent_config = config.get('config', None)

        if not agent_config:
            self.log.error("Config file not provided!")
            return

        self.name = agent_config.get('name', None)
        self.info = agent_config.get('info', None)
        self.iface = agent_config.get('iface', None)
        if self.iface:
            self.ip = get_ip_address(self.iface)

        sub = agent_config.get('sub', None)
        pub = agent_config.get('pub', None)

        self.agentType = agent_config.get('type', None)

        if self.agentType != 'local':
            self.transport = TransportChannel(self)
            self.moduleManager.add_module_obj(
                "transport_channel", self.transport)
            self.transport.set_downlink(sub)
            self.transport.set_uplink(pub)

            client_key = agent_config.get('client_key', None)
            server_key = agent_config.get('server_key', None)
            if (client_key is not None) and (server_key is not None):
                self.transport.set_certificates(client_key, server_key)

            self.transport._nodeManager = self.nodeManager
            self.transport._moduleManager = self.moduleManager
            self.nodeManager._transportChannel = self.transport
            self.moduleManager._transportChannel = self.transport

        self.nodeManager.create_local_node(self)

        if "broker" in config:
            broker_config = config["broker"]
            xpub = broker_config["xpub"]
            xsub = broker_config["xsub"]
            self.log.info("Start Broker with XPUB: {}, XSUB: {}"
                          .format(xpub, xsub))
            server_key = broker_config.get('server_key')
            client_keys = broker_config.get('client_keys')
            self.broker = Broker(xpub, xsub, server_key, client_keys)
            # TODO: start broker in separate process
            self.broker.setDaemon(True)
            self.broker.start()

        # load control programs
        controlApps = config.get('control_applications', {})
        for controlAppName, params in controlApps.items():
            pyModuleName = params.get('module', None)
            if not pyModuleName:
                myfile = params.get('file', None)
                pyModuleName = myfile.split('.')[0]

            pyClassName = params.get('class_name', None)
            kwargs = params.get('kwargs', {})

            self.moduleManager.register_module(
                controlAppName, pyModuleName, pyClassName,
                None, kwargs)

        # load modules
        modules = config.get('modules', {})
        for moduleName, m_params in modules.items():

            devices = m_params.get('devices', [])
            kwargs = m_params.get('kwargs', {})
            pyModuleName = m_params.get('module', None)
            className = m_params.get('class_name', None)

            if devices:
                for device in devices:
                    self.moduleManager.register_module(
                        moduleName, pyModuleName, className,
                        device, kwargs)
            else:
                self.moduleManager.register_module(
                    moduleName, pyModuleName, className,
                    None, kwargs)

    def run(self):
        self.log.debug("Agent starts all modules".format())
        # nofity START to modules
        self.moduleManager.start()
        try:
            while True:
                time.sleep(1)
        except:
            self.stop()
            # TODO: find better way to wait for all modules to exit
            # check if thay are _enabled?
            time.sleep(0.5)

    def stop(self):
        self.log.debug("Stop all modules")
        if self.broker:
            self.broker.stop()
        # nofity EXIT to modules
        self.moduleManager.exit()
        self.log.debug("STOP AGENT")
