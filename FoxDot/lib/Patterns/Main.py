"""

Contains classes `Pattern` and `PGroup` and the base class for `GeneratorPattern` (see Generators.py).

"""

from __future__ import absolute_import, division, print_function

from random import choice, shuffle
from copy import deepcopy

from .Operations import *
from ..Utils import *

import functools
import inspect

# Decorator functions for nested expansion of pattern functions and methods

def loop_pattern_func(f):
    ''' Decorator for allowing any Pattern function to create
        multiple Patterns by using Patterns or TimeVars as arguments '''
    @functools.wraps(f)
    def new_function(*args):

        # Return any functions that use TimeVars as PvarGenerators
        timevars = [arg for arg in args if isinstance(arg, Pattern.TimeVar)]
        if len(timevars) > 0:
            return Pattern.TimeVar.CreatePvarGenerator(f, *args)

        # Loop the pattern with different values
        pat = Pattern()
        # Force pattern types if using lists/tuples
        args = [PatternFormat(arg) for arg in args]
        # Continually extend the pattern
        for i in range(LCM(*[len(arg) for arg in args if (hasattr(arg, '__len__') and not isinstance(arg, PGroup))])):
            pat |= f(*[(arg[i] if isinstance(arg, Pattern) else arg) for arg in args])
        return pat
    new_function.argspec = inspect.getargspec(f)
    return new_function

# TODO -- if it isn't looped, return the original if it is a group

def loop_pattern_method(f):
    ''' Decorator for allowing any Pattern method to create
        multiple (or rather, longer) Patterns by using Patterns as arguments '''
    @functools.wraps(f)
    def new_function(self, *args):
        pat = Pattern()
        # Force pattern types if using lists/tuples
        args = [PatternFormat(arg) for arg in args]
        for i in range(LCM(*[len(arg) for arg in args if (hasattr(arg, '__len__') and not isinstance(arg, PGroup))])):
            pat |= f(self, *[(modi(arg, i) if not isinstance(arg, PGroup) else arg) for arg in args])
        return pat
    new_function.argspec = inspect.getargspec(f)
    return new_function

def PatternMethod(f):
    ''' Decorator that makes a function into a metaPattern method'''
    setattr(metaPattern, f.__name__, f)
    return

def StaticPatternMethod(f):
    ''' Decorator that makes a function into a metaPattern static  method'''
    setattr(metaPattern, f.__name__, staticmethod(f))
    return

def ClassPatternMethod(f):
    ''' Decorator that makes a function into a metaPattern class method'''
    setattr(metaPattern, f.__name__, classmethod(f))
    return

# Begin Pattern Abstratct Base Class

