import sys, os, argparse, time
import numpy as np
import traceback

this_dir = os.path.dirname(__file__)
sys.path.append(
        os.path.join(this_dir, 'src'))

import pmx as pm
import command as cm
from common import * # openlog, writelog

from ocs import ocs_agent, site_config, client_t
from ocs.ocs_twisted import TimeoutLock
class KikusuiAgent:
    def __init__(self, agent, kikusui_ip, kikusui_port):
        self.agent = agent
        self.log = agent.log
        self.lock = TimeoutLock()

        self.take_data = False
        self.switching = False # True while a command is sent to KIKSUI.
        self.switching2= False # True while IV is gotten.
        self.wait_loop = 100 # Max number of loop in __wait_control
        self.kikusui_ip = kikusui_ip
        self.kikusui_port = int(kikusui_port)

        self.position_path = '/data/wg-data/position.log'
        self.action_path = '/data/wg-data/action/'

        self.open_trial = 10
        self.Deg = 360/52000
        self.feedback_time = [0.181, 0.221, 0.251, 0.281, 0.301]
        self.feedback_cut = [0.5, 2.5, 4.5, 6.0, 7.0]
        self.operation_time = 0.401
        self.feedback_steps = 8
        self.num_laps = 2
        self.stopped_time = 10
        self.agent_interval = 0.2

        agg_params = {'frame_length': 60}
        self.agent.register_feed('kikusui_psu', record = True, agg_params = agg_params)

        try :
            self.PMX = pm.PMX(tcp_ip = self.kikusui_ip, tcp_port = self.kikusui_port, timeout = 0.5)
        except Exception as e:
            self.log.warn('Could not connect to serial converter! | Error = "%s"' % e)
            self.PMX = None
            pass

        if not self.PMX is None : self.cmd = cm.Command(self.PMX)
        else :                    self.cmd = None
        pass

    def __check_connect(self):
        if self.PMX is None :
            msg = 'No connection to the KIKUSUI power supply. | Error = "PMX is None"'
            self.log.warn(msg)
            return False, msg
        else :
            msg, ret = self.PMX.check_connect()
            if not ret :
                msg = 'No connection to the KIKUSUI power supply. | Error = "%s"' %  msg
                self.log.warn(msg)
                return False, msg
            pass
        return True, 'Connection is OK.'


    def __reconnect(self):
        self.log.warn('Trying to reconnect...')
        # reconnect
        try :
            if self.PMX : del self.PMX
            if self.cmd : del self.cmd
            self.PMX = pm.PMX(tcp_ip = self.kikusui_ip, tcp_port = self.kikusui_port, timeout = 0.5)
        except Exception as e:
            msg = 'Could not reconnect to the KIKUSUI power supply! | Error: %s' % e
            self.log.warn(msg)
            self.PMX = None
            self.cmd = None
            return False, msg
        # reinitialize cmd
        self.cmd = cm.Command(self.PMX)
        ret, msg = self.__check_connect()
        if ret :
            msg = 'Successfully reconnected to the KIKUSUI power supply!'
            self.log.info(msg)
            return True, msg
        else :
            msg = 'Failed to reconnect to the KIKUSUI power supply!'
            self.log.warn(msg)
            if self.PMX : del self.PMX
            if self.cmd : del self.cmd
            self.PMX = None
            self.cmd = None
            return False, msg

    def __wait_control(self):
        # check control
        for i in range(self.wait_loop) :
            if (not self.switching) and (not self.switching2) :
                self.switching=True
                return True
            time.sleep(0.1)
            pass
        msg = 'Failed to wait for getting the control. Exceed max. number of Waiting loop. (max={})'.format(self.wait_loop)
        self.log.warn(msg)
        return False

    def set_on(self, session, params = None):
        with self.lock.acquire_timeout(0, job = 'set_on') as acquired:
            if not acquired:
                self.log.warn('Could not set ON because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            # wait for getting control
            ret = self.__wait_control()
            if ret :
                self.cmd.user_input('on')
                self.switching = False
            else :
                msg = 'Could not set ON because of failure in getting the control.'
                self.log.warn(msg)
                return False, msg
                pass
            pass

        return True, 'Set Kikusui on'

    def set_off(self, session, params = None):
        with self.lock.acquire_timeout(0, job = 'set_off') as acquired:
            if not acquired:
                self.log.warn('Could not set OFF because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            # wait for getting control
            ret = self.__wait_control()
            if ret :
                self.cmd.user_input('off')
                self.switching = False
            else :
                msg = 'Could not set OFF because of failure in getting the control.'
                self.log.warn(msg)
                return False, msg
                pass
            pass

        return True, 'Set Kikusui off'

    def calibrate_itself(self, session, params = None):
        if params == None:
            params = {'storepath':self.action_path}
            pass

        with self.lock.acquire_timeout(0, job = 'set_off') as acquired:
            if not acquired:
                self.log.warn('Could not calibrate itself because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

        logfile = openlog(params['storepath'])

        ret = self.__wait_control()

        cycle = 1
        for i in range(11):
            tperiod = 0.10 + 0.02*i
            for j in range(100):
                if j%20 == 0:
                    self.log.warn(f'this is {cycle}th time action')
                    pass

                writelog(logfile, 'ON', tperiod, self.get_position(self.position_path, self.open_trial, self.Deg))
                self.rotate_alittle(ret, tperiod)
                time.sleep(self.agent_interval+1.)
                writelog(logfile, 'OFF', 0., self.get_position(self.position_path, self.open_trial, self.Deg))
                writelog(logfile, 'ON', 0.70, self.get_position(self.position_path, self.open_trial, self.Deg))
                self.rotate_alittle(ret, 0.70)
                time.sleep(self.agent_interval+1.)
                writelog(logfile, 'OFF', 0., self.get_position(self.position_path, self.open_trial, self.Deg))
                cycle += 1

                pass
            pass

        self.switching = False

        logfile.close()

        return True, 'Micro step rotation of wire grid finished. Please calibrate and take feedback params.'

    def emit_stepwise_signals(self, session, params = None):
        if params == None:
            params = {'feedback_steps': 8, 'num_laps': 1, 'stopped_time': 10, 'feedback_time': [0.181, 0.221, 0.251, 0.281, 0.301]}
            pass

        with self.lock.acquire_timeout(0, job = 'set_off') as acquired:
            if not acquired:
                self.log.warn('Could not emit polarized signals because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

        self.feedback_steps = params['feedback_steps']
        self.num_laps = params['num_laps']
        self.stopped_time = params['stopped_time']
        self.feedback_time = params['feedback_time']

        logfile = openlog(self.action_path)

        ret = self.__wait_control()

        for i in range(self.num_laps*16):
            self.move_next(ret, logfile, self.feedback_steps, self.feedback_time)
            time.sleep(self.stopped_time)
            pass

        self.switching = False

        logfile.close()

        return True, 'Step-wise rotation finished'

    def move_next(self, ret, logfile, feedback_steps, feedback_time): # each value can be changed
        wanted_angle = 22.5
        uncertaity_cancel = 3
        absolute_position = np.arange(0,360,wanted_angle)

        start_position = self.get_position(self.position_path, self.open_trial, self.Deg)
        if (360 < start_position + uncertaity_cancel):
            goal_position = wanted_angle
            pass
        elif absolute_position[-1] < start_position + uncertaity_cancel:
            goal_position = 0
            pass
        else:
            goal_position = min(absolute_position[np.where(start_position + uncertaity_cancel < absolute_position)[0]])
            pass

        with open('feedback.log', 'a') as f:
            f.write('start: {}, goal: {}\n'.format(round(start_position,3), round(goal_position,3)))
            pass

        #writelog(logfile, 'ON', feedback_time[-1]+0.1, self.get_position(self.position_path, self.open_trial, self.Deg))
        self.rotate_alittle(ret, feedback_time[-1]+0.1)
        time.sleep(self.agent_interval)
        #writelog(logfile, 'OFF', 0., self.get_position(self.position_path, self.open_trial, self.Deg))

        for l in range(feedback_steps):
            mid_position = self.get_position(self.position_path, self.open_trial, self.Deg)
            if goal_position + wanted_angle < mid_position:
                self.operation_time = self.get_exectime(goal_position - (mid_position - 360), self.feedback_cut, feedback_time)
                pass
            else:
                self.operation_time = self.get_exectime(goal_position - mid_position, self.feedback_cut, feedback_time)
                pass

            with open('operation_time.log', 'a') as f:
                f.write(str(l)+':'+str(round(mid_position,3))+' '+str(self.operation_time)+'\n')
                pass

            #writelog(logfile, 'ON', self.operation_time, self.get_position(self.position_path, self.open_trial, self.Deg))
            self.rotate_alittle(ret, self.operation_time)
            #writelog(logfile, 'OFF', 0., self.get_position(self.position_path, self.open_trial, self.Deg))
            pass

    def rotate_alittle(self, ret, operation_time):
        if ret:
            if operation_time != 0.:
                self.cmd.user_input('on')
                time.sleep(operation_time)
                self.cmd.user_input('off')
                time.sleep(self.agent_interval)
                pass
            pass
        else:
            msg = 'Could not rotate because of failure in getting the control.'
            self.log.warn(msg)
            return False, msg
            pass
        pass

    def get_position(self, position_path, open_trial, Deg):
        try:
            for i in range(open_trial):
                with open(position_path) as f:
                    position_data = f.readlines()
                    position = position_data[-1].split(' ')[1].replace('\n','')
                    if len(position) != 0:
                        break
                    pass
                pass
            pass
        except:
            with open('file_open_error.log','a') as f:
                traceback.print_exc(file=f)
                pass
            self.log.warn('Failed to open ENCODER POSITION FILE')
            pass

        return int(position)*Deg

    def get_exectime(self, position_difference, feedback_cut, feedback_time):
        if position_difference >= feedback_cut[4]:
            operation_time = feedback_time[4]
            pass
        if (feedback_cut[4] > position_difference) & (position_difference >= feedback_cut[3]):
            operation_time = feedback_time[3]
            pass
        if (feedback_cut[3] > position_difference) & (position_difference >= feedback_cut[2]):
            operation_time = feedback_time[2]
            pass
        if (feedback_cut[2] > position_difference) & (position_difference >= feedback_cut[1]):
            operation_time = feedback_time[1]
            pass
        if (feedback_cut[1] > position_difference) & (position_difference >= feedback_cut[0]):
            operation_time = feedback_time[0]
            pass
        if feedback_cut[0] > position_difference:
            operation_time = 0.
            pass
        return operation_time

    def set_c(self, session, params = None):
        if params == None:
            params = {'current': 0}

        with self.lock.acquire_timeout(0, job = 'set_c') as acquired:
            if not acquired:
                self.log.warn('Could not set c because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            # wait for getting control
            ret = self.__wait_control()
            if ret :
                if params['current'] <= 3. and 0. <= params['current']:
                    self.cmd.user_input('C {}'.format(params['current']))
                    pass
                else:
                    self.log.warn('Value Error: set current 3.0 A or less. Now set to 3.0 A')
                    self.cmd.user_input('C {}'.format(3.0))
                    pass
                self.switching = False
            else :
                msg = 'Could not set c because of failure in getting the control.'
                self.log.warn(msg)
                return False, msg
                pass
            pass

        return True, 'Set Kikusui current to {} A'.format(params['current'])


    def set_v(self, session, params = None):
        if params == None:
            params = {'volt': 0}

        with self.lock.acquire_timeout(0, job = 'set_v') as acquired:
            if not acquired:
                self.log.warn('Could not set v because {} is already running'.format(self.lock.job))
                return False, 'Could not acquire lock'

            # wait for getting control
            ret = self.__wait_control()
            if ret :
                if params['volt'] == 12.:
                    self.cmd.user_input('V {}'.format(params['volt']))
                    pass
                else:
                    self.log.warn('Value Error: Rated Voltage of the motor is 12 V. Now set to 12 V')
                    self.cmd.user_input('V {}'.format(12.))
                    pass
                self.switching = False
            else :
                msg = 'Could not set v because of failure in getting the control.'
                self.log.warn(msg)
                return False, msg
                pass
            pass

        return True, 'Set Kikusui voltage to {} V'.format(params['volt'])

    def get_vc(self, session, params = None):
        with self.lock.acquire_timeout(timeout = 0, job = 'get_vc') as acquired:
            if not acquired:
                self.log.warn('Could not get c,v because {} is already running'
                              .format(self.lock.job))
                return False, 'Could not acquire lock'

            v_val = None
            c_val = None
            s_val = None
            msg   = 'Error'
            s_msg = 'Error'

            # wait for getting control
            ret = self.__wait_control()
            if ret :
                # check connection
                ret, msg = self.__check_connect()
                if not ret :
                    msg = 'Could not get c,v because of failure of connection.'
                else :
                    msg, v_val, c_val = self.cmd.user_input('VC?')
                    s_msg, s_val      = self.cmd.user_input('O?')
                    pass
                self.switching = False
            else :
                msg = 'Could not get c,v because of failure in getting the control.'
                self.log.warn(msg)
                pass
            pass

        self.log.info('Get voltage/current message: {}'.format(msg));
        self.log.info('Get status message: {}'.format(s_msg));
        return True, 'Get Kikusui voltage / current: {} V / {} A [status={}]'.format(v_val,c_val,s_val)

    def start_IV_acq(self, session, params = None):
        with self.lock.acquire_timeout(timeout = 0, job = 'IV_acq') as acquired:
            if not acquired:
                self.log.warn('Could not start IV acq because {} is already running'
                              .format(self.lock.job))
                return False, 'Could not acquire lock'

            session.set_status('running')

        self.take_data = True

        while self.take_data:
            data = {'timestamp': time.time(), 'block_name': 'Kikusui_IV', 'data': {}}

            if not self.switching:
                self.switching2 = True;
                # check connection
                ret, msg = self.__check_connect()
                if not ret :
                    msg = 'Could not connect to the KIKUSUI power supply!'
                    v_val, i_val, vs_val, is_val = 0., 0., 0., 0.
                    s_val = -1 # -1 means Not connected.
                    # try to reconnect
                    self.__reconnect()
                else :
                    v_msg, v_val = self.cmd.user_input('V?')
                    i_msg, i_val = self.cmd.user_input('C?')
                    vs_msg,vs_val= self.cmd.user_input('VS?')
                    is_msg,is_val= self.cmd.user_input('CS?')
                    s_msg, s_val = self.cmd.user_input('O?')
                    pass
                self.switching2 = False;
                data['data']['kikusui_volt'] = v_val
                data['data']['kikusui_curr'] = i_val
                data['data']['kikusui_voltset'] = vs_val
                data['data']['kikusui_currset'] = is_val
                data['data']['kikusui_status'] = s_val
                self.agent.publish_to_feed('kikusui_psu', data)
            else:
                #data['data']['kikusui_volt'] = 0
                #data['data']['kikusui_curr'] = 0
                #data['data']['kikusui_status'] = 0
                pass

            time.sleep(1) # DAQ interval
            pass # End of while loop

        self.agent.feeds['kikusui_feed'].flush_buffer()
        return True, 'Acqusition exited cleanly'

    def stop_IV_acq(self, session, params = None):
        if self.take_data:
            self.take_data = False
            return True, 'requested to stop taking data'

        return False, 'acq is not currently running'

def make_parser(parser = None):
    if parser is None:
        parser = argparse.ArgumentParser()

    pgroup = parser.add_argument_group('Agent Options')
    pgroup.add_argument('--kikusui-ip')
    pgroup.add_argument('--kikusui-port')
    return parser

if __name__ == '__main__':
    site_parser = site_config.add_arguments()
    parser = make_parser(site_parser)

    args = parser.parse_args()

    site_config.reparse_args(args, 'KikusuiAgent')
    agent, runner = ocs_agent.init_site_agent(args)
    kikusui_agent = KikusuiAgent(agent, kikusui_ip = args.kikusui_ip,
                                          kikusui_port = args.kikusui_port)
    agent.register_process('IV_acq', kikusui_agent.start_IV_acq,
                           kikusui_agent.stop_IV_acq, startup = True)
    agent.register_task('set_on', kikusui_agent.set_on)
    agent.register_task('set_off', kikusui_agent.set_off)
    agent.register_task('set_c', kikusui_agent.set_c)
    agent.register_task('set_v', kikusui_agent.set_v)
    agent.register_task('get_vc',kikusui_agent.get_vc)
    agent.register_task('calibrate_wg',kikusui_agent.calibrate_itself)
    agent.register_task('stepwise_rotation', kikusui_agent.emit_stepwise_signals)

    runner.run(agent, auto_reconnect = True)