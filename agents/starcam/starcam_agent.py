import numpy as np
import datetime
import time
import os
from os import environ
import socket
from ocs import ocs_agent, site_config, client_t, ocs_feed
import argparse

class starcam_Agent:
    def __init__(self, agent, ip_address, user_port):
        self.agent = agent
        self.active = True
        self.log = agent.log
        self.job = None
        self._ip = ip_address
        self._port = user_port
        ##add into on register feed


    #Process functions
    @ocs_agent.param('test_mode',default=False,type=bool)
    def acq(self,session,params=None):
        """start_acq(test_mode=False)
        **Process** - Acquire data from starcam and write to feed.

        Parameters:
            test_mode (bool,optional): Run the acq process loop only once
        
        """


    #Tasks
    @ocs_agent.param('connect',default=True,type=bool)
    def connect_starcam(self,session,params):
        """ connect_starcam(connect=True)
        **Task** - Connect starcamera device.

        Args:
            connect (bool,optional):True for connect (default, False for off

        """
        self.agent._server_addr = (self.agent._ip,self.agent._port)
        
        s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        s.connect(sef.agent._server_addr)
        self.agent._socket = s
        return True, "Connected to %s"%repr(self.agent._server_addr)

    #@ocs_agent.params('send_commands',default=True,type=bool)
    #def send_commands(self,session,params):
    #    """send_commands(send_commands=True)
    #    **Task** - Send commands to starcamera.

    #    Args:
    #        Send camera, lens and astrometry parameters to starcamera.
        
        """





    def add_agent_args(parser_in=None):
        if parser_in is None:
            from argparser import ArgumentParser as A
            parser_in = A()
        pgroup = parser_in.add_argument_group('Agent Options')
        pgroup.add_argument("--mode",default="idle",choices=['idle','acq'])
        pgroup.add_argument("--ip_address",default="10.10.10.167",type=str,help="IP address of starcam computer")
        pgroup.add_argument("--user_port",default="8000",type=str,help="Port of starcam computer")
        pgroup.add_argument("--logodds",default=1e8,type=float,help='Log odds for astrometry (controls astrometry false positives)')
        pgroup.add_argument("--latitude",default=45.619471,type=float,help='Latitude of starcamera (radians)')
        pgroup.add_argument("--longitude",default=9.220168,type=float,help='Longitude of starcamera (degrees)')
        pgroup.add_argument("--height",default=58.17,type=float,help="Height above ellipsoid")
        pgroup.add_argument("--exposure",default=700,type=float,help="Exposure (mseconds)")
        pgroup.add_argument("--timelimit",default=1,type=float,help="Timeout limit for astrometry")
        pgroup.add_argument("--set_focus_to_amount",default=0,type=float,help="User's desired focus position (counts)")
        pgroup.add_argument("--auto_focus_bool",default=1,type=int,help="Begin autofocus (boolean, 1=True, 0=False)")
        pgroup.add_argument("--start_focus",default=0,type=int,help="Where to start auto-focusing process")
        pgroup.add_argument("--end_focus",default=1000,type=int,help="Where to end auto-focusing process")
        pgroup.add_argument("--focus_step",default=5,type=int,help="Granularity of auto-focusing")
        pgroup.add_argument("--photos_per_focus",default=3,type=int,help="Number of photos per auto-focus position")
        pgroup.add_argument("--infinity_focus_boolean",default=0,type=int,help="Set focus to infinity (boolean, 1=True, 0 =False)")
        pgroup.add_argument("--set_aperture_steps",default=0,type=int,help="Number of shifts to reach desired aperture")
        pgroup.add_argument("--make_HP_bool",default=0,type=int,help="Flag to make a new static hp mask (20=re-make)")
        pgroup.add_argument("--use_HP_bool",default=1,type=int,help="Flag to use current static mask")
        pgroup.add_argument("--spike_limit_value",default=3,type=int,help="Threshold for spike")
        pgroup.add_argument("--dynamic_hot_pixels_bool",default=1,type=int,help="Flag to use dynamic hot pixels")
        pgroup.add_argument("--r_smooth_value",default=2,type=int,help="Smoothing radius (pixel) for boxcar function")
        pgroup.add_argument("--high_pass_filter_bool",default=0,type=int,help="Turn on high pass filter")
        pgroup.add_argument("--r_high_pass_filter_value",default=10,type=int,help="Smoothing radius for high pass filter (pixels)")
        pgroup.add_argument("--centroid_search_border_value",default=1,type=int,help="Pixel distance from image edge to start star search")
        pgroup.add_argument("--filter_return_image_bool",default=0,type=int,help="Return filtered imahe (boolean, 1=True,0=False)")
        pgroup.add_argument("--n_sigma_value",default=2,type=float,help="This number times noise plus mean gives raw pixel value threshold for blobs")
        pgroup.add_argument("--star_spacing_value",default=15,type=int,help="Min. number of pixel spacing between stars (pixels)")

        return parser_in


if __name__ =='__main__':
    parser = add_agent_args()
    args = site_config.parse_args(agent_class="starcam_Agent",parser=parser)
    startup=False
    if args.mode = 'connect':
        startup=True
    agent,runner = ocs_agent.init_site_agent(args)


    fdata = starcam_Agent(agent,
            ip_address = arg.ip_address,
            user_port = arg.user_port)
    agent.register_process(


