# coding=utf-8

#     National Oceanic and Atmospheric Administration (NOAA)
#     Alaskan Fisheries Science Center (AFSC)
#     Resource Assessment and Conservation Engineering (RACE)
#     Midwater Assessment and Conservation Engineering (MACE)

#  THIS SOFTWARE AND ITS DOCUMENTATION ARE CONSIDERED TO BE IN THE PUBLIC DOMAIN
#  AND THUS ARE AVAILABLE FOR UNRESTRICTED PUBLIC USE. THEY ARE FURNISHED "AS IS."
#  THE AUTHORS, THE UNITED STATES GOVERNMENT, ITS INSTRUMENTALITIES, OFFICERS,
#  EMPLOYEES, AND AGENTS MAKE NO WARRANTY, EXPRESS OR IMPLIED, AS TO THE USEFULNESS
#  OF THE SOFTWARE AND DOCUMENTATION FOR ANY PURPOSE. THEY ASSUME NO RESPONSIBILITY
#  (1) FOR THE USE OF THE SOFTWARE AND DOCUMENTATION; OR (2) TO PROVIDE TECHNICAL
#  SUPPORT TO USERS.

"""
.. module:: echolab2.instruments.util.simrad_parsers

    :synopsis: Parsers for Simrad raw file datagrams

| Developed by:  Zac Berkowitz <zac.berkowitz@gmail.com> under contract for
| National Oceanic and Atmospheric Administration (NOAA)
| Alaska Fisheries Science Center (AFSC)
| Midwater Assesment and Conservation Engineering Group (MACE)
|
|
| Authors:
|       Zac Berkowitz <zac.berkowitz@gmail.com>
|       Rick Towler   <rick.towler@noaa.gov>
|       Ketil Malde <ketil@malde.org>

"""

import struct
import re
import numpy as np
from date_conversion import nt_to_unix
from construct import Struct, this, Container, PaddedString, Timestamp, If
from construct import Int32ul, Int32sl, Int16ul, Array, Float32l, Float64l, Int64ul

__all__ = ['SimradSINParser', 'SimradVERParser', 'SimradPHYParser',
            'SimradPCOParser', 'SimradPINParser', 'SimradEOPParser',
            'SimradSENParser', 'SimradRAWParser', 'SimradSECParser']

def construct_to_dict(obj):
    """Recursively convert a construct data stucture into a dict."""
    if isinstance(obj, Container):
        result_dict = {}
        for key, value in obj.items():
            result_dict[key] = construct_to_dict(value)
        return result_dict
    elif isinstance(obj, list):
        return [construct_to_dict(item) for item in obj]
    else:
        return obj


class _SimradDatagramParser(object):
    '''
    '''

    def __init__(self, header_type, header_formats):
        self._id      = header_type
        self._headers = header_formats
        self._versions    = list(header_formats.keys())

    def header_fmt(self, version=0):
        return '=' + ''.join([x[1] for x in self._headers[version]])

    def header_size(self, version=0):
        return struct.calcsize(self.header_fmt(version))

    def header_fields(self, version=0):
        return [x[0] for x in self._headers[version]]

    def header(self, version=0):
        return self._headers[version][:]

    def validate_data_header(self, data):

        if isinstance(data, dict):
            type_ = data['type'][:3]
            version   = int(data['type'][3])

        elif isinstance(data, str):
            type_ = data[:3]
            version   = int(data[3])

        else:
            raise TypeError('Expected a dict or str')

        if type_ != self._id:
            raise ValueError('Expected data of type %s, not %s' %(self._id, type_))

        if version not in self._versions:
            raise ValueError('No parser available for type %s version %d' %(self._id, version))

        return type_, version

    def from_string(self, raw_string, bytes_read):

        header = raw_string[:4]
        header = header.decode()
        id_, version = self.validate_data_header(header)
        return self._unpack_contents(raw_string, bytes_read, version=version)

    def to_string(self, data={}):

        id_, version = self.validate_data_header(data)
        datagram_content_str = self._pack_contents(data, version=version)
        return self.finalize_datagram(datagram_content_str)

    def _unpack_contents(self, raw_string='', version=0):
        raise NotImplementedError

    def _pack_contents(self, data={}, version=0):
        raise NotImplementedError

    @classmethod
    def finalize_datagram(cls, datagram_content_str):
        datagram_size = len(datagram_content_str)
        final_fmt = '=l%dsl' % (datagram_size)
        return struct.pack(final_fmt, datagram_size, datagram_content_str, datagram_size)


