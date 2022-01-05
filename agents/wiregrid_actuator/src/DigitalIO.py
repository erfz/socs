

class DigitalIO:
    """
    The digitalIO class to read & control the digital IOs
    via the Galil actuator controller.

    Args:
        name(string)    : Name of this instance
        io_list(list)   : IO configurations
        g(gclib.py())   : Actuator controller library
        verbose(int)    : Verbosity level
    """

    def __init__(self, name, io_list, g,
                 get_onoff_reverse=False, set_onoff_reverse=False, verbose=0):
        self.name = name
        self.g = g
        self.get_reverse = get_onoff_reverse
        self.set_reverse = set_onoff_reverse
        self.verbose = verbose

        self.io_list = io_list
        self.io_names = [io['name'] for io in io_list]
        self.io_labels = [io['label'] for io in io_list]
        self.io_indices = {io['name']: index
                           for index, io in enumerate(io_list)}
        self.io_dict = {io['name']: io['io'] for io in io_list}
        # Retrieve IO number: io OUT[3] --> 3
        self.io_numdict = \
            {name: (int)(io.split('[')[1].split(']')[0])
                for name, io in self.io_dict.items()}

    def _get_onoff(self, io_name):
        onoff = self.g.GCommand('MG @{}'.format(self.io_dict[io_name]))
        try:
            onoff = bool(float(onoff.strip()))
        except ValueError as e:
            msg = \
                'DigitalIO[{}]:_get_onoff(): ERROR!: '\
                'Failed to get correct on/off message '\
                'from the controller.\n'.format(self.name)\
                + 'DigitalIO[{}]:_get_onoff(): '\
                  ' message = "{}" | Exception = "{}"'\
                  .format(self.name, onoff, e)
            print(msg)
            raise ValueError(e)
        if self.get_reverse:
            onoff = not onoff
        # print('DigitalIO[{}]:_get_onoff(): onoff for {}: {}'
        #      .format(self.name, io_name, onoff))
        return int(onoff)

    def get_onoff(self, io_name=None):
        """
        Get True/False (ON/OFF) for the digital IOs
        If io_name=None, return a list of the ON/OFFs for all the IOs
        If io_name is list, return a list of the ON/OFFs for asked IOs
        If io_name is string (one IO), return one ON/OFF

        Args:
            io_name is a string of a IO name or list of IO names
        Return value:
            list of True/False or one True/Falsel
                True  : ON
                False : OFF
        """
        if io_name is None:
            onoff = [self._get_onoff(name) for name in self.io_names]
        elif isinstance(io_name, list):
            if not all([(name in self.io_names) for name in io_name]):
                msg = \
                    'DigitalIO[{}]:get_onoff(): ERROR!: '\
                    .format(self.name) \
                    + 'There is no matched IO name.\n'\
                      'DigitalIO[{}]:get_onoff():       '\
                      .format(self.name)\
                    + 'Assigned IO names = {}\n'\
                      .format(self.io_names)\
                    + 'DigitalIO[{}]:get_onoff():       '\
                      'Asked IO names = {}'.format(self.name, io_name)
                print(msg)
                raise ValueError(msg)
            onoff = [self._get_onoff(name) for name in io_name]
        else:
            if not (io_name in self.io_names):
                msg = \
                    'DigitalIO[{}]:get_onoff(): ERROR!: '\
                    'There is no IO name of {}.\n'\
                    .format(self.name, io_name) \
                    + 'DigitalIO[{}]:get_onoff():         '\
                      'Assigned IO names = {}'.format(self.name, self.io_names)
                print(msg)
                raise ValueError(msg)
            onoff = self._get_onoff(io_name)
        return onoff

    def get_label(self, io_name):
        if io_name is None:
            label = self.io_labels
        elif isinstance(io_name, list):
            if not all([(name in self.io_names) for name in io_name]):
                msg = \
                    'DigitalIO[{}]:get_label(): ERROR!: '\
                    'There is no matched IO name.\n'\
                    .format(self.name)\
                    + 'DigitalIO[{}]:get_label():     '\
                      'Assigned IO names = {}\n'\
                      .format(self.name, self.io_names)\
                    + 'DigitalIO[{}]:get_label():     '\
                      'Asked IO names    = {}'.format(self.name, io_name)
                print(msg)
                raise ValueError(msg)
            label = [self.io_indices[name] for name in io_name]
        else:
            if not (io_name in self.io_names):
                msg = \
                    'DigitalIO[{}]:get_label(): ERROR!: '\
                    'There is no IO name of {}.\n'\
                    .format(self.name, io_name) \
                    + 'DigitalIO[{}]:get_label():     '\
                      'Assigned IO names = {}'.format(self.name, self.io_names)
                print(msg)
                raise ValueError(msg)
            label = self.io_label(io_name)
        return label

    def _set_onoff(self, onoff, io_name):
        io_num = self.io_numdict[io_name]
        onoff = bool(int(onoff))
        if self.set_reverse:
            onoff = not onoff
        if onoff:
            cmd = 'SB {}'.format(io_num)
        else:
            cmd = 'CB {}'.format(io_num)
        self.g.GCommand(cmd)
        return True

    def set_onoff(self, onoff=0, io_name=None):
        """
        Set True/False (ON/OFF) for the digital IOs
        If io_name=None, return a list of the ON/OFFs for all the IOs
        If io_name is list, return a list of the ON/OFFs for asked IOs
        If io_name is string (one IO), return one ON/OFF

        Args:
            onoff: 0 (OFF) or 1 (ON)
            io_name: a string of a IO name or list of IO names
        Return value:
            True
        """
        set_io_names = []
        if io_name is None:
            set_io_names = self.io_names
        elif isinstance(io_name, list):
            if not all([(name in self.io_names) for name in io_name]):
                msg = \
                    'DigitalIO[{}]:set_onoff(): ERROR!: '\
                    'There is no matched IO name.\n'\
                    .format(self.name)\
                    + 'DigitalIO[{}]:set_onoff():    '\
                      'Assigned IO names = {}\n'\
                      .format(self.name, self.io_names)\
                    + 'DigitalIO[{}]:set_onoff():     '\
                      'Asked IO names    = {}'\
                      .format(self.name, io_name)
                print(msg)
                raise ValueError(msg)
            set_io_names = io_name
        else:
            if not (io_name in self.io_names):
                msg = \
                    'DigitalIO[{}]:set_onoff(): ERROR!: '\
                    'There is no IO name of {}.\n'\
                    .format(self.name, io_name)\
                    + 'DigitalIO[{}]:set_onoff():     '\
                      'Assigned IO names = {}'.format(self.name, self.io_names)
                print(msg)
                raise ValueError(msg)
            set_io_names = [io_name]
        print('DigitalIO[{}]:set_onoff(): Set {} for the IOs: '
              '{}'.format(self.name, 'ON' if onoff else 'OFF', set_io_names))
        for name in set_io_names:
            self._set_onoff(onoff, name)
        return True

    def set_allon(self):
        print('DigitalIO[{}]:set_allon(): '
              'Set ON for all of the digital IOs'.format(self.name))
        return self.set_onoff(1, None)

    def set_alloff(self):
        print('DigitalIO[{}]:set_allon(): '
              'Set OFF for all of the digital IOs'.format(self.name))
        return self.set_onoff(0, None)