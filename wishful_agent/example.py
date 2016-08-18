import logging
import datetime
import random
import wishful_upis as upis
import wishful_framework as wishful_module
from .node import NodeGroup
from .timer import TimerEventSender


__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2016, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz}@tkn.tu-berlin.de"


def print_response(node, data):
    print("{} Print response : "
          "NodeIP:{}, Result:{}"
          .format(datetime.datetime.now(), node.ip, data))


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
        self.apNodeGroup = NodeGroup()

        self.timeInterval = 10
        self.timer = TimerEventSender(self, PeriodicEvaluationTimeEvent)
        self.timer.start(self.timeInterval)

    @wishful_module.on_start()
    def my_start_function(self):
        print("start control loop")
        self.running = True

    @wishful_module.on_exit()
    def my_stop_function(self):
        print("stop control loop")
        self.running = False

    @wishful_module.on_event(upis.mgmt.NewNodeEvent)
    def add_node(self, event):
        node = event.node
        self.nodes.append(node)
        self.log.info("Added new node: {}".format(node))

        node.net.create_packetflow_sink(port=1234)
        # node.net.add_route()

        devs = node.get_devices()
        for dev in devs:
            print("Dev: ", dev)

        device = node.get_device(0)
        device.radio.set_power(15)
        device.radio.set_channel(random.randint(1, 11))
        # device.radio.add_interface(name="wlan0")
        # device.radio.set_mode(iface="wlan0", mode="STA")
        # device.radio.connect(iface="wlan0", ssid="1234")
        # device.enable_event(upis.radio.PacketLossEvent())
        device.start_service(
            upis.radio.SpectralScanService(rate=1000, f_range=[2200, 2500]))

        # remote rule
        # self.myRuleId = device.add_rule(
        #                        dataSource=upis.radio.SpectralScanService(rate=1000, f_range=[2200, 2500]),
        #                                cb=rule_matched)
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
        print("Packet Loss Event Handler")
        '''
        device = event.device
        iface = event.iface
        peerIface = device.get_peer()

        if peerIface.get_type() == "STA":
            txPower = peerIface.get_tx_power()
            # or txPower = peerIface.txPower
            # or txPower = peerIface.get_attribute(upi.radio.TxPower, ctx=None)
            txPower = txPower + 1
            peerIface.set_tx_power(txPower)
            # or peerIface.txPower = txPower
            # ctx = CallingContext()
            # ctx.blocking = True
            # or peerIface.set_attribute(upi.radio.TxPower, txpower, ctx=None)

        elif peerIface.get_type() == "AP":
            macAddr = device.get_mac()
            txPower = peerIface.get_tx_power_for_sta(macAddr)
            txPower = txPower + 1
            peerIface.set_tx_power_for_sta(macAddr, txPower)
        '''
        # device.stop_event(upis.radio.PacketLossEvent)

    @wishful_module.on_event(upis.radio.SpectralScanSampleEvent)
    def serve_spectral_scan_sample(self, event):
        sample = event.sample
        node = event.node
        dev = event.dev

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

        # execute non-blocking function immediately
        node.blocking(False).device("phy0").radio.set_power(12)
        device = node.get_device(0)
        response = device.radio.set_power(8)
        print(response)

        # execute non-blocking function immediately, with specific callback
        node.callback(print_response).radio.device("phy0").get_power()

        # schedule non-blocking function delay
        node.delay(3).net.create_packetflow_sink(port=1234)

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
            node.radio.device("phy0").clean_per_flow_tx_power_table()
        except Exception as e:
            print("{} !!!Exception!!!: {}".format(
                datetime.datetime.now(), e))
