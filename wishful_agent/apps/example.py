import logging
import datetime
import random
import wishful_upis as upis
import wishful_framework as wishful_module
from wishful_agent.timer import TimerEventSender


__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2016, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz}@tkn.tu-berlin.de"


class PeriodicEvaluationTimeEvent(upis.mgmt.TimeEvent):
    def __init__(self):
        super().__init__()


@wishful_module.build_module
class MyController(wishful_module.ControllerModule):
    def __init__(self, arg):
        super(MyController, self).__init__()
        self.log = logging.getLogger('MyController')
        self.arg = arg
        self.running = False
        self.nodes = []

        self.timeInterval = 10
        self.timer = TimerEventSender(self, PeriodicEvaluationTimeEvent)
        self.timer.start(self.timeInterval)

    @wishful_module.on_start()
    def my_start_function(self):
        print("start control app")
        self.running = True

    @wishful_module.on_exit()
    def my_stop_function(self):
        print("stop control app")
        self.running = False

    @wishful_module.on_event(upis.mgmt.NewNodeEvent)
    def add_node(self, event):
        node = event.node
        self.nodes.append(node)
        self.log.info("Added new node: {}".format(node))

        retVal = node.net.create_packetflow_sink(port=1234)
        print(retVal)
        # node.net.add_route()

        devs = node.get_devices()
        for dev in devs:
            print("Dev: ", dev)

        device = node.get_device(0)
        device.radio.set_power(15)
        # device.radio.tx_power = 15
        device.radio.set_channel(random.randint(1, 11))
        # device.radio.add_interface(name="wlan0")
        # device.radio.set_mode(iface="wlan0", mode="STA")
        # device.radio.connect(iface="wlan0", ssid="1234")
        device.enable_event(upis.radio.PacketLossEvent)
        self.packetLossEventsEnabled = True
        device.start_service(
            upis.radio.SpectralScanService(rate=1000, f_range=[2200, 2500]))
        self.spectralScanStarted = True

        # remote rule
        # self.myRuleId = device.add_rule(
        # dataSource=upis.radio.SpectralScanService(
        # rate=1000, f_range=[2200, 2500]),
        #                 cb=rule_matched)
        # local rule
        # self.add_rule()

    """
    @wishful_module.on_event(upis.mgmt.RuleMatched)
    def rule_matched(self, event):
        rule = event.rule
        if rule.id == self.myRuleId:
            pass
    """
    @wishful_module.on_event(upis.mgmt.NodeExitEvent)
    def remove_node(self, event):
        node = event.node
        reason = event.reason
        if node in self.nodes:
            self.nodes.remove(node)
            self.log.info("Node: {} removed, reason: {}".format(node, reason))

    @wishful_module.on_event(upis.radio.PacketLossEvent)
    def serve_packet_loss_event(self, event):
        node = event.node
        device = event.device
        self.log.info("Packet loss in node {}, dev: {}".format(node, device))

    @wishful_module.on_event(upis.radio.SpectralScanSampleEvent)
    def serve_spectral_scan_sample(self, event):
        sample = event.sample
        node = event.node
        device = event.device
        self.log.info("New SpectralScan Sample:{} from node {}, device: {}"
                      .format(sample, node, device))

    def default_cb(self, data):
        node = data.node
        dev = data.device
        msg = data.msg
        print("Default Callback: "
              "Node: {}, Dev: {}, Data: {}"
              .format(node, dev, msg))

    def get_power_cb(self, data):
        node = data.node
        dev = data.device
        msg = data.msg
        print("Power in "
              "Node: {}, Dev: {}, was set to: {}"
              .format(node, dev, msg))

    @wishful_module.on_event(PeriodicEvaluationTimeEvent)
    def periodic_evaluation(self, event):
        # go over collected samples, etc....
        # make some decisions, etc...
        # descriptor accumulates samples
        # ruleDescriptor.get_samples(-10)
        # eventDescriptor.get_events(-5)
        # serviceDescriptor.get_samples(-100)
        # cannot run indifinielety

        print("Periodic Evaluation")
        print("Connected nodes", [str(node) for node in self.nodes])
        self.timer.start(self.timeInterval)

        node = self.nodes[0]
        if not node:
            return

        device = node.get_device(0)

        if self.packetLossEventsEnabled:
            device.disable_event(upis.radio.PacketLossEvent)
            self.packetLossEventsEnabled = False
        else:
            device.enable_event(upis.radio.PacketLossEvent)
            self.packetLossEventsEnabled = True

        if self.spectralScanStarted:
            device.stop_service(
                upis.radio.SpectralScanService(rate=100, f_range=[2200, 2500]))
            self.spectralScanStarted = False
        else:
            device.start_service(
                upis.radio.SpectralScanService)
            self.spectralScanStarted = True

        # execute non-blocking function immediately
        node.blocking(False).device("phy0").radio.set_power(12)

        # execute non-blocking function immediately, with specific callback
        node.callback(self.get_power_cb).radio.device("phy0").get_power()

        # schedule non-blocking function delay
        node.delay(3).callback(self.default_cb).net.create_packetflow_sink(port=1234)

        # schedule non-blocking function exec time
        exec_time = datetime.datetime.now() + datetime.timedelta(seconds=3)
        node.exec_time(exec_time).radio.device(
            "phy0").set_channel(channel=random.randint(1, 11))

        # execute blocking function immediately
        result = node.radio.device("phy0").get_channel()
        print("{} Channel is: {}".format(datetime.datetime.now(), result))

        # exception handling, clean_per_flow_tx_power_table implementation
        # raises exception
        try:
            device.radio.clean_per_flow_tx_power_table()
        except Exception as e:
            print("{} !!!Exception!!!: {}".format(
                datetime.datetime.now(), e))
