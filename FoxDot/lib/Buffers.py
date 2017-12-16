"""

This module manages the allocation of buffer numbers and samples. To see
a list of descriptions of what sounds are mapped to what characters,
simply evaluate

    print(Samples)

Future:

Aiming on being able to set individual sample banks for different players
that can be proggrammed into performance.

"""
from __future__ import absolute_import, division, print_function

import fnmatch
import os
from contextlib import closing
from itertools import chain
from os.path import abspath, join, isabs, isfile, isdir, splitext

from .Code import WarningMsg
from .Logging import Timing
from .SCLang import SampleSynthDef
from .ServerManager import DefaultServer
from .Settings import FOXDOT_SND, FOXDOT_LOOP


alpha    = "abcdefghijklmnopqrstuvwxyz"

nonalpha = {"&" : "ampersand",
            "*" : "asterix",
            "@" : "at",
            "|" : "bar",
            "^" : "caret",
            ":" : "colon",
            "$" : "dollar",
            "=" : "equals",
            "!" : "exclamation",
            "/" : "forwardslash",
            ">" : "greaterthan",
            "#" : "hash",
            "-" : "hyphen",
            "<" : "lessthan",
            "%" : "percent",
            "+" : "plus",
            "?" : "question",
            "~" : "tilde",
            "\\" :"backslash",
            "1" : "1",
            "2" : "2",
            "3" : "3",
            "4" : "4" }

DESCRIPTIONS = { 'a' : "Gameboy hihat", 'A' : "Sword",
                 'b' : "Cowbell",       'B' : "Short saw",
                 'c' : "Box",           'C' : "Choral",
                 'd' : "Click",         'D' : "Buzz",
                 'e' : "Cowbell",       'E' : "Sparkle",
                 'f' : "Wood",          'F' : "Swipe",
                 'g' : "Ominous",       'G' : "Stab",
                 'h' : "Rough clap",    'H' : "Clap",
                 'i' : "Jungle snare",  'I' : "Rock snare",
                 'j' : "Jug",           'J' : "Reverse",
                 'k' : "Bass",          'K' : "Dub shot",
                 'l' : "Knock",         'L' : "Siren",
                 'm' : "Toms",          'M' : "Electro Tom",
                 'n' : "Noise",         'N' : "Gameboy SFX",
                 'o' : "Snare drum",    'O' : "Heavy snare",
                 'p' : "Tabla 1",       'P' : "Tabla long",
                 'q' : "Table 2",       'Q' : "Tabla long",
                 'r' : "Metal",         'R' : "Metallic",
                 's' : "Shaker",        'S' : "Tamborine",
                 't' : "Cowbell",       'T' : "Cowbell",
                 'u' : "Frying pan",    'U' : "Misc. Fx",
                 'v' : "Kick drum 3",   'V' : "Soft kick",
                 'w' : "Dub hits",      'W' : "Distorted",
                 'x' : "Bass drum 1",   'X' : "Heavy kick",
                 'y' : "Bleep",         'Y' : "High buzz",
                 'z' : "Scratch",       "Z" : "Buzz",
                 '-' : "Hi hat closed", "|" : "Glitch",
                 '=' : "Hi hat open",   "/" : "Reverse sounds",
                 '*' : "Clap",          "\\" : "Lazer",
                 '~' : "Ride cymbal",
                 '^' : "'Donk'",
                 '#' : "Crash",
                 '+' : "Clicks",
                 '@' : "Computer",
                 '1' : "Vocals (One)",
                 '2' : 'Vocals (Two)',
                 '3' : 'Vocals (Three)',
                 '4' : 'Vocals (Four)'}


def symbolToDir(symbol):
    """ Return the sample search directory for a symbol """
    if symbol.isalpha():
        return join(
            FOXDOT_SND,
            symbol.lower(),
            'upper' if symbol.isupper() else 'lower'
        )
    elif symbol in nonalpha:
        longname = nonalpha[symbol]
        return join(FOXDOT_SND, '_', longname)
    else:
        return None