class SimradUnknownParser(_SimradDatagramParser):
    '''
    Parser for unknown datagram types. This parser only extracts the type
    and timestampand returns the remainder of the data unparsed.

        type:         string == 'DEP0'
        low_date:     long uint representing LSBytes of 64bit NT date
        high_date:    long uint representing MSBytes of 64bit NT date
        timestamp:    datetime.datetime object of NT date, assumed to be UTC
        data:         bytearray containing the unknown datagram contents

    '''

    def __init__(self, dg_type):
        headers = {0: [('type', '4s'),
                       ('low_date', 'L'),
                       ('high_date', 'L')
                      ]
                  }
        _SimradDatagramParser.__init__(self, dg_type, headers)


    def _unpack_contents(self, raw_string, bytes_read, version):
        '''

        '''

        header_values = struct.unpack(self.header_fmt(version), raw_string[:self.header_size(version)])
        data = {}

        for indx, field in enumerate(self.header_fields(version)):
            data[field] = header_values[indx]
            if isinstance(data[field], bytes):
                #  first try to decode as utf-8 but fall back to latin_1 if that fails
                try:
                    data[field] = data[field].decode("utf-8")
                except UnicodeDecodeError:
                    data[field] = data[field].decode("latin_1")

        data['timestamp'] = nt_to_unix((data['low_date'], data['high_date']))
        data['timestamp'] = data['timestamp'].replace(tzinfo=None)
        data['bytes_read'] = bytes_read
        data['data'] = raw_string[self.header_size(version):]

        return data


    def _pack_contents(self, data, version):

        datagram_fmt      = self.header_fmt(version)
        datagram_contents = []

        for field in self.header_fields(version):
            if isinstance(data[field], str):
                data[field] = data[field].encode('latin_1')
            datagram_contents.append(data[field])

        datagram_fmt += '%ds' % (len(data['data']))
        datagram_contents.append(data['data'])

        return struct.pack(datagram_fmt, *datagram_contents)

class SimradSINParser(_SimradDatagramParser):
    """Parses SN90 system information datagrams"""
    
    def __init__(self):
        _SimradDatagramParser.__init__(self, "SIN", {0: []})

        self.dg_def = {0: Struct(
            'type' / PaddedString(4, 'ascii'),
            'timestamp' / Timestamp(Int64ul, 1e-7, 1600),
            'transceiver_count' / Int32ul,
            'transceivers' / Array(this.transceiver_count, 
                                   Struct(
                                       'ip' / Int32ul,
                                       'port' / Int16ul,
                                       'name' / PaddedString(32, 'ascii')
                                   )
                                )
                            )
                       }

    def _unpack_contents(self, raw_string, bytes_read, version):
        data = self.dg_def[version].parse(raw_string)
        data = construct_to_dict(data)
        return data
    
    def _pack_contents(self, data, version):
        pass

class SimradVERParser(_SimradDatagramParser):
    """Parses SN90 version information datagram."""
    
    def __init__(self):
        _SimradDatagramParser.__init__(self, "VER", {0: [], 1: []})
        
        self.dg_def = {0: Struct(
            'type' / PaddedString(4, 'ascii'),
            'timestamp' / Timestamp(Int64ul, 1e-7, 1600),
            'file_version' / PaddedString(32, 'ascii'),
            'software_version' / PaddedString(32, 'ascii'),
            'version_info' / PaddedString(64, 'ascii'),
            'product_name' / PaddedString(64, 'ascii')
        )}

    def _unpack_contents(self, raw_string, bytes_read, version):

        data = self.dg_def[version].parse(raw_string)
        data = construct_to_dict(data)
        return data


