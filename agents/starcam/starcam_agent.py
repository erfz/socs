import numpy as np
import datetime
import time
import os
from os import environ
import socket
from ocs import ocs_agent, site_config, client_t, ocs_feed
import argparse
from ocs.ocs_twisted import TimeoutLock


class starcam_Helper:
    """
    CLASS to control and retrieve data from the starcamera

    Args:
        ip_address: IP address of the starcamera computer
        user_port: port of the starcamera

    Atributes:
        unpack_data receives the astrometry data from starcamera system and unpacks it
        close closes the socket
    """
    def __init__(self,ip_address,user_port):
        self.ip = ip_address
        self.port = user_port
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.sock.connect((self.ip,self.port))
    
    def unpack_data(self,data):
        unpacked_data = struct.unpack_from("dddddddddddddiiiiiiiiddiiiiiiiiiiiiiifiii",data)
        return unpacked_data

    def get_astrom_data(self):
        self.starcamdata_raw = self.socket.recvfrom(224)
        self.starcamdata_unpacked = unpack_data(self.starcamdata_raw)
        c_time = self.starcamdata_unpacked[0]
        gmt = self.starcamdata_unpacked[1]
        blob_num = self.starcamdata_unpacked[2]
        obs_ra = self.starcamdata_unpacked[3]
        astrom_ra = self.starcamdata_unpacked[4]
        obs_dec = self.starcamdata_unpacked[5]
        astrom_dec = self.starcamdata_unpacked[6]
        fr = self.starcamdata_unpacked[7]
        ps = self.starcamdata_unpacked[8]
        alt = self.starcamdata_unpacked[9]
        az = self.starcamdata_unpacked[10]
        ir = self.starcamdata_unpacked[11]
        astrom_solve_time = self.starcamdata_unpacked[12]
        camera_time = self.starcamdata_unpacked[13]
        return c_time,gmt,blob_num,obs_ra,astrom_ra,obs_dec,astrom_dec,fr,ps,alt,az,ir,astrom_solve_time,camera_time

