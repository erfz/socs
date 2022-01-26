import sys
import os
import argparse
import time

this_dir = os.path.dirname(__file__)
sys.path.append(
        os.path.join(this_dir, 'src'))

import pid_controller as pd
from socs.agent.pmx import PMX, Command

from ocs import ocs_agent, site_config, client_t
from ocs.ocs_twisted import TimeoutLock

class RotationAgent:
    """Agent to control the rotation speed of the CHWP

    Args:
        kikusui_ip (str): IP address for the Kikusui power supply 
        kikusui_port (str): Port for the Kikusui power supply
        pid_ip (str): IP address for the PID controller
        pid_port (str): Port for the PID controller

    """
    def __init__(self, agent, kikusui_ip, kikusui_port, pid_ip, pid_port):
        self.agent = agent
        self.log = agent.log
        self.lock = TimeoutLock()
        self.take_data = False
        self.switching = False
        self.kikusui_ip = kikusui_ip
        self.kikusui_port = int(kikusui_port)
        self.pid_ip = pid_ip
        self.pid_port = pid_port

        agg_params = {'frame_length': 60}
        self.agent.register_feed('hwprotation', record = True, agg_params = agg_params)

        try:
            self.pmx = PMX(tcp_ip = self.kikusui_ip, tcp_port = self.kikusui_port, timeout = 0.5)
            self.cmd = Command(self.pmx)
            print('Connected to Kikusui power supply')
        except:
            print('Could not establish connection to Kikusui power supply')
            sys.exit(0)

        try:
            self.pid = pd.PID(pid_ip = self.pid_ip, pid_port = self.pid_port)
            print('Connected to PID controller')
        except:
            print('Could not establish connection to PID controller')
            sys.exit(0)

    def tune_stop(self, session, params = None):
        """tune_stop(params = None)
        
        Reverses the drive direction of the PID controller and optimizes the PID parameters for deceleration

        """
        with self.lock.acquire_timeout(0, job = 'tune_stop') as acquired:
            if not acquired:
                self.log.warn('Could not tune stop because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'
            
            print('tune_stop() called')
            self.pid.tune_stop()
        
        return True, 'Reversing Direction'

    def tune_freq(self, session, params = None):
        """tune_freq(params = None)
        
        Tunes the PID controller setpoint to the rotation frequency and optimizes the PID parameters for rotation

        """
        with self.lock.acquire_timeout(0, job = 'tune_freq') as acquired:
            if not acquired:
                self.log.warn('Could not tune freq because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            print('tune_freq() called')
            self.pid.tune_freq()

        return True, 'Tuning to setpoint'

    @ocs_agent.param('freq', default = 0., check = lambda x: 0. <= x <= 3.0)
    def declare_freq(self, session, params = None):
        """declare_freq(params = None)
        
        Stores the entered frequency as the PID setpoint when tune_freq is next called

        Args:
            params (dict): Parameters dictionary for passing parameters to task

        Parameters:
            freq (float): Desired HWP rotation frequency 

        """
        with self.lock.acquire_timeout(0, job = 'declare_freq') as acquired:
            if not acquired:
                self.log.warn('Could not declare freq because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            print('declare_freq() called')
            self.pid.declare_freq(params['freq'])

        return True, 'Setpoint at {} Hz'.format(params['freq'])

    @ocs_agent.param('p_param', default = 0.2, check = lambda x: 0. < x <= 8.)
    @ocs_agent.param('i_param', default = 63, type = int, check = lambda x: 0 <= x <= 200)
    @ocs_agent.param('d_param', default = 0., type = float, check = lambda x: 0. <= x < 10.)
    def set_pid(self, session, params = None):
        """set_pid(params = None)
        
        Sets the PID parameters. Note these changes are for the current session only and will change 
        whenever the agent container is reloaded

        Args:
            params (dict): Parameters dictionary for passing parameters to task

        Parameters:
            p_param (float): Proportional PID value
            i_param (float): Integral PID value
            d_param (float): Derivative PID value

        """
        with self.lock.acquire_timeout(0, job = 'set_pid') as acquired:
            if not acquired:
                self.log.warn('Could not set pid because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            print('set_pid() called')
            self.pid.set_pid([p_param, i_param, d_param])

        return True, 'Set PID params to p: {}, i: {}, d: {}'.format(p_param, i_param, d_param)

    def get_freq(self, session, params = None):
        """get_freq(params = None)
        
        Returns the current HWP frequency as seen by the PID controller

        """
        with self.lock.acquire_timeout(0, job = 'get_freq') as acquired:
            if not acquired:
                self.log.warn('Could not get freq because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            print('get_freq() called')
            self.pid.get_freq()

        return self.pid.cur_freq, 'Current frequency = {}'.format(self.pid.cur_freq)

    def get_direction(self, session, params = None):
        """get_direction(params = None

        Returns the current HWP tune direction as seen by the PID controller 

        """
        with self.lock.acquire_timeout(0, job = 'get_direction') as acquired:
            if not acquired:
                self.log.warn('Could not get freq because {} is already running'.format(self.lock.job))

            print('get_direction() called')
            self.pid.get_direction()

        return self.pid.direction, 'Current Direction = {}'.format(['Forward', 'Reverse'][self.pid.direction])

    @ocs_agent.param('direction', default = '0', choices = ['0', '1'])
    def set_direction(self, session, params = None):
        """set_direction(params = None)
        
        Sets the HWP rotation direction

        Args:
            params (dict): Parameters dictionary for passing parameters to task

        Parameters:
            direction (str, optional): '0' for forward and '1' for reverse. Default is '0'

        """
        with self.lock.acquire_timeout(0, job = 'set_direction') as acquired:
            if not acquired:
                self.log.warn('Could not set direction because {} is already running'.format(self.lock.job))

            print('set_direction() called')
            self.pid.set_direction(params['direction'])

        return True, 'Set direction'

    @ocs_agent.param('slope', default = 1., check = lambda x: -10. < x < 10.)
    @ocs_agent.param('offset', default = 0., check = lambda x: -10. < x < 10.)
    def set_scale(self, session, params = None):
        """set_scale(params = None)
        
        Sets the PID's internal conversion from input voltage to rotation frequency

        Args:
            params (dict): Parameters dictionary for passing parameters to task

        Parameters:
            slope (float): Slope of the "rotation frequency vs input voltage" relationship
            offset (float): y-intercept of the "rotation frequency vs input voltage" relationship

        """
        with self.lock.acquire_timeout(0, job = 'set_scale') as acquired:
            if not acquired:
                self.log.warn('Could not set scale because {} is already running'.format(self.lock.job))
            
            print('set_scale() called')
            self.pid.set_scale(params['slope'], params['offset'])

        return True, 'Set scale'

    def set_on(self, session, params = None):
        """set_on(params = None)
        
        Turns on the Kikusui drive voltage

        """
        with self.lock.acquire_timeout(0, job = 'set_on') as acquired:
            if not acquired:
                self.log.warn('Could not set on because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            self.switching = True
            time.sleep(1)
            print('set_on() called')
            self.cmd.user_input('on')
            self.switching = False

        return True, 'Set Kikusui on'

    def set_off(self, session, params = None):
        """set_off(params = None)
        
        Turns off the Kikusui drive voltage

        """
        with self.lock.acquire_timeout(0, job = 'set_off') as acquired:
            if not acquired:
                self.log.warn('Could not set off because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            self.switching = True
            time.sleep(1)
            print('set_off() called')
            self.cmd.user_input('off')
            self.switching = False

        return True, 'Set Kikusui off'

    @ocs_agent.param('volt', default = 0, check = lambda x: 0 <= x <= 35)
    def set_v(self, session, params = None):
        """set_v(params = None)
        
        Sets the Kikusui drive voltage

        Args:
            params (dict): Parameters dictionary for passing parameters to task

        Parameters:
            volt (float): Kikusui set voltage

        """
        with self.lock.acquire_timeout(0, job = 'set_v') as acquired:
            if not acquired:
                self.log.warn('Could not set v because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            self.switching = True
            time.sleep(1)
            print('set_v() called')
            self.cmd.user_input('V {}'.format(params['volt']))
            self.switching = False

        return True, 'Set Kikusui voltage to {} V'.format(params['volt'])

    @ocs_agent.param('volt', default = 32., check = lambda x: 0. <= x <= 35.)
    def set_v_lim(self, session, params = None):
        """set_v_lim(params = None)
        
        Sets the Kikusui drive voltage limit

        Args:
            params (dict): Parameters dictionary for passing parameters to task

        Parameters:
            volt (float): Kikusui limit voltage

        """
        with self.lock.acquire_timeout(0, job = 'set_v_lim') as acquired:
            if not acquired:
                self.log.warn('Could not set v lim because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            self.switching = True
            time.sleep(1)
            print('set_v_lim() called')
            print(params['volt'])
            self.cmd.user_input('VL {}'.format(params['volt']))
            self.switching = False

        return True, 'Set Kikusui voltage limit to {} V'.format(params['volt'])

    def use_ext(self, session, params = None): 
        """use_ext(params = None)
        
        Set's the Kikusui to use an external voltage control. Doing so enables PID control

        """
        with self.lock.acquire_timeout(0, job = 'use_ext') as acquired:
            if not acquired:
                self.log.warn('Could not use external voltage because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            self.switching = True
            time.sleep(1)
            print('use_ext() called')
            self.cmd.user_input('U')
            self.switching = False

        return True, 'Set Kikusui voltage to PID control'

    def ign_ext(self, session, params = None):
        """ign_ext(params = None)
        
        Set's the Kiksui to ignore external voltage control. Doing so disables the PID and switches to direct control

        """
        with self.lock.acquire_timeout(0, job = 'ign_ext') as acquired:
            if not acquired:
                self.log.warn('Could not ignore external voltage because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            self.switching = True
            time.sleep(1)
            print('ign_ext() called')
            self.cmd.user_input('I')
            self.switching = False

        return True, 'Set Kikusui voltage to direct control'

    def start_iv_acq(self, session, params = None):
        """start_iv_acq(params = None)

        Method to start Kikusui data acquisition process

        The most recent data collected is stored in the structure:
            >>> data
            {'kikusui_volt': 0, 'kikusui_curr': 0}

        """
        with self.lock.acquire_timeout(timeout = 0, job = 'iv_acq') as acquired:
            if not acquired:
                self.log.warn('Could not start iv acq because {} is already running'
                              .format(self.lock.job))
                return False, 'Could not acquire lock'

            session.set_status('running')
        
        self.take_data = True

        print('Starting IV acq')
        while self.take_data:
            data = {'timestamp': time.time(), 'block_name': 'HWPKikusui_IV', 'data': {}}
           
            if not self.switching:
                v_msg, v_val = self.cmd.user_input('V?')
                i_msg, i_val = self.cmd.user_input('C?')

                data['data']['kikusui_volt'] = v_val
                data['data']['kikusui_curr'] = i_val

                if type(data['data']['kikusui_curr'])  == float and type(data['data']['kikusui_volt']) == float:
                    self.agent.publish_to_feed('hwprotation', data)
            
            time.sleep(1)

        self.agent.feeds['hwprotation'].flush_buffer()
        return True, 'Acqusition exited cleanly'

    def stop_iv_acq(self, session, params = None):
        """
        Stops acq process
        """
        if self.take_data:
            print('Stopping IV acq')
            self.take_data = False
            return True, 'requested to stop taking data'

        return False, 'acq is not currently running'

def make_parser(parser = None):
    """
    Build the argument parser for the Agent. Allows sphinx to automatically build documentation
    baised on this function
    """
    if parser is None:
        parser = argparse.ArgumentParser()

    # Add options specific to this agent
    pgroup = parser.add_argument_group('Agent Options')
    pgroup.add_argument('--kikusui-ip')
    pgroup.add_argument('--kikusui-port')
    pgroup.add_argument('--pid-ip')
    pgroup.add_argument('--pid-port')
    return parser

if __name__ == '__main__':
    # Get the default ocs argument parser
    site_parser = site_config.add_arguments()
    parser = make_parser(site_parser)

    # Parse the command line
    args = parser.parse_args()

    # Interpret options in the context of site_config
    site_config.reparse_args(args, 'RotationAgent')
    agent, runner = ocs_agent.init_site_agent(args)
    rotation_agent = RotationAgent(agent, kikusui_ip = args.kikusui_ip, 
                                          kikusui_port = args.kikusui_port,
                                          pid_ip = args.pid_ip,
                                          pid_port = args.pid_port)
    agent.register_process('iv_acq', rotation_agent.start_iv_acq,
                           rotation_agent.stop_iv_acq, startup = True)
    agent.register_task('tune_stop', rotation_agent.tune_stop)
    agent.register_task('tune_freq', rotation_agent.tune_freq)
    agent.register_task('declare_freq', rotation_agent.declare_freq)
    agent.register_task('set_pid', rotation_agent.set_pid) 
    agent.register_task('get_freq', rotation_agent.get_freq)  
    agent.register_task('get_direction', rotation_agent.get_direction)
    agent.register_task('set_direction', rotation_agent.set_direction) 
    agent.register_task('set_scale', rotation_agent.set_scale)
    agent.register_task('set_on', rotation_agent.set_on)
    agent.register_task('set_off', rotation_agent.set_off)
    agent.register_task('set_v', rotation_agent.set_v)
    agent.register_task('set_v_lim', rotation_agent.set_v_lim)
    agent.register_task('use_ext', rotation_agent.use_ext)
    agent.register_task('ign_ext', rotation_agent.ign_ext)

    runner.run(agent, auto_reconnect = True)