class SimradPHYParser(_SimradDatagramParser):
    """Parses SN90 physical configuration datagrams"""
    
    def __init__(self):
        self.dg_def = {0: Struct(
            'type' / PaddedString(4, 'ascii'),
            'timestamp' / Timestamp(Int64ul, 1e-7, 1600),
            'platform_count' / Int32sl,
            'platforms' / Array(this.platform_count,
                Struct(
                    'struct_size' / Int32sl,
                    'platform_type' / Int32sl,
                    'dimension' / If(this.platform_type == 0,
                       Struct(
                        'length' / Float32l,
                        'width' / Float32l,
                        'height' / Float32l
                       )
                    ),
                    'offset_from_centre' / If(this.platform_type == 0,
                        Struct(
                            'origin_offset_from_centre_x' / Float32l,
                            'origin_offset_from_centre_y' / Float32l,
                            'origin_offset_from_centre_z' / Float32l
                       )
                    ),
                    'name' / If(this.platform_type == 1, PaddedString(32, 'ascii')),
                    'parent_platform' / If(this.platform_type == 1, PaddedString(32, 'ascii')),
                    'rotation_x' / If(this.platform_type == 1, Float32l),
                    'rotation_y' / If(this.platform_type == 1, Float32l),
                    'rotation_z' / If(this.platform_type == 1, Float32l)
                )
            )
        )}

        _SimradDatagramParser.__init__(self, "PHY", {0: []})
        

    def _unpack_contents(self, raw_string, bytes_read, version):
        data = self.dg_def[version].parse(raw_string)
        data = construct_to_dict(data)
        return data


class SimradPINParser(_SimradDatagramParser):
    """Parses SN90 ping information datagrams"""
    
    def __init__(self):
        _SimradDatagramParser.__init__(self, "PIN", {0: [], 1: []})
        
        self.dg_def = {
            0: Struct(
                'type' / PaddedString(4, 'ascii'),
                'timestamp' / Timestamp(Int64ul, 1e-7, 1600),
                'ping_time' / Timestamp(Int64ul, 1e-7, 1600),
                'ping_number' / Int32sl,
                'latitude' / Float64l,
                'longitude' / Float64l,
                'speed'  / Float64l,
                'heading'  / Float64l,
                'heave' / Float64l,
                'roll' / Float64l,
                'pitch' / Float64l,
                'vessel_depth' / Float64l,
                'transducer_offset_x' / Float64l,
                'transducer_offset_y' / Float64l,
                'transducer_offset_z' / Float64l,
                'relative_transducer_heading' / Float64l,
                'sound_velocity' / Float64l
            ),
            1: Struct(
                'type' / PaddedString(4, 'ascii'),
                'timestamp' / Timestamp(Int64ul, 1e-7, 1600),
                'ping_time' / Timestamp(Int64ul, 1e-7, 1600),
                'ping_number' / Int32sl,
                'latitude' / Float64l,
                'longitude' / Float64l,
                'speed'  / Float64l,
                'heading'  / Float64l,
                'heave' / Float64l,
                'roll' / Float64l,
                'pitch' / Float64l,
                'vessel_depth' / Float64l,
                'vessel_distance' / Float64l,  # the only difference to PIN0
                'transducer_offset_x' / Float64l,
                'transducer_offset_y' / Float64l,
                'transducer_offset_z' / Float64l,
                'relative_transducer_heading' / Float64l,
                'sound_velocity' / Float64l
            )
        }

    def _unpack_contents(self, raw_string, bytes_read, version):

        data = self.dg_def[version].parse(raw_string)
        data = construct_to_dict(data)
        return data

class SimradEOPParser(_SimradDatagramParser):
    """Parses SN90 end of ping datagram."""
    
    def __init__(self):

        _SimradDatagramParser.__init__(self, "EOP", {0: [], 1: []})

        self.dg_def = {0: Struct(
            'type' / PaddedString(4, 'ascii'),
            'timestamp' / Timestamp(Int64ul, 1e-7, 1600)
        )}

    def _unpack_contents(self, raw_string, bytes_read, version):
        data = self.dg_def[version].parse(raw_string)
        data = construct_to_dict(data)
        return data


