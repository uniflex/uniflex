Running examples
================

1. Only local node::

    cd ./examples/simple_controller
    uniflex-agent --config ./config_local.yaml

2. Global and local nodes (run with -v for debug mode)::

    # start global node
    cd ./examples/simple_controller
    uniflex-agent --config ./config_master.yaml

    # start local node
    cd ./examples/simple_controller
    uniflex-agent --config ./config_slave.yaml