class metaPattern(object):
    """ Abstract base class for Patterns """

    data = None
    bracket_style = "[]"
    debugging = False

    def __init__(self, data=[]):

        # Keep track of the names of any Pattern sub-classes that
        # might be created during runtime

        if self.__class__.__name__ not in PATTERN_WEIGHTS:

            PATTERN_WEIGHTS.insert(-1, self.__class__.__name__)

        if type(data) is str:

            self.fromString(data)

        elif type(data) is tuple:

            self.data = PGroup(data)
            self.make()

        elif isinstance(data, self.__class__):

            self.data = data.data

        else:

            self.data = data
            self.make()

    @classmethod
    def get_methods(cls):
        return [attr for attr in dir(cls) if callable(getattr(cls, attr))]

    def __len__(self):
        """ Returns the *expanded" length of the pattern. e.g. the following
            are identical.
            ```
            >>> print( len(P[0,1,2,[3,4]]) )
            8
            >>> print( len(P[0,1,2,3,0,1,2,4]) )
            8
            ```
        """
        lengths = [1] + [len(p) for p in self.data if isinstance(p, Pattern)]
        return LCM(*lengths) * len([item for item in self.data if not isinstance(item, EmptyItem)])

    def __str__(self):
        try:
            if len(self.data) > 20:
                val = self.data[:8] + [dots()] + self.data[-8:]
            else:
                val = self.data
        except AttributeError:
            val = self.data
        return "P" + self.bracket_style[:-1] + ( repr(val)[1:-1] ) + self.bracket_style[-1]

    def __repr__(self):
        return str(self)

    # Conversion methods

    def string(self):
        """ Returns a PlayString in string format from the Patterns values """
        string = ""
        for item in self.data:
            if isinstance(item, (PGroup, GeneratorPattern)):
                string += item.string()
            elif isinstance(item, Pattern):
                string += "(" + "".join([(s.string() if hasattr(s, "string") else str(s)) for s in item.data]) + ")"
            else:
                string += str(item)
        return string

    def asGroup(self):
        """ Returns the Pattern as a PGroup """
        return PGroup(self.data)

    def group(self):
        """ Returns the Pattern as a PGroup """
        return PGroup(self.data)

    # TODO -- this is super hacky vv

    def convert_data(self, dtype=float, *args, **kwargs):
        """ Makes a true copy and converts the data to a given data type """
        return self.true_copy([(item.convert_data(dtype, *args, **kwargs) if isinstance(item, metaPattern) else dtype(item, *args, **kwargs)) for item in self.data])

    def copy(self):
        """ Returns a copy of the Pattern such that alterations to the
            Pattern.data do not affect the original.
        """
        return self.__class__(self.data[:])

    def true_copy(self, new_data=None):
        """ Returns a copy of the Pattern such that items within the
            Pattern hold the same state as the original.
        """
        new = self.__class__()
        new.__dict__ = {key: value for key, value in self.__dict__.items()}
        if new_data is not None:
            new.data = new_data
        return new

    # Pattern container methods

    def __getitem__(self, key):
        """ Calls self.getitem. Is overridden in `FoxDot.lib.TimeVar`
            for indexing with TimeVars """
        return self.getitem(key)

    def getitem(self, key, get_generator=False):
        """ Is called by __getitem__ """
        # We can get multiple values by indexing with a pattern or tuple
        if isinstance(key, (metaPattern, tuple)):
            val = self.__class__([self.getitem(n) for n in key])
        # We can get items using a slice
        elif isinstance(key, slice):
            val = self.__getslice__(key.start,  key.stop, key.step)
        else:
            # Get the "nested" single value
            i = key % len(self.data)
            val = self.data[i]
            if isinstance(val, Pattern) or ( isinstance(val, GeneratorPattern) and not get_generator ):
                j   = key // len(self.data)
                val = val.getitem(j, get_generator)
            elif isinstance(val, GeneratorPattern) and get_generator:
                return val
        return val

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            self.data[key] = Format(value) # TODO - make sure this works
        else:
            i = key % len(self.data)
            if isinstance(self.data[i], metaPattern):
                j = key // len(self.data)
                self.data[i][j] = value
            else:
                if key >= len(self.data):
                    self.data[i] = Pattern([self.data[i], Format(value)]).stutter([key // len(self.data) , 1])
                else:
                    self.data[i] = Format(value)
        return

    def setitem(self, key, value):
        self.data[key] = Format(value)

    def __iter__(self):
        """ Returns a generator object for this Pattern """
        for i in range(len(self)):
            yield self.getitem(i)

    def items(self):
        """ Returns a generator object equivalent to using enumerate() """
        for i, value in enumerate(self):
            yield i, value

    def __getslice__(self, start, stop, step=1):
        start = start if start is not None else 0
        stop  = stop if stop is not None else len(self)
        step  = step if step is not None else 1

        if stop < start:

            stop = (len(self.data) + start)

        return Pattern([self[i] for i in range(start, stop, step) ])

    def __setslice__(self, i, j, item):
        """ Only works in Python 2 """
        self.data[i:j] = Format(item)

    # Integer returning

    def count(self, item):
        """ Returns the number of occurrences of item in the Pattern"""
        return self.data.count(item)

    """

        Pattern operators (i.e. magic methods)
        --------------------------------------

    """
    def __add__(self, other):  return PAdd(self, other)
    def __radd__(self, other): return PAdd(self, other)
    def __sub__(self, other):  return PSub(self, other)
    def __rsub__(self, other): return PSub2(self, other)
    def __mul__(self, other):  return PMul(self, other)
    def __rmul__(self, other): return PMul(self, other)
    def __truediv__(self, other):   return PDiv(self, other)
    def __rtruediv__(self, other):  return PDiv2(self, other)
    def __floordiv__(self, other):  return PFloor(self, other)
    def __rfloordiv__(self, other): return PFloor2(self, other)
    def __mod__(self, other):  return PMod(self, other)
    def __rmod__(self, other): return PMod2(self, other)
    def __pow__(self, other):  return PPow(self, other)
    def __rpow__(self, other): return PPow2(self, other)
    def __xor__(self, other):  return PPow(self, other)
    def __rxor__(self, other): return PPow2(self, other)
    def __truediv__(self, other):  return PDiv(self, other)
    def __rtruediv__(self, other): return PDiv2(self, other)

    def __abs__(self):
        return self.__class__([abs(item) for item in self])

    def __bool__(self):
        return all([bool(item > 0) for item in self])

    def __nonzero__(self):
        return self.__bool__()

    def abs(self):
        return abs(self)

    def __invert__(self):
        """ Using the ~ symbol as a prefix to a Pattern will reverse it.
            >>> a = P[:4]
            >>> print(a, ~a)
            P[0, 1, 2, 3], P[3, 2, 1, 0]
        """
        return self.mirror()

    # Piping patterns together using the '|' operator

    def __or__(self, other):
        """ Use the '|' symbol to 'pipe' Patterns into on another """
        return self.pipe(other)
    def __ror__(self, other):
        """ Use the '|' symbol to 'pipe' Patterns into on another """
        return asStream(other).pipe(self)

    # Zipping patterns together using the '&' operator

    def __and__(self, other):
        return self.zip(other)

    def __rand__(self, other):
        return asStream(other).zip(self)

    #  Comparisons --> this might be a tricky one
    def __eq__(self, other):
        return PEq(self, other)
    def __ne__(self, other):
        return PNe(self, other)
    def eq(self, other):
        return self.__class__([int(value == modi(asStream(other), i)) for i, value in enumerate(self)])
    def ne(self, other):
        return self.__class__([int(value != modi(asStream(other), i)) for i, value in enumerate(self)])
    # def gt(self, other):
    #     return self.__class__([int(value > modi(asStream(other), i)) for i, value in enumerate(self)])
    # def lt(self, other):
    #     return self.__class__([int(value < modi(asStream(other), i)) for i, value in enumerate(self)])
    # def ge(self, other):
    #     return self.__class__([int(value >= modi(asStream(other), i)) for i, value in enumerate(self)])
    # def le(self, other):
    #     return self.__class__([int(value <= modi(asStream(other), i)) for i, value in enumerate(self)])
    def __gt__(self, other):
        #return self.__class__([int(value > modi(asStream(other), i)) for i, value in enumerate(self)])
        values = []
        other = asStream(other)
        for i, value in enumerate(self): # possibly LCM in future
            value = value > other[i]
            if not isinstance(value, PGroup):
                value = int(value)
            values.append(value)
        return self.__class__(values)

    def __ge__(self, other):
        #return self.__class__([int(value >= modi(asStream(other), i)) for i, value in enumerate(self)])
        values = []
        other = asStream(other)
        for i, value in enumerate(self): # possibly LCM in future
            value = value >= other[i]
            if not isinstance(value, PGroup):
                value = int(value)
            values.append(value)
        return self.__class__(values)

    def __lt__(self, other):
        #return self.__class__([int(value < modi(asStream(other), i)) for i, value in enumerate(self)])
        values = []
        other = asStream(other)
        for i, value in enumerate(self): # possibly LCM in future
            value = value < other[i]
            if not isinstance(value, PGroup):
                value = int(value)
            values.append(value)
        return self.__class__(values)

    def __le__(self, other):
        #return self.__class__([int(value <= modi(asStream(other), i)) for i, value in enumerate(self)])
        values = []
        other = asStream(other)
        for i, value in enumerate(self): # possibly LCM in future
            value = value <= other[i]
            if not isinstance(value, PGroup):
                value = int(value)
            values.append(value)
        return self.__class__(values)

    # Methods that return augmented versions of original

    def shuffle(self, n=1):
        """ Returns a new Pattern with shuffled contents. Note: nested patterns
            stay together. To shuffle the contents of nested patterns, use
            `deep_shuffle` or `true_shuffle`.
        """
        items = []

        for i in range(n):
            data = self.data[:]
            shuffle(data)
            items.extend(data)
        return self.__class__(items)

    def deep_shuffle(self, n=1):
        """ Returns a new Pattern with shuffled contents and shuffles
            any nested patterns. To shuffle the contents of nested patterns
            with the rest of the Pattern's contents, use `true_shuffle`.
        """
        items = []
        for i in range(n):
            data = [(item if not isinstance(item, metaPattern) else item) for item in self.data[:]]
            shuffle(data)
            items.extend(data)
        return self.__class__(items)

    def true_shuffle(self, n=1):
        """ Returns a new Pattern with completely shuffle contents such
            that nested Patterns are shuffled within the larger Pattern
        """
        items = []
        for i in range(n):
            data = list(self)
            shuffle(data)
            items.extend(data)
        return self.__class__(items)

    def reverse(self):
        """ Reverses the contents of the Pattern. Nested patterns are
            not reversed. To reverse the contents of nester patterns
            use `Pattern.mirror()`
        """
        new = self.__class__(self.data[:])
        new.data.reverse()
        return new

    def sort(self):
        """ Used in place of sorted(pattern) to force type """
        return self.__class__(sorted(self.data))

    def mirror(self):
        """ Reverses the pattern. Differs to `Pattern.reverse()` in that
            all nested patters are also reversed. """
        new = []
        for i in range(len(self.data), 0, -1):

            value = self.data[i-1]

            if hasattr(value, 'mirror'):

                value = value.mirror()

            new.append(value)

        return self.__class__(new)

    def stutter(self, n=2):
        """ Returns a new Pattern with each item repeated by `n`. Use
            a list of numbers for stutter different items by different
            amount. e.g.
            ```
            >>> P[0, 1, 2, 3].stutter([1,3])
            P[0, 1, 1, 1, 2, 3, 3, 3]
            ```
        """
        n = asStream(n)
        lrg = max(len(self.data), len(n))
        new = []
        for i in range(lrg):
            for j in range(modi(n,i)):
                new.append(modi(self.data,i))
        return self.__class__(new)

    def arp(self, arp_pattern):
        """ Return a new Pattern with each item repeated len(arp_pattern) times
            and incremented by arp_pattern. Useful for arpeggiating. e.g.
            ```
            >>> P[0, 1, 2, 3].arp([0, 2])
            P[0, 2, 1, 3, 2, 4, 3, 5]
            ```
        """
        return self.stutter(len(arp_pattern)) + arp_pattern

    def splice(self, seq, *seqs):
        """ Takes at least list / Pattern and creates a new Pattern by
            adding a value from each pattern in turn to the new pattern.
            e.g.
            ```
            >>> P[0,1,2,3].splice([4,5,6,7],[8,9])
            P[0,4,8,1,5,9,2,6,8,3,7,9]
            ```
        """
        sequences = (self, seq) + seqs
        size = LCM(*[len(s) for s in sequences])
        new = []
        for i in range(size):
            for seq in sequences:
                new.append(modi(seq, i))
        return self.__class__(new)

    def invert(self):
        """ Inverts the values with the Pattern.
        """
        new = []
        lrg = float(max(self.data))
        for item in self.data:
            try:
                new.append(item.invert())
            except:
                new.append((((item / lrg) * -1) + 1) * lrg)
        return self.__class__(new)

    def shufflets(self, n):
        """ Returns a Pattern of 'n' number of PGroups made from shuffled
            versions of the original Pattern """
        new = self.data[:]
        return Pattern([Pattern(new).shuffle().asGroup() for i in range(n)])

    # Loop methods

    @loop_pattern_method
    def pivot(self, i):
        """ Mirrors and rotates the Pattern such that the item at index 'i'
            is in the same place """
        if len(self) > 0:
            mid = len(self) / 2
            if i > mid:
                i = len(self) - i - 1
                new = self.mirror().rotate((2*(i % len(self)))+1)
            else:
                new = self.rotate((2*(i % len(self)))+1).mirror()
        else:
            new = self.copy()
        return new

    @loop_pattern_method
    def accum(self, n=None):
        """ Returns a Pattern that is equivalent to list of sums of that
            Pattern up to that index."""
        if n is None:
            n = len(self)
        new = [0]
        for i in range(n-1):
            new.append( new[-1] + self[i] )
        return self.__class__(new)

    @loop_pattern_method
    def stretch(self, size):
        """ Stretches (repeats) the contents until len(Pattern) == size """
        new = []
        for n in range(size):
            new.append( modi(self.data, n) )
        new = self.__class__(new)
        return new

    @loop_pattern_method
    def loop(self, n):
        """ Repeats this pattern n times """
        new = []
        for i in range(n):
            new += list(self)
        return self.__class__(new)

    @loop_pattern_method
    def swap(self, n=2):
        new = []
        for pair in [list(val) for val in [reversed(self[i:i+n]) for i in range(0, len(self), n)]]:
            for item in pair:
                new.append(item)
        return self.__class__(new)

    @loop_pattern_method
    def rotate(self, n=1):
        n = int(n)
        new = self.data[n:] + self.data[0:n]
        return self.__class__(new)

    @loop_pattern_method
    def sample(self, n):
        """ Returns an n-length pattern from a sample"""
        return self.__class__(random.sample(list(self), n))

    @loop_pattern_method
    def palindrome(self, a=0, b=None):
        """ Returns the original pattern with mirrored version of itself appended.
            a removes values from the middle of the pattern, if positive.
            b removes values from the end of the pattern, should be negative.

            e.g.

            >>> P[:4].palindrome()
            P[0, 1, 2, 3, 3, 2, 1, 0]
            >>> P[:4].palindrome(1)
            P[0, 1, 2, 3, 2, 1, 0]
            >>> P[:4].palindrome(-1)
            P[0, 1, 2, 3, 3, 2, 1]
            >>> P[:4].palindrome(1,-1)
            P[0, 1, 2, 3, 2, 1]

        """
        a = int(a)

        if a < 0:

            a, b = 0, a

        return self | self.mirror()[a:b]

    def normalise(self):
        """ Returns the pattern with all values between 0 and 1 """
        pos = self - min(self)
        return pos / max(pos)

    def unduplicate(self):
        """ Removes any consecutive duplicate numbers from a Pattern """
        new = []
        last_val = None
        for value in self:
            if value != last_val:
                new.append(value)
            last_val = value
        return self.__class__(new)

    def add(self, other):
        return self + other

    @loop_pattern_method
    def limit(self, func, value):
        """ Returns a new Pattern generated by adding elements from
            this Pattern to a new list and repeatedly calling
            `func()` on this list until `func(l)` is greater than `value`
            e.g.
            ```
            >>> print( P[0, 1, 2, 3].limit(sum, 10) )
            P[0, 1, 2, 3, 0, 1, 2]
            ```
        """
        new = []
        i = 0
        while func(new) < value:
            new.append(self[i])
            i+=1
        return self.__class__(new)

    # Methods that take a non number / pattern argument

    def replace(self, sub, repl):
        """ Replaces any occurrences of "sub" with "repl" """
        new = []
        for item in self.data:
            if isinstance(item, metaPattern):
                new.append(item.replace(sub, repl))
            elif item == sub:
                new.append(repl)
            else:
                new.append(item)
        return self.__class__(new)

    def map(self, mapping):
        """ Similar to Pattern.replace, but takes a dictionary of values """
        new = []
        for item in self.data:
            if isinstance(item, metaPattern):
                new.append(item.map(mapping))
            else:
                new.append(mapping.get(item, 0))
        return self.__class__(new)

    def layer(self, method, *args, **kwargs):
        """ Zips a pattern with a modified version of itself. Method argument
            can be a function that takes this pattern as its first argument,
            or the name of a Pattern method as a string. """

        if callable(method):
            func = method
            args = [self.data] + list(args)
        else:
            func = getattr(self, method)
            assert callable(func)

        return self.zip(func(*args, **kwargs))

    def every(self, n, method, *args, **kwargs):
        """ Returns the pattern looped n-1 times then appended with
            the version returned when method is called on it. """
        return self.loop(n-1).pipe(getattr(self, method).__call__(*args, **kwargs))

    def map(self, func):
        return self.__class__([(item.map(func) if isinstance(item, metaPattern) else func(item)) for item in self.data])



    def extend(self, item):
        self[len(self):] = [item]
        return self

    def new_extend(self, item):
        new = self.__class__()
        new.data = list(self.data)
        new.extend(item)
        return new

    def append(self, item):
        self.data.append(item)
        self.make()
        return self

    def new_append(self, item):
        new = self.__class__()
        new.data = list(self.data)
        new.append(item)
        return new

    def i_rotate(self, n=1):
        self.data = self.data[n:] + self.data[0:n]
        return self

    def i_reverse(self):
        self.data.reverse()
        return self

    def i_sort(self):
        self.data = Pattern(sorted(self.data))
        return self

    def i_shuf(self):
        shuffle(self.data)
        return self

    def set(self, index, value):
        self.data[index] = asStream(value)
        return self

    # Boolean tests

    def contains_nest(self):
        """ Returns true if the pattern contains a nest """
        pass

    def startswith(self, prefix):
        return self.data[0] == prefix

    def all(self, func=(lambda x: bool(x))):
        """ Returns true if all of the patterns contents satisfies func(x) - default is nonzero """
        if len(self.data) is 0:
            return False

        for item in self.data:
            if not func(item):
                return False
        return True

    # Extension methods

    def pipe(self, pattern):
        """ Concatonates this patterns stream with another """
        return Pattern(self.data + asStream(pattern).data)

    def zipx(self, other):
        """ Returns a `Pattern` of `PGroups`, where each `PGroup` contains the i-th
            element from each of the argument sequences. The length of the pattern
            is the lowest common multiple of the lengths of the two joining patterns. """
        new = []
        other = asStream(other)
        for i in range(LCM(len(self.data), len(other.data))):
            item1 = self.data[i % len(self.data)]
            item2 = other.data[i % len(other.data)]
            new.append((item1, item2))
        return self.__class__(new)

    def zip(self, other, dtype=None):
        """ Zips two patterns together. If one item is a tuple, it extends the tuple / PGroup
            i.e. arrow_zip([(0,1),3], [2]) -> [(0,1,2),(3,2)]
        """
        output = Pattern()

        dtype = PGroup if dtype is None else dtype

        for i in range(LCM(len(self), len(other))):

            item1 = self.getitem(i, get_generator=True)
            item2 = other.getitem(i, get_generator=True)

            if all([x.__class__== PGroup for x in (item1, item2)]):

                new_item = PGroup(item1.data + item2.data)

            elif item1.__class__ == PGroup:

                new_item = PGroup(item1.data + [item2])

            elif item2.__class__ == PGroup:

                new_item = PGroup([item1] + item2.data)

            else:

                new_item = (item1, item2)

            output.append(new_item)

        return output

    def deepzip(self, other):
        new = []
        other = asStream(other)
        for i in range(LCM(len(self.data), len(other.data))):
            p1 = self.data[i % len(self.data)]
            p2 = other.data[i % len(other.data)]
            if isinstance(p1, metaPattern):
                value = p1.deepzip(p2)
            elif isinstance(p2, metaPattern):
                value = p2.deeprzip(p1)
            else:
                value = (p1, p2)
            new.append(value)
        return self.__class__(new)

    def deeprzip(self, other):
        new = []
        other = asStream(other)
        for i in range(LCM(len(self.data), len(other.data))):
            p1 = self.data[i % len(self.data)]
            p2 = other.data[i % len(other.data)]
            if isinstance(p1, metaPattern):
                value = p1.deeprzip(p2)
            elif isinstance(p2, metaPattern):
                value = p2.deepzip(p1)
            else:
                value = (p2, p1)
            new.append(value)
        return self.__class__(new)

    # Returns individual elements / slices

    def choose(self):
        """ Returns one randomly selected item """
        return choice(self.data)

    def trim(self, size):
        return self[:size]

    def ltrim(self, size):
        return self[-size:]

    def get_behaviour(self):
        return None

    # Automatic expansion of nested patterns

    def make(self):
        """ This method automatically laces and groups the data """

        #: Force data into an iterable form
        if isinstance(self.data, str):

            self.data = list(self.data)

        if not isinstance(self.data, PatternType): # not sure about PlayString data

            self.data = [self.data]

        #: Put any data in a tuple into a PGroup
        for i, data in enumerate(self.data):
            if type(data) is tuple:
                self.data[i] = PGroup(data)
            elif type(data) is list:
                self.data[i] = Pattern(data)
            elif type(data) is str and len(data) > 1:
                self.data[i] = Pattern(data)

        self.data = list(self.data)

        return self

class Pattern(metaPattern):
    """ Base type pattern """
    debug = False

class PGroup(metaPattern):
    """
        Class to represent any groupings of notes as denoted by brackets.
        PGroups should only be found within a Pattern object.

    """

    bracket_style = "()"

    def __init__(self, seq=[], *args):

        if not args:

            if isinstance(seq, metaPattern):

                seq = seq.data

            elif isinstance(seq, tuple):

                seq = list(seq)
        else:

            seq = [seq] + list(args)

        metaPattern.__init__(self, seq)

        # If the PGroup contains patterns, invert it to a Pattern of PGroups

        l = [len(p) for p in self.data if isinstance(p, Pattern)]

        if len(l) > 0:

            new_data = []

            for key in range(LCM(*l)):

                new_data.append(self.__class__([item.getitem(key) if isinstance(item, Pattern) else item for item in self.data]))

            self.__class__ = Pattern

            self.data = new_data

    def extend(self, item):
        self.data.extend(item)
        return self

    def merge(self, value):
        """ Merge values into one PGroup """
        if hasattr(value, "__len__"):
            new_data = list(value)
        else:
            new_data = [value]
        return self.__class__(list(self.data) + new_data)

    def calculate_step(self, dur):
        return dur

    def calculate_delay(self, delay):
        return 0

    def calculate_time(self, dur):
        """ Returns a PGroup of durations to use as the delay argument
            when this is a sub-class of `PGroupPrime` """
        values = []
        step  = self.calculate_step(dur)
        for i, item in enumerate(self):
            delay = self.calculate_delay( i * step )
            if hasattr(item, "calculate_time"):
                delay += item.calculate_time( step )
            values.append( delay )
        return PGroup(values)

    def flatten(self):
        """ Returns a nested PGroup as un-nested e.g.
            ```
                >>> P(0,(3,5)).flatten()
                P(0, 3, 5)
            ```
        """
        values = []
        for item in self:
            if isinstance(item, PGroup):
                values.extend(list(item))
            else:
                values.append(item)
        return PGroup(values)

    def get_behaviour(self):
        """ Returns a function that modulates a player event dictionary """
        def action(event, key):
            event['delay'] += self.calculate_time(float(event['dur']))
            return event
        return action

    def has_behaviour(self):
        """ Returns True if this is a PGroupPrime or any elements are
            instances of PGroupPrime or its sub-classes"""
        for value in self:
            if isinstance(value, PGroup):
                if value.has_behaviour():
                    return True
        else:
            return False

    def get_name(self):
        return self.__class__.__name__

    def ne(self, other):
        """ Not equals operator """
        values = []
        other  = PatternFormat(other)
        if isinstance(other, Pattern):
            return other.ne(self)
        for i, item in enumerate(self): # possibly LCM
            item = item != modi(other,i)
            if not isinstance(item, metaPattern):
                item = int(item)
            values.append(item)
        return self.__class__(values)

    def __ne__(self,  other):
        return self.ne(other)

    def eq(self, other):
        """ equals operator """
        values = []
        other  = PatternFormat(other) # bad function  name
        if isinstance(other, Pattern):
            return other.eq(self)
        for i, item in enumerate(self): # possibly LCM
            item = item == modi(other,i)
            if not isinstance(item, metaPattern):
                item = int(item)
            values.append(item)
        return self.__class__(values)

    def __eq__(self, other):
        return self.eq(other)

    def __gt__(self, other):
        values = []
        other  = PatternFormat(other)
        if isinstance(other, Pattern):
            return other < self
        for i, item in enumerate(self): # possibly LCM
            item = item > modi(other,i)
            if not isinstance(item, metaPattern):
                item = int(item)
            values.append(item)
        return self.__class__(values)

    def __lt__(self, other):
        values = []
        other  = PatternFormat(other)
        if isinstance(other, Pattern):
            return other > self
        for i, item in enumerate(self): # possibly LCM
            item = item < modi(other,i)
            if not isinstance(item, metaPattern):
                item = int(item)
            values.append(item)
        return self.__class__(values)

    def __ge__(self, other):
        values = []
        other  = PatternFormat(other)
        if isinstance(other, Pattern):
            return other <= self
        for i, item in enumerate(self): # possibly LCM
            item = item >= modi(other,i)
            if not isinstance(item, metaPattern):
                item = int(item)
            values.append(item)
        return self.__class__(values)

    def __le__(self, other):
        values = []
        other  = PatternFormat(other)
        if isinstance(other, Pattern):
            return other >= self
        for i, item in enumerate(self): # possibly LCM
            item = item <= modi(other,i)
            if not isinstance(item, metaPattern):
                item = int(item)
            values.append(item)
        return self.__class__(values)


import random

class GeneratorPattern(random.Random):
    """
        Used for when a Pattern does not generate a set length pattern,
        e.g. random patterns
    """
    MAX_SIZE = 65536
    debugging = False

    def __new__(cls, *args, **kwargs):
        """ Override random.Random using first argument as a seed """
        return super(GeneratorPattern, cls).__new__ (cls)

    def __init__(self, **kwargs):

        random.Random.__init__(self)

        # Set the seed if a random pattern

        if kwargs.get("seed", None) is not None:

            self.seed(kwargs["seed"])

        self.args = tuple()
        self.kwargs = kwargs

        self.mod = Pattern()
        self.mod_functions = []
        self.name  = self.__class__.__name__
        self.parent = None
        self.last_value = None
        self.data  = []
        self.index   = 0
        self.cache = {}

    def __repr__(self):
        """ String version is the name of the class and its arguments """
        return "{}({})".format(self.name, self.data)

    def getitem(self, index=None, *args):
        """ Calls self.func(index) to get an item if index is not in
            self.history, otherwise returns self.history[index] """
        if index is None:
            index, self.index = self.index, self.index + 1
        # If we have already accessed by this index, return the value
        if index in self.cache:
            return self.cache[index]
        else:
            # Calculate new value
            value = self.func(index)
            # Store if we refer to the same index
            self.cache[index] = value
            return value

    def new(self, other, func=Nil):
        """ Creates a new `GeneratorPattern` that references
            this pattern but returns a modified value based on
            func. """
        new = GeneratorPattern()
        new.parent = self
        new.name   = new.parent.name
        other      = asStream(other)
        new.data   = "{} {}".format(func.__name__, other)
        new.func   = lambda index: func(new.parent.getitem(index), other[index])
        return new

    def func(self, index):
        return index

    def __int__(self):
        return int(self.getitem())

    def __float__(self):
        return  float(self.getitem())

    # Arithmetic operations create new GeneratorPatterns
    def __add__(self, other):
        return self.new(other, Add)
    def __radd__(self, other):
        return self.new(other, Add)
    def __sub__(self, other):
        return self.new(other, Sub)
    def __rsub__(self, other):
        return self.new(other, rSub)
    def __mul__(self, other):
        return self.new(other, Mul)
    def __rmul__(self, other):
        return self.new(other, Mul)
    def __div__(self, other):
        return self.new(other, Div)
    def __truediv__(self, other):
        return self.new(other, Div)
    def __rdiv__(self, other):
        return self.new(other, rDiv)
    def __rtruediv__(self, other):
        return self.new(other, rDiv)
    def __mod__(self, other):
        return self.new(other,  Mod)
    def __rmod__(self, other):
        return self.new(other, rMod)
    # Container methods
    def __iter__(self):
        for i in range(self.MAX_SIZE):
            yield self[i]

    def __getitem__(self, key):
        if type(key) is int:
            return self.getitem(key)
        elif type(key) is slice:
            a = key.start if key.start else 0
            b = key.stop
            c = key.step if key.step else 1
            return Pattern([self[i] for i in range(a, b, c)])

    def dup(self, n=2):
        """ Returns a PGroup with n lots of the Generator """
        return PGroup([self.__class__(*self.args, **self.kwargs) for i in range(n)])


class PatternContainer(metaPattern):
    def getitem(self, key, *args):
        key = key % len(self)
        return self.data[key]
    def __len__(self):
        return len(self.data)
    def __str__(self):
        return str(self.data)
    def __repr__(self):
        return str(self)

class EmptyItem(object):
    """ Can be used in a pattern and and is essentially not there """
    def __init__(self):
        pass
    def __repr__(self):
        return "_"

"""    Utility functions and data
"""

# Used to force any non-pattern data into a Pattern

PatternType = (Pattern, list)

def asStream(data):
    """ Forces any data into a [pattern] form """
    return data if isinstance(data, Pattern) else Pattern(data)

def PatternFormat(data):
    """ If data is a list, returns Pattern(data). If data is a tuple, returns PGroup(data).
        Returns data if neither. """
    if isinstance(data, list):
        return Pattern(data)
    if isinstance(data, tuple):
        return PGroup(data)
    return data

Format = PatternFormat ## TODO - Remove this

def patternclass(a, b):
    return PGroup if isinstance(a, PGroup) and isinstance(b, PGroup) else Pattern

def Convert(*args):
    """ Returns tuples/PGroups as PGroups, and anything else as Patterns """
    PatternTypes = []
    for val in args:
        if isinstance(val, (Pattern, PGroup)):
            PatternTypes.append(val)
        elif isinstance(val, tuple):
            PatternTypes.append(PGroup(val))
        else:
            PatternTypes.append(Pattern(val))
    return PatternTypes if len(PatternTypes) > 0 else PatternTypes[0]

def asPattern(item):
    if isinstance(item,  metaPattern):
        return item
    if isinstance(item, list):
        return Pattern(item)
    if isinstance(item, tuple):
        return PGroup(item)
    return Pattern(item)

def pattern_depth(pat):
    """ Returns the level of nested arrays """
    total = 1
    for item in pat:
        if isinstance(item, PGroup):
            depth = pattern_depth(item)
            if depth + 1 > total:
                total = depth + 1
    return total

def equal_values(this, that):
    """ Returns True if this == that """
    comp = this == that
    if isinstance(comp, metaPattern):
        return all(list(comp))
    else:
        return comp

def group_modi(pgroup, index):
    """ Returns value from pgroup that modular indexes nested groups """
    std_type = (int, float, str, bool)
    if isinstance(pgroup, Pattern.TimeVar) and isinstance(pgroup.now(), std_type):
            return pgroup
    elif isinstance(pgroup, std_type):
        return pgroup
    try:
        return group_modi(pgroup[index % len(pgroup)], index // len(pgroup))
    except(TypeError, AttributeError, ZeroDivisionError):
        return pgroup