class SimradSENParser(_SimradDatagramParser):
    """Parses SN90 sensor datagrams"""
    
    def __init__(self):
        headers = {0: [('type', '4s'),
                       ('low_date', 'L'),
                       ('high_date', 'L'),
                       ('low_received_time', 'L'),
                       ('high_received_time', 'L'),
                       ('protocol', '32s'),
                       ('port_name', '32s'),
                       ('message_length', 'i'),
                       ]
                   }

        _SimradDatagramParser.__init__(self, "SEN", headers)
        
    def _unpack_contents(self, raw_string, bytes_read, version):
        header_values = struct.unpack(self.header_fmt(version), raw_string[:self.header_size(version)])
        data = {}

        for indx, field in enumerate(self.header_fields(version)):
            data[field] = header_values[indx]
            if isinstance(data[field], bytes):
                #  first try to decode as utf-8 but fall back to latin_1 if that fails
                try:
                    data[field] = data[field].decode("utf-8")
                except UnicodeDecodeError:
                    data[field] = data[field].decode("latin_1")

            if field in ['protocol', 'port_name']:
                data[field] = data[field].strip('\x00')

        data['timestamp'] = nt_to_unix((data['low_date'], data['high_date']))
        data['timestamp'] = data['timestamp'].replace(tzinfo=None)
        data['received_time'] = nt_to_unix((data['low_date'], data['high_date'])).replace(tzinfo=None)
        data['bytes_read'] = bytes_read
        data['parsing_completed'] = False

        return data

