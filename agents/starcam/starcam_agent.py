import numpy as np
from numpy import random
import datetime
import time
import os
from os import environ
import socket
from ocs import ocs_agent, site_config
from ocs.ocs_twisted import TimeoutLock
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.util import sleep as dsleep
import argparse
import txaio

# For logging
txaio.use_twisted()
LOG = txaio.make_logger()

#making change

class starcam_Agent:
    def __init__(self, agent, ip_address, port, timeout):
        self.agent = agent
        self.active = True
        self.log = agent.log
        ##self.lock = TimeoutLock()
        self.job = None

        agg_params = {'frame_length': 60,
                      'exclude_influx': False}

        # register the feed
        self.agent.register_feed('pwvs',
                                 record=True,
                                 agg_params=agg_params,
                                 buffer_time=1
                                 )

        self.last_published_reading = None

    def establish_star_cam_socket(self,ip_address,port):
        """
        PROCESS: Create a socket with the Star Camera server on which to receive telemetry 
        Ags:
            ip_address (): IP address of the Star Camera
            port (): Star Camera port
        """
        # establish port with Star Camera
        server_addr = (ip_address, port)
        # TCP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(server_addr)
        print("Connected to %s" % repr(server_addr))
        return (s, ip_address,port)

    def get_starcam_data(client_socket):
        """
        PROCESS: Receive telemetry and camera settings from Star Camera.
        Args:
            client_socket (): Socket to communicate with the camera

        """
        try: 
            (StarCam_data, _) = client_socket.recvfrom(224)   
            backupStarCamData(StarCam_data)
            print("Received Star Camera data.")
            return StarCam_data
        except ConnectionResetError:
            return None
        except struct.error:
            return None




    def start_acq(self, filename, year):
        """
        PROCESS: Acquire data and write to feed
        Args:
            filename (str): name of PWV text file
            year (int): year for the corresponding Julian Day
        """
        while True:
            last_pwv, last_timestamp = read_data_from_textfile(self.filename, self.year)

            pwvs = {'block_name': 'pwvs',
                    'timestamp': last_timestamp,
                    'data': {'pwv': last_pwv}
                    }

            if self.last_published_reading is not None:
                if last_timestamp > self.last_published_reading[0]:
                    self.agent.publish_to_feed('pwvs', pwvs)
                    self.last_published_reading = (last_pwv, last_timestamp)
            else:
                self.agent.publish_to_feed('pwvs', pwvs)
                self.last_published_reading = (last_pwv, last_timestamp)

    def stop_acq(self):
        ok = False
        with self.lock:
            if self.job == 'acq':
                self.job = '!acq'
                ok = True
            return (ok, {True: 'Requested process stop.', False: 'Failed to request process stop.'}[ok])

