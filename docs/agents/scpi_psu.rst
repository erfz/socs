.. highlight:: rst

.. _scpi_psu:

==================
SCPI PSU Agent
==================

This agent uses Standard Commands for Programmable Instruments (SCPI)
It works for many power supplies, including the Keithley 2230G
and BK Precision 9130. It connects to the PSU over ethernet, and allows
users to set current, voltage, and turn channels on/off. It also allows for
live monitoring of the PSU output.

.. argparse::
    :filename: ../agents/scpi_psu/scpi_psu_agent.py
    :func: make_parser
    :prog: python3 scpi_psu_agent.py


Configuration File Examples
---------------------------
Below are configuration examples for the ocs config file and for running the
Agent in a docker container.

ocs-config
``````````
To configure the SCPI PSU Agent we need to add a block to our ocs
configuration file. Here is an example configuration block using all of
the available arguments::

      {'agent-class': 'ScpiPsuAgent',
        'instance-id': 'psuK',
        'arguments': [
          ['--ip-address', '10.10.10.5'],
          ['--gpib-slot', '1']
          ]},

Most power supplies (including the Keithley 2230G and BK Precision 9130)
have GPIB ports rather than ethernet ports. Therefore a GPIB-to-ethernet
converter is required, and the gpib slot must be specified in the ocs
configuration file. The IP address is then associated with the converter.

Docker
``````
The SCPI PSU Agent should be configured to run in a Docker container.
An example docker-compose service configuration is shown here::

  ocs-psuK:
    image: simonsobs/ocs-scpi-psu-agent:latest
    hostname: ocs-docker
    network_mode: "host"
    volumes:
      - ${OCS_CONFIG_DIR}:/config:ro
    command:
      - "--instance-id=psuK"

Example Client
--------------
Below is an example client demonstrating full agent functionality.
Note that all tasks can be run even while the data acquisition process
is running.::

    from ocs.matched_client import MatchedClient

    #Initialize the power supply
    psuK = MatchedClient('psuK', args=[])
    psuK.init.start()
    psuK.init.wait()

    #Turn on channel 1
    psuK.set_output.start(channel = 1, state=True)
    psuK.set_output.wait()

    #Set channel 1 voltage
    psuK.set_voltage.start(channel=1, volts=30)
    psuK.set_voltage.wait()

    #Set channel 1 current
    psuK.set_current.start(channel=1, current=0.1)
    psuK.set_current.wait()

    #Get instantaneous reading of current and voltage output
    statusK, messageK, sessionK = psuK.monitor_output.status()
    print(sessionK['data']['data'])

    #Start live monitoring of current and voltage output
    statusK, messageK, sessionK = psuK.monitor_output.start()
    print(sessionK)


Agent API
---------

.. autoclass:: agents.scpi_psu.scpi_psu_agent.ScpiPsuAgent
    :members: monitor_output, set_voltage, set_current, set_output