class SimradPCOParser(_SimradDatagramParser):
    """Parses SN90 ping configuration datagrams"""
    
    
    def __init__(self):
        _SimradDatagramParser.__init__(self, "PCO", {0: [], 1: []})
        print('xx')
        self.dg_def = Struct(
            'type' / PaddedString(4, 'ascii'),
            'timestamp' / Timestamp(Int64ul, 1e-7, 1600),
            'ping_configuration' / Struct(
                'no_of_transceivers' / Int32sl,
                'transceiver_config' / Array(this.no_of_transceivers,
                    Struct(
                        'transceiver_config_size' / Int32sl,
                        'id' / Int32sl,
                        'transceiver_name_len' / Int16ul,
                        'transceiver_name' / PaddedString(this.transceiver_name_len*2, 'utf_16_le'),
                        'split_beam_percentage' /Int32sl,
                        'txconfig' / Struct(
                            'tx_configuration_size' / Int32sl,
                            'no_of_pings' / Int32sl,
                            'tx_ping_config' / Array(this.no_of_pings,
                                Struct(
                                    'tx_ping_config_size' / Int32sl,
                                    'id' / Int32sl,
                                    'ping_name_len' / Int16ul,
                                    'ping_name' / PaddedString(this.ping_name_len*2, 'utf_16_le'),
                                    'frequency' / Float32l,
                                    'pulse_duration' /Float32l,
                                    'pulse_form' / Int32sl,
                                    'pulse_sweep' / Float32l,
                                    'pulse_slope' / Float32l,
                                    'focus_x' / Int32sl,
                                    'focus_y' / Int32sl,
                                    'beam_width_x' / Float32l,
                                    'beam_width_y' / Float32l,
                                    'steering_x' / Float32l,
                                    'steering_y' / Float32l,
                                    'beam_delay' / Float32l,
                                    'tx_amplitude' / Float32l,
                                    'tx_voltage' / Float32l,
                                    'actual_beam_bandwidth_rx' / Float64l,
                                    'decimation' / Int32sl,
                                    'range' / Float64l,
                                    'steering_vector_hcs_x' / Float32l,
                                    'steering_vector_hcs_y' / Float32l,
                                    'steering_vector_hcs_z' / Float32l,
                                    'rotation_axis_vector_x' / Float32l,
                                    'rotation_axis_vector_y' / Float32l,
                                    'rotation_axis_vector_z' / Float32l,
                                    'tx_ping_weight_x_len' / Int32sl,
                                    'tx_ping_weight_x' / Array(this.tx_ping_weight_x_len, Float32l),
                                    'tx_ping_weight_y_len' / Int32sl,
                                    'tx_ping_weight_y' / Array(this.tx_ping_weight_y_len, Float32l),
                                    'performance_info' / Struct(
                                        'tx_ping_performance_info_size' / Int32sl,
                                        'tx_power' / Float32l,
                                        'source_level' / Float32l
                                    )
                                )
                            )
                        ),
                        'rx_config' / Struct(
                            'rx_configuration_size' / Int32sl,
                            'audio_beam_index' / Int32sl,
                            'no_of_fans' / Int32sl,
                            'fans' / Array(this.no_of_fans,
                                Struct(
                                    'fan_config_size' / Int32sl,
                                    'id' / Int32sl,
                                    'fan_name_len' / Int16ul,
                                    'fan_name' / PaddedString(this.fan_name_len*2, 'utf_16_le'),
                                    'sample_interval' / Float64l,
                                    'tx_ping_id' / Int32sl,
                                    'main_beam_rx_weight_x_len' / Int32sl,
                                    'main_beam_rx_weight_x' / Array(this.main_beam_rx_weight_x_len, Float32l),
                                    'main_beam_rx_weight_y_len' / Int32sl,
                                    'main_beam_rx_weight_y' / Array(this.main_beam_rx_weight_y_len, Float32l),
                                    'split_beam_rx_weight_x_len' / Int32sl,
                                    'split_beam_rx_weight_x' / Array(this.split_beam_rx_weight_x_len, Float32l),
                                    'split_beam_rx_weight_y_len' / Int32sl,
                                    'split_beam_rx_weight_y' / Array(this.split_beam_rx_weight_y_len, Float32l),
                                    'noise_filter' / Int32sl,
                                    'processing' / Struct(
                                        'fan_processing_size' / Int32sl,
                                        'tvg_a' / Float64l,
                                        'tvg_b' / Float64l,
                                        'tvg_c' / Float64l,
                                        'rcg' / Int32sl,
                                        'agc' / Int32sl,
                                        'amp_gain' / Int32sl
                                    ),
                                    'no_of_rx_beams' / Int32sl,
                                    'rx_beams' / Array(this.no_of_rx_beams, 
                                        Struct(
                                            'rx_beam_config_size' / Int32sl,
                                            'id' / Int32sl,
                                            'beam_name_len' / Int16ul,
                                            'beam_name' / PaddedString(this.beam_name_len*2, 'utf_16_le'),
                                            'beam_width_x' / Float32l,
                                            'beam_width_y' / Float32l,
                                            'steering_x' / Float32l,
                                            'steering_y' / Float32l,
                                            'beam_type' / Int32sl,
                                            'steering_vector_hcs_x' / Float32l,
                                            'steering_vector_hcs_y' / Float32l,
                                            'steering_vector_hcs_z' / Float32l,
                                            'processing_type' / Int32sl,
                                            'performance_info' / Struct(
                                                'rx_beam_performance_info_size' / Int32sl,
                                                'directivity_index' / Float32l,
                                                'gain' / Float32l,
                                                'gain_adjust' / Float32l,
                                                'sa_correction' / Float32l,
                                                'sa_correction_adjust' / Float32l,
                                                'equivalent_beam_angle' / Float32l,
                                                'absorption_coefficient' / Float32l,
                                                'angle_sensitivity_alongship' / Float32l,
                                                'angle_sensitivity_athwartship' / Float32l
                                            ),
                                            'rx_delay' / If (this._._._._._.type == 'PCO1', Int32sl)
                                        )
                                    ),
                                    'rx_delay' / If (this._._._._.type == 'PCO1', Int32sl) 
                                )
                            )
                        ),
                        'transmission_mode' / Int32sl
                    )
                ),
                'hint_since_last_len' / Int16ul,
                'hint_since_last' / PaddedString(this.hint_since_last_len*2, 'utf_16_le'),
                'hint_since_last_ping_len' / Int16ul,
                'hint_since_last_ping' / PaddedString(this.hint_since_last_ping_len*2, 'utf_16_le')
            )
        )
        
    def _unpack_contents(self, raw_string, bytes_read, version):

        data = self.dg_def.parse(raw_string)
        data = construct_to_dict(data)
        return data

class SimradSECParser(_SimradDatagramParser):
    """Parses SN90 sensor configuration datagrams"""
    
    def __init__(self):
        headers = {0: [('type', '4s'),
                       ('low_date', 'L'),
                       ('high_date', 'L'),
                       ],
                   }

        _SimradDatagramParser.__init__(self, "SEC", headers)
        
    def _unpack_contents(self, raw_string, bytes_read, version):
        header_values = struct.unpack(self.header_fmt(version), raw_string[:self.header_size(version)])
        data = {}

        for indx, field in enumerate(self.header_fields(version)):
            data[field] = header_values[indx]
            if isinstance(data[field], bytes):
                #  first try to decode as utf-8 but fall back to latin_1 if that fails
                try:
                    data[field] = data[field].decode("utf-8")
                except UnicodeDecodeError:
                    data[field] = data[field].decode("latin_1")

        data['timestamp'] = nt_to_unix((data['low_date'], data['high_date'])).replace(tzinfo=None)
        data['bytes_read'] = bytes_read
        data['parsing_completed'] = False

        data['xml'] = raw_string[self.header_size(version):].decode('utf-8')

        return data