class BufferManager(object):
    def __init__(self, server=DefaultServer, paths=()):
        self._server = server
        self._max_buffers = server.max_buffers
        # Keep buffer 0 unallocated because we use it as the "nil" buffer
        self._nextbuf = 1
        self._buffers = [None for _ in range(self._max_buffers)]
        self._fn_to_buf = {}
        self._paths = [FOXDOT_LOOP] + list(paths)
        self._ext = ['wav', 'wave', 'aif', 'aiff', 'flac']

    def __str__(self):
        return "\n".join(["%r: %s" % (k, v) for k, v in sorted(DESCRIPTIONS.items())])

    def __repr__(self):
        return '<BufferManager>'

    def _incr_nextbuf(self):
        self._nextbuf += 1
        if self._nextbuf >= self._max_buffers:
            self._nextbuf = 1

    def _getNextBufnum(self):
        """ Get the next free buffer number """
        start = self._nextbuf
        while self._buffers[self._nextbuf] is not None:
            self._incr_nextbuf()
            if self._nextbuf == start:
                raise RuntimeError("Buffers full! Cannot allocate additional buffers.")
        freebuf = self._nextbuf
        self._incr_nextbuf()
        return freebuf

    def addPath(self, path):
        """ Add a path to the search paths for samples """
        self._paths.append(abspath(path))

    def free(self, bufnum):
        """ Free a buffer. Accepts a filename or buffer number """
        if fn is not None:
            del self._fn_to_buf[fn]
            self._buffers[bufnum] = None
            self._server.bufferFree(bufnum)

    def freeAll(self):
        """ Free all buffers """
        buffers = list(self._fn_to_buf.values())
        for bufnum in buffers:
            self.free(bufnum)

    def setMaxBuffers(self, max_buffers):
        """ Set the max buffers on the SC server """
        if max_buffers < self._max_buffers:
            if any(self._buffers[max_buffers:]):
                raise RuntimeError(
                    "Cannot shrink buffer size. Buffers already allocated."
                )
            self._buffers = self._buffers[:max_buffers]
        elif max_buffers > self._max_buffers:
            while len(self._buffers) < max_buffers:
                self._buffers.append(None)
        self._max_buffers = max_buffers
        self._nextbuf = self._nextbuf % max_buffers

    def getBufferFromSymbol(self, symbol, index=0):
        """ Get buffer information from a symbol """
        if symbol.isspace():
            return 0
        dirname = symbolToDir(symbol)
        if dirname is None:
            return 0
        samplepath = self._findSample(dirname, index)
        if samplepath is None:
            return 0
        return self._allocateAndLoad(samplepath)

    def getBufferInfo(self, bufnum):
        """ Proxy to fetch buffer info from server """
        return self._server.getBufferInfo(bufnum)

    def _allocateAndLoad(self, filename):
        """ Allocates and loads a buffer from a filename, with caching """
        if filename not in self._fn_to_buf:
            bufnum = self._getNextBufnum()
            self._server.bufferRead(filename, bufnum)
            self._fn_to_buf[filename] = bufnum
            self._buffers[bufnum] = filename
        return self._fn_to_buf[filename]

    def _getSoundFile(self, filename):
        """ Look for a file with all possible extensions """
        base, cur_ext = splitext(filename)
        if cur_ext:
            # If the filename already has an extensions, keep it
            if isfile(filename):
                return filename
        else:
            # Otherwise, look for all possible extensions
            for ext in self._ext:
                # Look for .wav and .WAV
                for tryext in [ext, ext.upper()]:
                    extpath = filename + '.' + tryext
                    if isfile(extpath):
                        return extpath
        return None

    def _getSoundFileOrDir(self, filename):
        """ Get a matching sound file or directory """
        if isdir(filename):
            return abspath(filename)
        foundfile = self._getSoundFile(filename)
        if foundfile:
            return abspath(foundfile)
        return None

    def _searchPaths(self, filename):
        """ Search our search paths for an audio file or directory """
        if isabs(filename):
            return self._getSoundFileOrDir(filename)
        else:
            for root in self._paths:
                fullpath = join(root, filename)
                foundfile = self._getSoundFileOrDir(fullpath)
                if foundfile:
                    return foundfile
        return None

    def _getFileInDir(self, dirname, index):
        """ Return nth sample in a directory """
        candidates = []
        for filename in sorted(os.listdir(dirname)):
            name, ext = splitext(filename)
            if ext.lower()[1:] in self._ext:
                fullpath = join(dirname, filename)
                if len(candidates) == index:
                    return fullpath
                candidates.append(fullpath)
        if candidates:
            return candidates[index % len(candidates)]
        return None

    def _patternSearch(self, filename, index):
        """
        Return nth sample that matches a path pattern

        Path pattern is a relative path that can contain wildcards such as *
        and ? (see fnmatch for more details). Some example paths:

            samp*
            **/voices/*
            perc*/bass*

        """

        def _findNextSubpaths(path, pattern):
            """ For a path pattern, find all subpaths that match """
            # ** is a special case meaning "all recursive directories"
            if pattern == '**':
                for dirpath, _, _ in os.walk(path):
                    yield dirpath
            else:
                children = os.listdir(path)
                for c in fnmatch.filter(children, pattern):
                    yield join(path, c)

        candidates = []
        queue = self._paths[:]
        subpaths = filename.split(os.sep)
        filepat = subpaths.pop()
        while subpaths:
            subpath = subpaths.pop(0)
            queue = list(chain.from_iterable(
                (_findNextSubpaths(p, subpath) for p in queue)
            ))

        # If the filepat (ex. 'foo*.wav') has an extension, we want to match
        # the full filename. If not, we just match against the basename.
        match_base = not hasext(filepat)

        for path in queue:
            for subpath, _, filenames in os.walk(path):
                for filename in sorted(filenames):
                    basename, ext = splitext(filename)
                    if ext[1:].lower() not in self._ext:
                        continue
                    if match_base:
                        ismatch = fnmatch.fnmatch(basename, filepat)
                    else:
                        ismatch = fnmatch.fnmatch(filename, filepat)
                    if ismatch:
                        fullpath = join(subpath, filename)
                        if len(candidates) == index:
                            return fullpath
                        candidates.append(fullpath)
        if candidates:
            return candidates[index % len(candidates)]
        return None

    @Timing('bufferSearch', logargs=True)
    def _findSample(self, filename, index=0):
        """
        Find a sample from a filename or pattern

        Will first attempt to find an exact match (by abspath or relative to
        the search paths). Then will attempt to pattern match in search paths.

        """
        path = self._searchPaths(filename)
        if path:
            # If it's a file, use that sample
            if isfile(path):
                return path
            # If it's a dir, use one of the samples in that dir
            elif isdir(path):
                foundfile = self._getFileInDir(path, index)
                if foundfile:
                    return foundfile
                else:
                    WarningMsg("No sound files in %r" % path)
                    return None
            else:
                WarningMsg("File %r is neither a file nor a directory" % path)
                return None
        else:
            # If we couldn't find a dir or file with this name, then we use it
            # as a pattern and recursively walk our paths
            foundfile = self._patternSearch(filename, index)
            if foundfile:
                return foundfile
            WarningMsg("Could not find any sample matching %r" % filename)
            return None

    def loadBuffer(self, filename, index=0):
        """ Load a sample and return the number of a buffer """
        samplepath = self._findSample(filename, index)
        if samplepath is None:
            return 0
        else:
            return self._allocateAndLoad(samplepath)


def hasext(filename):
    return bool(splitext(filename)[1])


Samples = BufferManager()


class LoopSynthDef(SampleSynthDef):
    def __init__(self):
        SampleSynthDef.__init__(self, "loop")
        self.sample = self.new_attr_instance("sample")
        self.stretch = self.new_attr_instance("stretch")
        self.defaults['sample']   = 0

    def __call__(self, filename, pos=0, sample=0, **kwargs):
        kwargs["buf"] = Samples.loadBuffer(filename, sample)
        return SampleSynthDef.__call__(self, pos, **kwargs)

loop = LoopSynthDef()
