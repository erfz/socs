# Script to log and control the Sorenson DLM power supply, for heaters
# Tanay Bhandarkar, Jack Orlowski-Scherer
import time
import socket
import argparse
from ocs import site_config, ocs_agent
from ocs.ocs_twisted import TimeoutLock, Pacemaker


class DLM:
    def __init__(self, ip_address, port=9221, timeout=10):
        self.ip_address = ip_address
        self.port = port
        self.comm = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.comm.connect((self.ip_address, self.port))
        self.comm.settimeout(timeout)

    def send_msg(self, cmd):
        """
        Sends a message to the DLM. 'OPC?' causes the DLM to wait for the
        previous command to complete to being the next
        """
        msg = str(cmd) + ';OPC?\r\n'
        self.comm.send(msg.encode('ASCII'))
        time.sleep(0.1)

    def rec_msg(self):
        """
        Waits for a message from the DLM, typically as a result of a query,
        and returns it
        """
        dataStr = self.comm.recv(1024).decode('ASCII')
        return dataStr.strip()

    def set_overv_prot(self, voltage):
        """
        Sets the overvoltage protection
        """
        self.send_msg('*CLS')
        self.send_msg('*RST')
        self.send_msg('SOUR:VOLT:PROT {}'.format(voltage))

        self.send_msg('SOUR:VOLT:PROT?')
        ovp = self.rec_msg()
        if ovp != str(voltage):
            print("Error: Over voltage protection not set to requested value")
            return False

        self.send_msg('STAT:PROT:ENABLE 8')
        self.send_msg('STAT:PROT:ENABLE?')
        enb = self.rec_msg()
        if enb != '8':
            print('Error: Over voltage protection failed to enable')
            return False

        self.send_msg('STAT:PROT:EVENT?')
        event = self.rec_msg()
        if event != '0':
            print('Error: Over voltage already tripped')
            return False

        return True

    def read_voltage(self):
        """
        Reads output  voltage
        """
        self.send_msg('SOUR:VOLT?')
        msg = self.rec_msg()
        return msg

    def read_current(self):
        """
        Reads output current
        """
        self.send_msg('MEAS:CURR?')
        msg = self.rec_msg()
        return msg

    def sys_err_check(self):  # never used
        """
        Queries sytem error and returns error byte
        """
        self.send_msg('SYST:ERR?')
        msg = self.rec_msg()
        return msg