class SimradNMEAParser(_SimradDatagramParser):
    '''
    ER60 NMEA datagram contains the following keys:


        type:         string == 'NME0'
        low_date:     long uint representing LSBytes of 64bit NT date
        high_date:    long uint representing MSBytes of 64bit NT date
        timestamp:     datetime.datetime object of NT date, assumed to be UTC

        nmea_string:  full (original) NMEA string

    The following methods are defined:

        from_string(str):    parse a raw ER60 NMEA datagram
                            (with leading/trailing datagram size stripped)

        to_string():         Returns the datagram as a raw string (including leading/trailing size fields)
                            ready for writing to disk
    '''

    nmea_head_re = re.compile(r'\$[A-Za-z]{5},')

    def __init__(self):
        headers = {0: [('type', '4s'),
                       ('low_date', 'L'),
                       ('high_date', 'L')
                      ]}

        _SimradDatagramParser.__init__(self, "NME", headers)


    def _unpack_contents(self, raw_string, bytes_read, version):
        '''
        Parses the NMEA string provided in raw_string

        :param raw_string:  Raw NMEA strin (i.e. '$GPZDA,160012.71,11,03,2004,-1,00*7D')
        :type raw_string: str

        :returns: None
        '''

        header_values = struct.unpack(self.header_fmt(version), raw_string[:self.header_size(version)])
        data = {}

        for indx, field in enumerate(self.header_fields(version)):
            data[field] = header_values[indx]
            if isinstance(data[field], bytes):
                #  first try to decode as utf-8 but fall back to latin_1 if that fails
                try:
                    data[field] = data[field].decode("utf-8")
                except UnicodeDecodeError:
                    data[field] = data[field].decode("latin_1")

        data['timestamp'] = nt_to_unix((data['low_date'], data['high_date']))
        data['timestamp'] = data['timestamp'].replace(tzinfo=None)
        data['bytes_read'] = bytes_read

        if version == 0:

            data['nmea_string'] = str(raw_string[self.header_size(version):].strip(b'\x00'), 'ascii', errors='replace')

            if self.nmea_head_re.match(data['nmea_string'][:7]) is not None:
                data['nmea_talker'] = data['nmea_string'][1:3]
                data['nmea_type']   = data['nmea_string'][3:6]
            else:
                data['nmea_talker'] = ''
                data['nmea_type']   = 'UNKNOWN'

        return data

    def _pack_contents(self, data, version):

        datagram_fmt      = self.header_fmt(version)
        datagram_contents = []

        if version == 0:

            for field in self.header_fields(version):
                if isinstance(data[field], str):
                    data[field] = data[field].encode('latin_1')
                datagram_contents.append(data[field])

            if data['nmea_string'][-1] != '\x00':
                tmp_string = data['nmea_string'] + '\x00'
            else:
                tmp_string = data['nmea_string']

            #Pad with more nulls to 4-byte word boundry if necessary
            if len(tmp_string) % 4:
                tmp_string += '\x00' * (4 - (len(tmp_string) % 4))

            datagram_fmt += '%ds' % (len(tmp_string))

            #Convert to python string if needed
            if isinstance(tmp_string, str):
                tmp_string = tmp_string.encode('ascii', errors='replace')

            datagram_contents.append(tmp_string)


        return struct.pack(datagram_fmt, *datagram_contents)




