# -*- coding: utf-8 -*-
"""
BaseFromRaw
======

BaseFromRaw implement a bridge between the new neo.rawio API
and the neo.io legacy that give neo.core object.
The neo.rawio API is more restricted and limited and do not cover tricky
cases with asymetrical tree of neo object.
But if a fromat is done in neo.rawio the neo.io is done for free with this class.


"""

import collections
import logging
import numpy as np

from neo import logging_handler
from neo.core import (AnalogSignal, Block,
                      Epoch, Event,
                      IrregularlySampledSignal,
                      ChannelIndex,
                      Segment, SpikeTrain, Unit)
from neo.io.baseio import BaseIO

import quantities as pq

class BaseFromRaw(BaseIO):
    is_readable = True
    is_writable = False

    supported_objects = [Block, Segment, AnalogSignal, ] #ChannelIndex, SpikeTrain, Unit, Event, 
    readable_objects = [Block, Segment]
    writeable_objects = []

    is_streameable = True

    name = 'BaseIO'
    description = ''
    extentions = []

    mode = 'file'

    def __init__(self, **kargs):
        BaseIO.__init__(self, **kargs)
        self.parse_header()
    
    #~ def read_all_blocks(self, **kargs):
        #~ blocks = []
        #~ for bl_index in range(self.block_count()):
            #~ bl = self.read_block(block_index=bl_index, **kargs)
            #~ blocks.append(bl)
        #~ return blocks
    
    def read_block(self, block_index=0, lazy=False, cascade=True, signal_group_mode='group-by-same-units',  **kargs):
        
        bl = Block(name='Block {}'.format(block_index))
        if not cascade:
            return bl
        
        channels = self.header['signal_channels']
        for i, ind in self._make_channel_groups(signal_group_mode=signal_group_mode).items():
            channel_index = ChannelIndex(index=ind, channel_names=channels[ind]['name'],
                            channel_ids=channels[ind]['id'], name='Channel group {}'.format(i))
            bl.channel_indexes.append(channel_index)
        
        for seg_index in range(self.segment_count(block_index)):
            seg =  self.read_segment(block_index=block_index, seg_index=seg_index, 
                                                                lazy=lazy, cascade=cascade, signal_group_mode=signal_group_mode, **kargs)
            bl.segments.append(seg)
            
            for i, anasig in enumerate(seg.analogsignals):
                bl.channel_indexes[i].analogsignals.append(anasig)
        
        bl.create_many_to_one_relationship()
        
        return bl

    def read_segment(self, block_index=0, seg_index=0, lazy=False, cascade=True, 
                        signal_group_mode='group-by-same-units', **kargs):
        seg = Segment(index=seg_index)#name, 

        if not cascade:
            return seg
        
        
        #AnalogSignal
        signal_channels = self.header['signal_channels']
        channel_indexes=np.arange(signal_channels.size)

        if not lazy:
            raw_signal = self.get_analogsignal_chunk(block_index=block_index, seg_index=seg_index,
                        i_start=None, i_stop=None, channel_indexes=channel_indexes)
            float_signal = self.rescale_signal_raw_to_float(raw_signal,  dtype='float32', channel_indexes=channel_indexes)
        else:
            sig_shape = self.analogsignal_shape(block_index=block_index, seg_index=seg_index,)

        sample_rate = 0 #TODO
        t_start = 0 #TODO
        t_stop = 100000 #TODO
        for i, ind in self._make_channel_groups(signal_group_mode=signal_group_mode).items():
            units = np.unique(signal_channels[ind]['units'])
            assert len(units)==1
            units = units[0]

            if lazy:
                anasig = AnalogSignal(np.array([]), units=units,  copy=False,
                        sampling_rate=sample_rate*pq.Hz,t_start=t_start*pq.s)
                anasig.lay_shape = (sig_shape[0], len(ind))
            else:
                anasig = AnalogSignal(float_signal[:, ind], units=units,  copy=False,
                        sampling_rate=sample_rate*pq.Hz, t_start=t_start*pq.s)
            
            seg.analogsignals.append(anasig)
        
        
        #SpikeTrain
        unit_channels = self.header['unit_channels']
        for unit_index in range(len(unit_channels)):
            print('yep', unit_index)
            if not lazy:
                spike_timestamp = self.spike_timestamps(block_index=block_index, seg_index=seg_index, 
                                        unit_index=unit_index, ind_start=None, ind_stop=None)
                spike_times = self.rescale_spike_timestamp(spike_timestamp, 'float64')
                
                sptr = SpikeTrain(spike_times, units='s', copy=False, t_start=t_start*pq.s, t_stop=t_stop*pq.s)
            else:
                nb = self.spike_count(block_index=block_index, seg_index=seg_index, 
                                        unit_index=unit_index)
                
                sptr = SpikeTrain(np.array([]), units='s', copy=False, t_start=t_start*pq.s, t_stop=t_stop*pq.s)
                sptr.lay_shape = (nb,)
                
            seg.spiketrains.append(sptr)
            
        
        return seg
    
    def _make_channel_groups(self, signal_group_mode='group-by-same-units'):
        
        channels = self.header['signal_channels']
        groups = collections.OrderedDict()
        if signal_group_mode=='group-by-same-units':
            all_units = np.unique(channels['units'])
            print('all_units', all_units)
            for i, unit in enumerate(all_units):
                ind, = np.nonzero(channels['units']==unit)
                groups[i] = ind
                print(i, unit, ind)
        elif signal_group_mode=='split-all':
            for i in range(channels.size):
                groups[i] = np.array([i])
        else:
            raise(NotImplementedError)
        return groups
        
