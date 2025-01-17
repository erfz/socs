.. highlight:: rst

.. _smurf_stream_simulator:

======================
SMuRF Stream Simulator
======================

The SMuRF Stream Simulator is meant to mock a SMuRF streamer, for cases when
you want to test something and you do not have access to a SMuRF. It
establishes a G3NetworkSender and sends simulated timestreams over it. You can
connect the timestream aggregator to it and simulate recording data to disk in
.g3 files.

.. argparse::
    :filename: ../agents/smurf_stream_simulator/smurf_stream_simulator.py
    :func: make_parser
    :prog: python3 smurf_stream_simulator.py

Configuration File Examples
---------------------------
Below are configuration examples for the ocs config file and for running the
simulator in a docker container.

ocs-config
``````````
To configure the simulator we need to add a SmurfStreamSimulator block to our
ocs configuration file. Here is an example configuration block
using all of the available arguments::

      {'agent-class': 'SmurfStreamSimulator',
       'instance-id': 'smurf-stream',
       'arguments': [['--auto-start', True],
                     ['--port', '50000'],
                     ['--num_chans', '528'],
                     ['--stream-id', 'stream_sim']]},

Docker
``````
The simulator should be configured to run in a Docker container. An example
docker-compose service configuration is shown here::

  smurf-stream-sim:
    image: simonsobs/smurf-stream-sim
    hostname: ocs-docker
    ports:
      - "50000:50000"
    volumes:
      - ${OCS_CONFIG_DIR}:/config:ro

Agent API
---------

.. autoclass:: agents.smurf_stream_simulator.smurf_stream_simulator.SmurfStreamSimulator
    :members: start_background_streamer, stop_background_streamer, set_stream_on, set_stream_off