class SimradRawParser(_SimradDatagramParser):
    '''
    Sample Data Datagram parser operates on dictonaries with the following keys:

        type:         string == 'RAW0'
        low_date:     long uint representing LSBytes of 64bit NT date
        high_date:    long uint representing MSBytes of 64bit NT date
        timestamp:    datetime.datetime object of NT date, assumed to be UTC

        channel                         [short] Channel number
        mode                            [short] 1 = Power only, 2 = Angle only 3 = Power & Angle
        transducer_depth                [float]
        frequency                       [float]
        transmit_power                  [float]
        pulse_length                    [float]
        bandwidth                       [float]
        sample_interval                 [float]
        sound_velocity                  [float]
        absorption_coefficient          [float]
        heave                           [float]
        roll                            [float]
        pitch                           [float]
        temperature                     [float]
        heading                         [float]
        transmit_mode                   [short] 0 = Active, 1 = Passive, 2 = Test, -1 = Unknown
        spare0                          [str]
        offset                          [long]
        count                           [long]

        power                           [numpy array] Unconverted power values (if present)
        angle                           [numpy array] Unconverted angle values (if present)

    from_string(str):   parse a raw sample datagram
                        (with leading/trailing datagram size stripped)

    to_string(dict):    Returns raw string (including leading/trailing size fields)
                        ready for writing to disk
    '''

    def __init__(self):
        headers = {0 : [('type', '4s'),
                        ('low_date', 'L'),
                        ('high_date', 'L'),
                        ('channel', 'h'),
                        ('mode', 'h'),
                        ('transducer_depth', 'f'),
                        ('frequency', 'f'),
                        ('transmit_power', 'f'),
                        ('pulse_length', 'f'),
                        ('bandwidth', 'f'),
                        ('sample_interval', 'f'),
                        ('sound_velocity', 'f'),
                        ('absorption_coefficient', 'f'),
                        ('heave', 'f'),
                        ('roll', 'f'),
                        ('pitch', 'f'),
                        ('temperature', 'f'),
                        ('heading', 'f'),
                        ('transmit_mode', 'h'),
                        ('spare0', '6s'),
                        ('offset', 'l'),
                        ('count', 'l')
                        ],
                   2 : [('type', '4s'),
                        ('low_date', 'L'),
                        ('high_date', 'L'),
                        ('ipaddress', 'I'),
                        ('port', 'H'),
                        ('padding', 'H'),
                        ('message_length', 'l'),
                        ],
                   3 : [('type', '4s'),
                        ('low_date', 'L'),
                        ('high_date', 'L'),
                        ('channel_id', '128s'),
                        ('data_type', 'h'),
                        ('spare', '2s'),
                        ('offset', 'l'),
                        ('count', 'l')
                        ],
                    4 : [('type', '4s'),
                        ('low_date', 'L'),
                        ('high_date', 'L'),
                        ('channel_id', '128s'),
                        ('data_type', 'h'),
                        ('spare', '2s'),
                        ('offset', 'l'),
                        ('count', 'l')
                        ]
                    }
        _SimradDatagramParser.__init__(self, 'RAW', headers)

    def _unpack_contents(self, raw_string, bytes_read, version):

        header_values = struct.unpack(self.header_fmt(version), raw_string[:self.header_size(version)])

        data = {}

        for indx, field in enumerate(self.header_fields(version)):
            data[field] = header_values[indx]
            if isinstance(data[field], bytes):
                #  first try to decode as utf-8 but fall back to latin_1 if that fails
                try:
                    data[field] = data[field].decode("utf-8")
                except UnicodeDecodeError:
                    data[field] = data[field].decode("latin_1")

        data['timestamp'] = nt_to_unix((data['low_date'], data['high_date']))
        data['timestamp'] = data['timestamp'].replace(tzinfo=None)
        data['bytes_read'] = bytes_read

        if version == 0:

            if data['count'] > 0:
                block_size = data['count'] * 2
                indx = self.header_size(version)

                if int(data['mode']) & 0x1:
                    data['power'] = np.frombuffer(raw_string[indx:indx + block_size], dtype='int16')
                    indx += block_size
                else:
                    data['power'] = None

                if int(data['mode']) & 0x2:
                    data['angle'] = np.frombuffer(raw_string[indx:indx + block_size], dtype='int8')
                    data['angle'].shape = (data['count'], 2)
                else:
                    data['angle'] = None

            else:
                data['power'] = np.empty((0,), dtype='int16')
                data['angle'] = np.empty((0,), dtype='int8')
        elif version == 2:
            data['parsing_completed'] = False
        elif version == 3 or version == 4:

            #  clean up the channel ID
            data['channel_id'] = data['channel_id'].strip('\x00')

            if data['count'] > 0:

                #  set the initial block size and indx value.
                block_size = data['count'] * 2
                indx = self.header_size(version)

                if data['data_type'] & 0b1:
                    data['power'] = np.frombuffer(raw_string[indx:indx + block_size], dtype='int16')
                    indx += block_size
                else:
                    data['power'] = None

                if data['data_type'] & 0b10:
                    data['angle'] = np.frombuffer(raw_string[indx:indx + block_size], dtype='int8')
                    data['angle'].shape = (data['count'], 2)
                    indx += block_size
                else:
                    data['angle'] = None

                #  determine the complex sample data type - this is contained in bits 2 and 3
                #  of the datatype <short> value. I'm assuming the types are exclusive...
                #  Note that Numpy doesn't support the complex32 type so both the full precision
                #  (complex comprised of 2 32-bit floats) and reduced precision (complex
                #  comprised of 2 16-bit floats) are returned as np.complex64 which is complex
                #  comprised of 2 32-bit floats.
                data['complex_dtype'] = np.float16
                type_bytes = 2
                if ((data['data_type'] & 0b1000)):
                     data['complex_dtype'] = np.float32
                     type_bytes = 4

                #  determine the number of complex samples
                data['n_complex'] = data['data_type'] >> 8

                #  unpack the complex samples
                if (data['n_complex'] > 0):
                    #  determine the block size (complex data are comprised
                    #  of two values so we have to double this)
                    block_size = 2 * data['count'] * data['n_complex'] * type_bytes

                    #  convert and reshape the raw string data
                    data['complex'] = np.frombuffer(raw_string[indx:indx + block_size],
                            dtype=data['complex_dtype'])
                    data['complex'].shape = (data['count'], 2 * data['n_complex'])
                    data['complex'].dtype = np.complex64
                else:
                    data['complex'] = None

            else:
                data['power'] = np.empty((0,), dtype='int16')
                data['angle'] = np.empty((0,), dtype='int8')
                data['complex'] = np.empty((0,), dtype='complex64')
                data['n_complex'] = 0

        return data

    def _pack_contents(self, data, version):

        datagram_fmt = self.header_fmt(version)
        datagram_contents = []

        if version == 0:

            if data['count'] > 0 and data['mode'] == 0:
                    data['count'] = 0

            for field in self.header_fields(version):
                if isinstance(data[field], str):
                    data[field] = data[field].encode('latin_1')
                datagram_contents.append(data[field])

            if data['count'] > 0:

                if int(data['mode']) & 0x1:
                    datagram_fmt += '%dh' % (data['count'])
                    datagram_contents.extend(data['power'])

                if int(data['mode']) & 0x2:
                    n_angles = data['count'] * 2
                    datagram_fmt += '%db' % (n_angles)
                    #  reshape the angle array for writing
                    data['angle'].shape=(n_angles,)
                    datagram_contents.extend(data['angle'])

        elif version == 3 or version == 4:

            # Add the spare field
            data['spare'] = ''

            # work through the parameter dict and append data values to the
            # packed datagram list.
            for field in self.header_fields(version):
                if isinstance(data[field], str):
                    data[field] = data[field].encode('latin_1')
                datagram_contents.append(data[field])

            # Check if we have data to write
            if data['count'] > 0:

                if data['data_type'] & 0b0001:
                    # Add the power data
                    datagram_fmt += '%dh' % (data['count'])
                    datagram_contents.extend(data['power'])

                if data['data_type'] & 0b0010:
                    # Add the angle data
                    n_angles = data['count'] * 2
                    datagram_fmt += '%db' % (n_angles)
                    #  reshape the angle array for writing
                    data['angle'].shape=(n_angles,)
                    datagram_contents.extend(data['angle'])

                if data['data_type'] & 0b1100:
                    # Add the complex data
                    if data['data_type'] & 0b0100:
                        # pack as 16 bit floats - struct doesn't have support for
                        # half floats so we use just pack them as bytes.
                        datagram_fmt += '%dB' % (data['complex'].shape[0] * 2)
                    else:
                        # pack as 32 bit floats
                        datagram_fmt += '%dB' % (data['complex'].shape[0] * 4)
                    datagram_contents.extend(data['complex'].view(np.ubyte))

        return struct.pack(datagram_fmt, *datagram_contents)
