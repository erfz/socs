import os
import argparse
import time
import txaio

ON_RTD = os.environ.get('READTHEDOCS') == 'True'
if not ON_RTD:
    from ocs import ocs_agent, site_config
    from ocs.ocs_twisted import TimeoutLock, Pacemaker
    import casperfpga
    from holog_daq import poco3, fpga_daq3, synth3

class FPGAAgent:
    """
    Agent for connecting to the Synths for holography
    
    Args: 
    """

    def __init__( self, agent ):
        
        self.fpga = None
        self.initialized = False
        self.take_data = False

        self.agent = agent
        self.log = agent.log
        self.lock = TimeoutLock()
        
        """
        if mode == 'acq':
            self.auto_acq = True
        else:
            self.auto_acq = False
        self.sampling_frequency = float(samp)

        ### register the position feeds
        agg_params = {
            'frame_length' : 10*60, #[sec] 
        }
        ### Agent registers data feed, things published to feed go to grafana and .g3 files
        ### pick a good name for feeds, once it's registered it's kinda permanent
        self.agent.register_feed('fpga',
                                 record = True,
                                 agg_params = agg_params,
                                 buffer_time = 0)
        """
    def init_FPGA(self, session, params=None):
        """init_synth(params=None)
        Perform first time setup for communication with Synth.

        Args:
            params (dict): Parameters dictionary for passing parameters to
                task.
        """

        if params is None:
            params = {}

        self.log.debug("Trying to acquire lock")
        with self.lock.acquire_timeout(timeout=1, job='init') as acquired:
            # Locking mechanism stops code from proceeding if no lock acquired
            if not acquired:
                self.log.warn("Could not start init because {} is already running".format(self.lock.job))
                return False, "Could not acquire lock."
            # Run the function you want to run
            self.log.debug("Lock Acquired initializing the FPGA")
            
            self.roach, self.opts, self.baseline = fpga_daq3.roach2_init()
            print("Programming FPGA with python2")
            err = os.system("/opt/anaconda2/bin/python2 /home/chesmore/Desktop/holog_daq/scripts/upload_fpga_py2.py")
            assert err == 0

            self.fpga = casperfpga.CasperFpga(self.roach)


        # This part is for the record and to allow future calls to proceed,
        # so does not require the lock
        self.initialized = True
        #if self.auto_acq:
        #    self.agent.start('acq')
        return True, 'FPGA connected.'


    def take_data(self, session, params=None):

        if params is None:
            params = {}

        self.log.debug("Trying to acquire lock")
        with self.lock.acquire_timeout(timeout=1, job='take_data') as acquired:
            # Locking mechanism stops code from proceeding if no lock acquired
            if not acquired:
                self.log.warn("Could not start init because {} is already running".format(self.lock.job))
                return False, "Could not acquire lock."
            # Run the function you want to run
            self.log.debug("Lock Acquired initializing the FPGA")


        # This part is for the record and to allow future calls to proceed,
        # so does not require the lock
        self.initialized = True
        #if self.auto_acq:
        #    self.agent.start('acq')
        return True, 'FPGA connected.'


    # def take_data(self, session, params=None):
    #     """
    #     params: 
    #         dict: {'freq0': float
    #                'freq1': float}
    #     """
    #     # f1 = params.get('freq1', 0)

    #     with self.lock.acquire_timeout(timeout=3, job='take_data') as acquired:
    #         if not acquired:
    #             self.log.warn(f"Could not set position because lock held by {self.lock.job}")
    #             return False, "Could not acquire lock"
                        
    #         ## this is where you would talk to self.fpga and tell is to give you
    #         ## some data 
    #         self.roach, self.opts, self.baseline = fpga_daq3.roach2_init()
    #         print('initial ROACH settings')
    #         self.synth_settings = synth3.SynthOpt()
    #         print('class of synthesizer settings acquired')
    #         out = fpga_daq3.TakeAvgData(self.baseline, self.fpga, self.synth_settings)
                        
    #         # data dictionary is what we will send to the data feed
    #         #data = {'timestamp':time.time(), 'block_name':'fpga','data':{}}
            
    #         #THING, THING2 = self.fpga.give_me_data()

    #         #data['data']['THING'] = THING
    #         #data['data']['OTHER_THING'] = THING2

    #         #self.agent.publish_to_feed('fpga',data)
    #         #session.data.update( data['data'] )

    #         pass

    #     return True, "Data acquired."
    
def make_parser(parser=None):
    """Build the argument parser for the Agent. Allows sphinx to automatically
    build documentation based on this function.
    """
    if parser is None:
        parser = argparse.ArgumentParser()

    # Add options specific to this agent.
    pgroup = parser.add_argument_group('Agent Options')
    return parser


if __name__ == '__main__':
    # For logging
    txaio.use_twisted()
    LOG = txaio.make_logger()

    # Start logging
    txaio.start_logging(level=os.environ.get("LOGLEVEL", "info"))

    parser = make_parser()

    # Interpret options in the context of site_config.
    args = site_config.parse_args(agent_class = 'FPGAAgent', parser=parser)
   
    agent, runner = ocs_agent.init_site_agent(args)

    fpga_agent = FPGAAgent(agent,)

    agent.register_task('init_FPGA', fpga_agent.init_FPGA)
    agent.register_task('take_data', fpga_agent.take_data)
    
    runner.run(agent, auto_reconnect=True)