import argparse
import os
import time

import numpy as np
import txaio
import yaml

ON_RTD = os.environ.get("READTHEDOCS") == "True"
if not ON_RTD:
    from holog_daq import synth3
    from ocs import ocs_agent, site_config
    from ocs.ocs_twisted import Pacemaker, TimeoutLock


class SynthAgent:
    """
    Agent for connecting to the Synths for holography
    """

    def __init__(self, agent, config_file):

        self.lo_id = None
        self.initialized = False
        self.take_data = False

        self.agent = agent
        self.log = agent.log
        self.lock = TimeoutLock()

        agg_params = {"frame_length": 10 * 60}  # [sec]
        self.agent.register_feed(
            "synth_LO", record=True, agg_params=agg_params, buffer_time=0
        )
        """
        if mode == 'acq':
            self.auto_acq = True
        else:
            self.auto_acq = False
        self.sampling_frequency = float(samp)

        ### register the position feeds
        """
        if config_file == "None":
            raise Exception("No config file specified for the FTS mirror config")
        else:
            config_file_path = os.path.join(os.environ["OCS_CONFIG_DIR"], config_file)
            print(config_file_path)
            with open(config_file_path) as stream:
                self.holog_configs = yaml.safe_load(stream)
                if self.holog_configs is None:
                    raise Exception("No mirror configs in config file.")
                self.log.info(f"Loaded mirror configs from file {config_file_path}")
                self.N_MULT = self.holog_configs.pop("N_MULT", None)
                self.ghz_to_mhz = self.holog_configs.pop("ghz_to_mhz", None)

    def init_synth(self, session, params=None):
        """init_synth(params=None)
        Perform first time setup for communication with Synth.
        """

        if params is None:
            params = {}

        self.log.debug("Trying to acquire lock")
        with self.lock.acquire_timeout(timeout=0, job="init") as acquired:
            # Locking mechanism stops code from proceeding if no lock acquired
            if not acquired:
                self.log.warn(
                    "Could not start init because {} is already running".format(
                        self.lock.job
                    )
                )
                return False, "Could not acquire lock."
            # Run the function you want to run
            self.log.debug("Lock Acquired Connecting to Stages")
            self.lo_id = synth3.get_LOs()

            synth3.set_RF_output(0, 1, self.lo_id) # LO ID, On=1, USB connection ID
            synth3.set_RF_output(1, 1, self.lo_id) # LO ID, On=1, USB connection ID

            # data = {"timestamp": time.time(), "block_name": "synth_LO", "data": {}}

            # data["data"]["F1_status"] = 1
            # data["data"]["F2_status"] = 1

            # self.agent.publish_to_feed("synth_LO", data)
            # session.data.update(data["data"])


        # This part is for the record and to allow future calls to proceed,
        # so does not require the lock
        self.initialized = True

        return True, "Synth Initialized."

    def set_frequencies(self, session, params):
        """
        params: 
            dict: {'freq0': float
                   'freq1': float}
        """

        f1 = params.get("freq1", 0)
        f_offset = params.get("offset", 0)

        F_1 = int(f1 * self.ghz_to_mhz / self.N_MULT) # Convert GHz -> MHz for synthesizers

        print(F_1,F_1+f_offset)

        with self.lock.acquire_timeout(timeout=3, job="set_frqeuencies") as acquired:
            if not acquired:
                self.log.warn(
                    f"Could not set position because lock held by {self.lock.job}"
                )
                return False, "Could not acquire lock"

            synth3.set_f(0, F_1, self.lo_id)
            synth3.set_f(1, F_1+f_offset, self.lo_id)

            data = {"timestamp": time.time(), "block_name": "synth_LO", "data": {}}

            data["data"]["F1"] = F_1
            data["data"]["F2"] = F_1+f_offset

            self.agent.publish_to_feed("synth_LO", data)
            session.data.update(data["data"])

        return True, "Frequencies Updated"

    # This function is not finished, need to figure out how to read out frequency from USB connection.
    def read_frequencies(self, session, params=None):

        with self.lock.acquire_timeout(timeout=3, job="read_frqeuencies") as acquired:
            if not acquired:
                self.log.warn(
                    f"Could not set position because lock held by {self.lock.job}"
                )
                return False, "Could not acquire lock"

        return True, "Frequencies Updated"

    def set_synth_status(self, session, params):
        """
        params: 
            dict: {'LO_ID': int
                   'status': int}
        """

        LO_ID = params.get("lo_id", 0)
        switch = params.get("switch", 0)

        with self.lock.acquire_timeout(timeout=3, job="turn_on_or_off_synth") as acquired:
            if not acquired:
                self.log.warn(
                    f"Could not set position because lock held by {self.lock.job}"
                )
                return False, "Could not acquire lock"

            synth3.set_RF_output(LO_ID, switch, self.lo_id)

            data = {"timestamp": time.time(), "block_name": "synth_LO", "data": {}}

            data["data"]["F1_status"] = switch

            self.agent.publish_to_feed("synth_LO", data)
            session.data.update(data["data"])


        return True, "Frequencies Updated"

def make_parser(parser=None):
    """Build the argument parser for the Agent. Allows sphinx to automatically
    build documentation based on this function.
    """
    if parser is None:
        parser = argparse.ArgumentParser()

    # Add options specific to this agent.
    pgroup = parser.add_argument_group("Agent Options")
    pgroup.add_argument("--config_file")

    return parser


if __name__ == "__main__":
    # For logging
    txaio.use_twisted()
    LOG = txaio.make_logger()

    # Start logging
    txaio.start_logging(level=os.environ.get("LOGLEVEL", "info"))

    parser = make_parser()

    # Interpret options in the context of site_config.
    args = site_config.parse_args(agent_class="SynthAgent", parser=parser)

    agent, runner = ocs_agent.init_site_agent(args)

    synth_agent = SynthAgent(agent, args.config_file)

    agent.register_task("init_synth", synth_agent.init_synth)
    agent.register_task("set_frequencies", synth_agent.set_frequencies)
    agent.register_task("read_frequencies", synth_agent.read_frequencies)
    agent.register_task("set_synth_status", synth_agent.set_synth_status)

    runner.run(agent, auto_reconnect=True)