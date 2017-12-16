"""

FoxDot is a Python library and programming environment that provides a fast and
user-friendly abstraction to the powerful audio-engine, SuperCollider. It comes
with its own IDE, which means it can be used straight out of the box; all you need
is Python and SuperCollider and you're ready to go!

For more information on installation, check out [the guide](http://foxdot.org/installation),
or if you're already set up, you can also find a useful starter guide that introduces the
key components of FoxDot on [the website](http://foxdot.org/).

Please see the documentation for more detailed information on the FoxDot classes
and how to implement them.

Copyright Ryan Kirkbride 2015
"""

from __future__ import absolute_import, division, print_function

import logging

from .Code import *

FoxDotCode.namespace = globals()

from .TempoClock import *
from .Buffers import *
from .Players import *
from .Patterns import *
from .Effects import *
from .TimeVar import *
from .Constants import *
from .Midi import *
from .Settings import *
from .SCLang._SynthDefs import *
from .ServerManager import *
from .SCLang import SynthDefs, Env, SynthDef, CompiledSynthDef
from .Root import Root
from .Scale import Scale
from .Utils import processSample
from .Workspace import get_keywords

# stdlib imports

from random import choice as choose

# Define any custom functions

@PatternMethod
def __getitem__(self, key):
    """ Overrides the Pattern.__getitem__ to allow indexing
        by TimeVar and PlayerKey instances. """
    if isinstance(key, PlayerKey):
        # Create a player key whose calculation is get_item
        return key.index(self)
    elif isinstance(key, TimeVar):
        # Create a TimeVar of a PGroup that can then be indexed by the key
        item = TimeVar(tuple(self.data))
        item.dependency = key
        item.evaluate = fetch(Get)
        return item
    else:
        return self.getitem(key)

def _futureBarDecorator(n, multiplier=1):
    if callable(n):
        Clock.schedule(n, Clock.next_bar())
        return n
    def wrapper(f):
        Clock.schedule(f, Clock.next_bar() + (n * multiplier))
        return f
    return wrapper

def nextBar(n=0):
    ''' Schedule functions when you define them with @nextBar
    Functions will run n beats into the next bar.

    >>> nextBar(v1.solo)
    or
    >>> @nextBar
    ... def dostuff():
    ...     v1.solo()
    '''
    return _futureBarDecorator(n)

def futureBar(n=0):
    ''' Schedule functions when you define them with @futureBar
    Functions will run n bars in the future (0 is the next bar)

    >>> futureBar(v1.solo)
    or
    >>> @futureBar(4)
    ... def dostuff():
    ...     v1.solo()
    '''
    return _futureBarDecorator(n, Clock.bar_length())

def update_foxdot_clock(clock):
    """ Tells the TimeVar, Player, and MidiIn classes to use
        a new instance of TempoClock. """

    assert isinstance(clock, TempoClock)

    for item in (TimeVar, Player, MidiIn, Trigger):

        item.set_clock(clock)

def update_foxdot_server(serv):
    """ Tells the `Effect` and`TempoClock`classes to send OSC messages to
        a new ServerManager instance.
    """

    assert isinstance(serv, ServerManager)

    TempoClock.set_server(serv)
    SynthDefs.set_server(serv)
    Trigger.set_server(serv)

    return

def instantiate_player_objects():
    """ Instantiates all two-character variable Player Objects """
    alphabet = list('abcdefghijklmnopqrstuvwxyz')
    numbers  = list('0123456789')

    for char1 in alphabet:

        group = []

        for char2 in alphabet + numbers:

            arg = char1 + char2

            FoxDotCode.namespace[arg] = Player(arg)

            group.append(arg)

        FoxDotCode.namespace[char1 + "_all"] = Group(*[FoxDotCode.namespace[char1+str(n)] for n in range(10)])

    return


class Trigger(object):
    """
    Triggers a sample to play once

    :param quant: Quantize the trigger on this beat

    """
    server = None
    clock = None
    queue_block = None

    def __init__(self, filename, sample=0, pos=0, fin=-1, dur=0, stretch=0,
                 rate=1, amp=1, delay=0, quant=1):
        now = Clock.now()
        if quant == 0:
            # Can't run immediately; the buffer might need to load.
            next_run = now + .01
        else:
            next_run = now + quant - now % quant
        Clock.schedule(self, next_run + delay)

        if len(filename) == 1:
            sample = Samples.getSampleFromSymbol(filename, sample)
            self.buf = sample.bufnum
        else:
            self.buf = Samples.loadBuffer(filename, sample)
        self.pos = pos
        self.fin = fin
        if dur > 0:
            self.dur = clock.beat_dur(dur)
        else:
            self.dur = dur
        self.stretch = stretch
        self.rate = rate
        self.amp = amp

    @classmethod
    def set_server(cls, server):
        cls.server = server

    @classmethod
    def set_clock(cls, clock):
        cls.clock = clock

    @classmethod
    def set_queue_block(cls, queue_block):
        cls.queue_block = queue_block

    def __call__(self):
        message = processSample(self.server, self.clock, self.buf, self.pos,
                                self.fin, self.dur, self.stretch, self.rate)
        message['amp'] = self.amp
        info = self.server.getBufferInfo(self.buf)
        if info is None:
            synthdef = 'play1'
        else:
            synthdef = 'play1' if info.channels == 1 else 'play2'

        # No fx for now
        effects = {}
        bundle = self.server.get_bundle(synthdef, message, effects)
        self.queue_block.osc_messages.append(bundle)

trigger = Trigger


def Master():
    """ Returns a `Group` containing all the players currently active in the Clock """
    return Group(*Clock.playing)

# Create a clock and define functions

logging.basicConfig(level=logging.ERROR)
when.set_namespace(FoxDotCode) # experimental

Clock = TempoClock()
update_foxdot_server(DefaultServer)
update_foxdot_clock(Clock)
instantiate_player_objects()