class starcam_Agent:
    def __init__(self, agent, ip_address, user_port):
        self.agent = agent
        self.active = True
        self.log = agent.log
        self.job = None
        self.take_data = False
        self.lock=TimeoutLock()

        ##register feed
        agg_params={'frame_length':60}
        self.agent.register_feed("starcamera",
                record=True,
                agg_params=agg_params,
                buffer_time=1)

        try:
            self.starcam_Helper=starcam_Helper(ip_address,user_port)
        except socket.timeout as e:
            self.log.error("Starcamaera connection has times out")
            return False,"Timeout"


    def try_set_job(self,job_name):
        with self.lock:
            if self.job==None:
                self.job = job_name
                return True, 'ok.'
            return False,'Conflict: "%s" is already running.'%self.job
    
    def set_job_done(self):
        with self.lock:
            self.job = None

    #Process functions
    @ocs_agent.param('test_mode',default=False,type=bool)
    def acq(self,session,params=None):
        """start_acq(test_mode=False)
        **Process** - Acquire data from starcam and write to feed.

        Parameters:
            test_mode (bool,optional): Run the acq process loop only once.
                This is meant only for testing. Default is false.
        """
        if params is None:
            params={}
        f_sample = params.get('sampling_frequency')
        if f_sample is None:
            f_sample = self.f_sample
        if f_sample %1 ==0:
            pm = Pacemaker(f_sample,True)
        else:
            pm = Pacemaker(f_sample)
        wait_time = 1 / f_sample

        with self.lock.acquire_timeout(timeout=0,job='init') as acquired:
            pm.sleep()
            if not acquired:
                self.log.warn("Coult not start init because {} is already running".format(self.lock.job))
                return False,"Could not acquire lock"
            ok,msg=self.try_set_job('acq')
            if not ok: return ok,msg
            session.set_status('running')
            self.take_data = True
            while self.take_data:
                data = {
                    'timestamp':time.time(),
                    'block_name':'astrometry',
                    'data':{}
                    }
                c_time_reading,gmt_reading,blob_num_reading,obs_ra_reading,astrom_ra_reading,obs_dec_reading,astrom_dec_reading,fr_reading,ps_reading,alt_reading,az_reading,ir_reading,astrom_solve_time_reading,camera_time_reading = starcam_Helper.get_astrom_data(self)
                data['data']['c_time']=c_time_reading
                data['data']['gmt']=gmt_reading
                data['data']['blob_num']=blob_num_reading
                data['data']['obs_ra']=obs_ra_deading
                data['data']['astrom_ra']=astrom_ra_deading
                data['data']['obs_dec']=obs_dec_reading
                data['data']['astrom_dec']=astrom_dec_reading
                data['data']['fr']=fr_reading
                data['data']['ps']=ps_reading
                data['data']['alt']=alt_reading
                data['data']['az']=az_reading
                data['data']['ir']=ir_reading
                data['data']['astrom_solve_time']=astrom_solve_time_reading
                data['data']['camera_time']=camera_time_reading
                self.agent.publish_to_feed('starcamera,',data)
            self.agent.feed['astrometry'].flush_buffer()
            self.set_job_done()
        return True,'Acquisition exited cleanly'


    def _stop_acq(self,session,params):
        ok=False
        with self.lock:
            if self.job == 'acq':
                session.set_status('stopping')
                self.job = '!acq'
                ok = True
        return (ok, {True: 'Requested process to stop',
            False: 'Failed to request process stop.'}[ok])

    #Tasks

    @ocs_agent.param('send_commands',default=None,type=bytes)
    def send_commands(self,session,params=None):
        """ send_commands(send_commands=None)
        **Task** - Send commands to starcamera device.

        Args:
            cmds_to_camera (bytes): Commands to send to camera in byte form
        """
        cmds_to_camera = pack_cmds(self,session,params)

        with self.lock.acquire_timeout(timeout=3,job='init') as acquired:
            if acquired:
                self.socket.sendto(cmds_to_camera,self.server_addr)
            else:
                return False, "Could not acquire lock"
        return True,"Sent commands to starcamera"

    def pack_cmds(self,session,params):
        """pack_cmds
        **Function** - pack parameters stored in params dictionary into a bytes object. This function gets called in the send_commands task.
        Args:
            params

        """
        logodds = params['logodds']
        latitude = params['latitude']
        longitude = params['longitude']
        height = params['height']
        exposure = params['exposure']
        timelimit = params['timelimit']
        set_focus_to_amount = params['set_focus_to_amount']
        auto_focus_bool = params['auto_focus_bool']
        start_focus = params['start_focus']
        end_focus = params['end_focus']
        step_size = params['step_size']
        photos_per_focus = params['photos_per_focus']
        infinity_focus_bool = params['infinity_focus_bool']
        set_aperture_steps = params['set_aperture_steps']
        max_aperture_bool = params['max_aperture_bool']
        make_HP_bool = params['make_HP_bool']
        use_HP_bool = params['use_HP_bool']
        spike_limit_value = params['spike_limit_value']
        dynamic_hot_pixel_bool = params['dynamic_hot_pixel_bool']
        r_smooth_value = params['r_smooth_value']
        high_pass_filter_bool = params['high_pass_filter_bool']
        r_high_pass_filter_value = params['r_high_pass_filter_value']
        centroid_search_border_value = params['centroid_search_border_value']
        filter_return_image_bool = params['filter_return_image_bool']
        n_sigma_value = params['n_sigma_value']
        star_spacing_value = params['star_spacing_value']
        cmds_for_camera = struct.pack('ddddddfiiiiiiiiiifffffffff', logodds, latitude, longitude, height, exposure,
                                       timelimit, set_focus_to_amount, auto_focus_bool, start_focus, end_focus,
                                       step_size, photos_per_focus, infinity_focus_bool, set_aperture_steps,
                                       max_aperture_bool, make_HP_bool, use_HP_bool, spike_limit_value,
                                       dynamic_hot_pixels_bool, r_smooth_value, high_pass_filter_bool,
                                       r_high_pass_filter_value, centroid_search_border_value, filter_return_image_bool,
                                       n_sigma_value, star_spacing_value)
        return cmds_for_camera
        
def add_agent_args(parser_in=None):
    if parser_in is None:
        from argparse import ArgumentParser as A
        parser_in = A()
    pgroup = parser_in.add_argument_group('Agent Options')
    pgroup.add_argument("--ip-address",default="10.10.10.167",type=str,help="IP address of starcam computer")
    pgroup.add_argument("--user-port",default="8000",type=str,help="Port of starcam computer")
    return parser_in


if __name__ =='__main__':
    parser = add_agent_args()
    args = site_config.parse_args(agent_class="starcam_Agent",parser=parser)
    startup=True
    agent,runner = ocs_agent.init_site_agent(args)
    starcam_agent = starcam_Agent(agent,
            ip_address = args.ip_address,
            user_port = args.user_port)
    agent.register_process('acq',starcam_agent.acq,starcam_agen._stop_acq,startup=True)
    agent.register_task('send_commands',starcam_agent.send_commands)
    runner.run(agent,auto_reconnect=True)