class DLMAgent:
    """Agent to connect to a Sorenson DLM power supply via ethernet.

    Args:
        ip_address: str
            IP address of the DLM
        port: int
            Port number for DLM; default is 9221

    """

    def __init__(self, agent, ip_address, port, f_sample=2.5):
        self.active = True  # not used elsewhere
        self.agent = agent
        self.log = agent.log
        self.lock = TimeoutLock()
        self.f_sample = f_sample
        self.take_data = False
        self.over_volt = 0.
        self.initialized = False
        self._acq_proc_lock = TimeoutLock()  # is this necessary? only used in init_dlm
        self._lock = TimeoutLock()  # is this necessary? only used in init_dlm

        try:
            self.dlm = DLM(ip_address, int(port))
        except socket.timeout as e:
            self.log.error("DLM power supply has timed out"
                           + f"during connect with error {e}")
            return False, "Timeout"

        agg_params = {'frame length': 60, }
        self.agent.register_feed('voltages',
                                 record=True,
                                 agg_params=agg_params,
                                 buffer_time=1)

    def acq(self, session, params=None):
        """acq(sampling_frequency=2.5)

        **Process** - Get voltage and current values from the sorenson,
        publishes them to the feed.

        Args:
            sampling_frequency: float
                defaults to 2.5Hz
        """
        if params is None:
            params = {}

        f_sample = params.get('sampling_frequency')
        if f_sample is None:
            f_sample = self.f_sample
        if f_sample % 1 == 0:
            pm = Pacemaker(f_sample, True)
        else:
            pm = Pacemaker(f_sample)
        wait_time = 1 / f_sample  # variable never used
        # job='init' is set here and in other acquire_timeout calls
        # even though the job is not 'init'
        with self.lock.acquire_timeout(timeout=0, job='init') as acquired:
            # Locking mechanism stops code from proceeding if no lock acquired
            pm.sleep()
            if not acquired:
                self.log.warn("Could not start init because {} is already running".format(self.lock.job))
                return False, "Could not acquire lock."

            session.set_status('running')
            last_release = time.time()
            self.take_data = True

            while self.take_data:
                # About every second, release and acquire the lock
                if time.time() - last_release > 1.:
                    last_release = time.time()
                    if not self.lock.release_and_acquire(timeout=10):
                        print(f"Could not re-acquire lock now held by {self.lock.job}.")
                        return False
                data = {
                    'timestamp': time.time(),
                    'block_name': 'voltages',
                    'data': {}
                }
                voltage_reading = self.dlm.read_voltage()
                current_reading = self.dlm.read_current()
                self.log.debug('Voltage: {}'.format(voltage_reading))
                self.log.debug('Current: {}'.format(current_reading))

                data['data']["voltage"] = float(voltage_reading)
                data['data']["current"] = float(current_reading)

                self.agent.publish_to_feed('voltages', data)
                pm.sleep()

            self.agent.feeds['voltages'].flush_buffer()
        return True, 'Acquistion exited cleanly'

    @ocs_agent.param('voltage', default=0., type=float, check=lambda V: 0 <= V <= 300)
    def set_voltage(self, session, params=None):
        """set_voltage(voltage=None)

        **Task** - Sets voltage of power supply.

        Args:
            voltage (float): Voltage to set.

        Examples:
            Example of a client, setting the current to 1V::

                client.set_voltage(voltage = 1.)

        """

        # job='init' set erroneously
        with self.lock.acquire_timeout(timeout=3, job='init') as acquired:
            if acquired:
                if self.over_volt == 0:
                    return False, 'Over voltage protection not set'
                elif float(params['voltage']) > float(self.over_volt):
                    return False, 'Voltage greater then over voltage protection'
                else:
                    self.dlm.send_msg('SOUR:VOLT {}'.format(params['voltage']))
            else:
                return False, "Could not acquire lock"

        return True, 'Set voltage to {}'.format(params['voltage'])

    def set_over_volt(self, session, params=None):
        """set_over_volt(over_volt=None)

        **Task** - Sets over voltage protection of power supply.

        Args:
            over_volt (int): Over voltage protection to set

        Examples:
            Example of a client, setting the overvoltage protection to 10V::

                client.set_over_volt(over_volt = 10.)

        """

        # job='init' set erroneously
        with self.lock.acquire_timeout(timeout=3, job='init') as acquired:
            if acquired:
                if not self.dlm.set_overv_prot(params['over_volt']):
                    return False, 'Failed to set overvoltage protection'
                self.over_volt = float(params['over_volt'])
            else:
                return False, 'Could not acquire lock'
        return True, 'Set over voltage protection to {}'.format(params['over_volt'])

    @ocs_agent.param('current', default=0., type=float, check=lambda x: 0 <= x <= 2)
    def set_current(self, session, params=None):
        """set_current(current=None)

        **Task** - Sets current of power supply.

        Args:
            current (float): Current to set.

        Examples:
            Example of a client, setting the current to 1A::

                client.set_current(current = 1.)

        """

        # job='init' set erroneously
        with self.lock.acquire_timeout(timeout=3, job='init') as acquired:
            if acquired:
                if self.over_volt == 0:
                    return False, 'Over voltage protection not set'
                # voltage not a param?
                # what is the intended check here?
                # elif float(params['voltage']) > float(self.over_volt):
                #     return False, 'Voltage greater then over voltage protection'
                else:
                    self.dlm.send_msg('SOUR:CURR {}'.format(params['current']))
            else:
                return False, "Could not acquire lock"

        return True, 'Set current to {}'.format(params['current'])

    @ocs_agent.param('auto_acquire', default=False, type=bool)
    @ocs_agent.param('acq_params', type=dict, default=None)
    @ocs_agent.param('force', default=False, type=bool)
    def init_dlm(self, session, params=None):
        """init_dlm(auto_acquire=False, acq_params=None, force=False)
        **Task** - Perform first time setup of the Sorenson DLM communication.

        Parameters:
            auto_acquire (bool, optional): Default is False. Starts data
                acquisition after initialization if True.
            acq_params (dict, optional): Params to pass to acq process if
                auto_acquire is True.
            force (bool, optional): Force initialization, even if already
                initialized. Defaults to False.
        """
        if params is None:
            params = {}

        if self.initialized and not params.get('force', False):
            self.log.info("DLM already initialized Returning...")
            return True, "Already initialized"

        # purpose of these locks when they are not used elsewhere?
        with self._lock.acquire_timeout(job='init') as acquired1, \
                self._acq_proc_lock.acquire_timeout(timeout=0., job='init') \
                as acquired2:
            if not acquired1:
                self.log.warn(f"Could not start init because "
                              f"{self._lock.job} is already running")
                return False, "Could not acquire lock"
            if not acquired2:
                self.log.warn(f"Could not start init because "
                              f"{self._acq_proc_lock.job} is already running")
                return False, "Could not acquire lock"
            # no code is lock-protected here --- i.e., locks are acquired
            # and then immediately freed
        session.set_status('running')

        # Start data acquisition if requested
        if params.get('auto_acquire', False):
            self.agent.start('acq', params.get('acq_params', None))

        self.initialized = True
        return True, 'DLM module initialized.'

    def _stop_acq(self, session, params=None):
        """
        End voltage data acquisition
        """
        if self.take_data:
            self.take_data = False
            return True, 'requested to stop taking data.'
        else:
            return False, 'acq is not currently running'


def make_parser(parser=None):
    """Build the argument parser for the Agent. Allows sphinx to automatically
    build documentation based on this function.
    """
    if parser is None:
        parser = argparse.ArgumentParser()

    pgroup = parser.add_argument_group('Agent Options')
    pgroup.add_argument('--ip-address', type=str, help="Serial-to-ethernet "
                        + "converter ip address")
    pgroup.add_argument('--port', type=int, help="Serial-to-ethernet "
                        + "converter port")

    return parser


if __name__ == '__main__':
    parser = make_parser()
    args = site_config.parse_args(agent_class='DLMAgent',
                                  parser=parser)

    agent, runner = ocs_agent.init_site_agent(args)
    DLM_agent = DLMAgent(agent, args.ip_address, args.port)
    agent.register_process('acq', DLM_agent.acq, DLM_agent._stop_acq)
    agent.register_task('set_voltage', DLM_agent.set_voltage)
    agent.register_task('close', DLM_agent._stop_acq)
    agent.register_task('set_over_volt', DLM_agent.set_over_volt)
    agent.register_task('init_dlm', DLM_agent.init_dlm, startup=True)
    agent.register_task('set_current', DLM_agent.set_current)
    runner.run(agent, auto_reconnect=True)
