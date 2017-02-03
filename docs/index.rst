A Framework for Simplifying Wireless Network Control
====================================================

Classical control and management plane for computer networks is addressing individual parameters of protocol layers within an individual wireless network device.
We argue that this is not sufficient in phase of increasing deployment of highly re-configurable systems, as well as heterogeneous wireless systems co-existing in the same radio spectrum which demand harmonized, frequently even coordinated adaptation of multiple parameters in different protocol layers (cross-layer) in multiple network devices (cross-node).
We propose UniFlex, a framework enabling unified and flexible radio and network control.
It provides an API enabling coordinated cross-layer control and management operation over multiple wireless network nodes.
The controller logic may be implemented either in a centralized or distributed manner.
This allows to place time-sensitive control functions close to the controlled device (i.e., local control application), off-load more resource hungry network application to compute servers and make them work together to control entire network.
The UniFlex framework was prototypically implemented and provided to the research community as open-source.
We evaluated the framework in a number of use-cases, what proved its usability.

.. rubric:: Contents

.. toctree::
   :maxdepth: 2

   installation
   examples

.. rubric:: Indices and tables

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
