"""
    Time-Dependent Variables (TimeVar)

"""

from __future__ import absolute_import, division, print_function

from .Patterns import *
from .Repeat import *
from .Utils  import *
from .Patterns.Operations import *

def fetch(func):
    """ Function to wrap basic lambda operators for TimeVars  """
    def eval_now(a, b):
        try:
            a = a.now()
        except:
            pass
        try:
            b = b.now()
        except:
            pass
        return func(a, b)
    return eval_now


class TimeVar:
    """ Var(values [,durs=[4]]) """

    metro = None
    depth = 128

    def __init__(self, values, dur=None, **kwargs):

        Repeatable.__init__(self)

        if dur is None:

            dur = self.metro.bar_length()

        self.name   = "un-named"

        self.values   = values
        self.dur    = dur
        self.bpm    = kwargs.get('bpm', None)

        # This is possibly a bad idea
        # self.data = self

        # Dynamic method for calculating values
        self.func     = Nil
        self.evaluate = fetch(Nil)
        self.dependency = None

        self.update(values, dur)

        self.current_value = None
        self.current_index = None
        self.next_value    = None

        self.proportion    = 0

        self.current_time_block  = None

        # If the clock is not ticking, start it

        if self.metro.ticking == False:

            self.metro.start()

    @classmethod
    def set_clock(cls, tempo_clock):
        cls.metro = tempo_clock
        return

    @staticmethod
    def stream(values):
        return asStream(values)

    @staticmethod
    def CreatePvarGenerator(func, *args):
        return PvarGenerator(func, *args)

    # Standard dunder methods
    def __str__(self):
        return str(self.now())
    def __repr__(self):
        return str(self.now())
    def __len__(self):
        return len(self.now())
    def __int__(self):
        return int(self.now())
    def __float__(self):
        return float(self.now())
    def __abs__(self):
        return abs(self.now())

    # For printing the details
    def info(self):
        return "<{}({}, {})>".format(self.__class__.__name__, repr(self.get_values()), repr(self.get_durs()))

    def all_values(self):
        """ Displays the values and the dependency value - useful for debugging """
        return self.value + [self.dependency]

    def _bpm_cycle_dur(self):
        """ Returns the time, in seconds, for a var to loop to its original
            value and duration if this var is a bpm value. """
        return sum([(self.dur[i] / self.values[i]) for i in range(LCM(len(self.dur), len(self.values)) )]) * 60

    def _bpm_to_beats(self, duration, start=0):
        """ If self.values are series of bpm, how many beats occur in
            the time frame 'duration'. Used in TempoClock """

        cycle_dur = self._bpm_cycle_dur()

        start = start % self.length() # What offset to the start to apply

        n = duration // cycle_dur # How many cycles occurred in duration

        r = duration % cycle_dur  # How many seconds of the last cycle occurred

        total = n * self.length()

        i = 0

        while r > 0:

            # Work out their durations and sub from 'r' until 0

            seconds = (self.dur[i]/ self.values[i]) * 60.0

            offset  = (start / self.values[i]) * 60.0

            seconds = seconds - offset

            if seconds > 0:

                beats = (self.values[i] * min(seconds, r)) / 60.0
                r    -= seconds
                start = 0
                total += beats

            else:

                start -= self.dur[i]

            i += 1
        return total

    # Update methods

    def new(self, other):
        """ Returns a new TimeVar object """
        new = TimeVar(other, self.dur, bpm=self.bpm)
        new.dependency = self
        return new

    def length(self):
        """ Returns the duration of one full cycle in beats """
        return self.time[-1][1]

    def update(self, values, dur=None, **kwargs):
        """ Updates the TimeVar with new values. If `dur` is a `GeneratorPattern`
            type, then it is converted to a normal `Pattern` of length `TimeVar.depth`,
            which is 128 by default but can be changed.
        """

        self.bpm = kwargs.get('bpm', self.bpm)

        # if isinstance(values, str): values = [values]

        self.values = []
        self.time = []

        #: Update the durations of each state

        if dur is not None:

            if isinstance(dur, GeneratorPattern):

                self.dur = dur[:self.depth]

            else:

                self.dur = asStream(dur)

        self.values = self.stream(values)

        a, b = 0, 0

        for dur in self.dur:
            a = b
            b = a + dur
            self.time.append([a,b])

        return self

    # Evaluation methods

    def calculate(self, val): # maybe rename to resolve
        """ Returns val as modified by its dependencies """
        return self.evaluate(val, self.dependency)

    def current_time(self, beat=None):
        """ Returns the current beat value """
        if beat is None:
            beat = self.metro.now()
        if self.bpm is not None:
            beat *= (self.bpm / float(self.metro.bpm))
        return float(beat)

    def get_current_index(self, time=None):
        """ Returns the index of the value currently represented """

        # Get the time value if not from the Clock

        time = self.current_time(time)

        # Work out how many cycles have already passed

        total_dur = float(sum(self.dur))

        loops = time // total_dur

        # And therefore how much time we are into one cycle

        time  = time - (loops * total_dur)

        # And how many events have passed

        total_events = int(loops * len(self.dur))

        count = 0

        for i, value in enumerate(self.dur):

            acc = count + value

            if acc > time:

                i = i + total_events

                break

            else:

                count = acc
        else:

            i = i + total_events

        # Store the % way through this value's time

        self.proportion = (float(time % total_dur) - count) / (acc - count)

        return i

    def now(self, time=None):
        """ Returns the value currently represented by this TimeVar """
        i = self.get_current_index(time)
        self.current_value = self.calculate(self.values[i])
        return self.current_value

    def copy(self):
        new = var(self.values, self.dur, bpm=self.bpm)
        return new

    def get_durs(self):
        return self.dur

    def get_values(self):
        return self.values

    # 1. Methods that change the 'var' in place
    def i_invert(self):
        lrg = float(max(self.values))
        for i, item in enumerate(self.values):
            self.values[i] = (((item / lrg) * -1) + 1) * lrg
        return


    # Method that return an augmented NEW version of the 'var'

    def invert(self):
        new = self.new(self.values)
        lrg = float(max(new.data))
        for i, item in enumerate(new.data):
            new.data[i] = (((item / lrg) * -1) + 1) * lrg
        return new

    def lshift(self, duration):
        time = [self.dur[0]-duration] + list(self.dur[1:]) + [duration]
        return self.__class__(self.values, time)

    def rshift(self, duration):
        time = [duration] + list(self.dur[:-1]) + [self.dur[-1]-duration]
        data = [self.values[-1]] + list(self.values)
        return self.__class__(data, time)

    def extend(self, values, dur=None):
        data = list(self.values) + list(values)
        durs = self.dur if not dur else list(self.dur) + list(asStream(dur))
        return self.__class__(data, durs)

    def shuf(self):
        pass

    # Mathmetical operators

    def math_op(self, other, op):
        """ Performs the mathematical operation between self and other. "op" should
            be the  string name of a dunder method  e.g. __mul__ """
        if not isinstance(other, (TimeVar, int, float)):
            if type(other) is tuple:
                return PGroup([getattr(self, op).__call__(x) for x in other])
            elif type(other) is list:
                return Pattern([getattr(self, op).__call__(x) for x in other])
            else:
                return getattr(other, get_inverse_op(op)).__call__(self)
        return other

    def __add__(self, other):
        new = self.math_op(other, "__add__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(Add)
        return new

    def __radd__(self, other):
        new = self.math_op(other, "__radd__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(rAdd)
        return new

    def __sub__(self, other):
        new = self.math_op(other, "__sub__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(rSub)
        return new

    def __rsub__(self, other):
        new = self.math_op(other, "__rsub__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(Sub)
        return new

    def __mul__(self, other):
        new = self.math_op(other, "__mul__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(Mul)
        return new

    def __rmul__(self, other):
        new = self.math_op(other, "__rmul__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(Mul)
        return new

    def __pow__(self, other):
        new = self.math_op(other, "__pow__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(rPow)
        return new

    def __rpow__(self, other):
        new = self.math_op(other, "__rpow__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(Pow)
        return new

    def __floordiv__(self, other):
        new = self.math_op(other, "__floordiv__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(rFloorDiv)
        return new

    def __rfloordiv__(self, other):
        new = self.math_op(other, "__rfloordiv__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(FloorDiv)
        return new

    def __truediv__(self, other):
        new = self.math_op(other, "__truediv__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(rDiv)
        return new

    def __rtruediv__(self, other):
        new = self.math_op(other, "__rtruediv__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(Div)
        return new

    # Incremental operators (use in place of var = var + n)
    def __iadd__(self, other):
        self.values = self.values + other
        return self
    def __isub__(self, other):
        self.values = self.values - other
        return self
    def __imul__(self, other):
        self.values = self.values * other
        return self
    def __idiv__(self, other):
        self.values = self.values / other
        return self

    # Comparisons -- todo: return TimeVars

    def __gt__(self, other):
        return float(self.now()) > float(other)

    def __lt__(self, other):
        return float(self.now()) < float(other)

    def __ge__(self, other):
        return float(self.now()) >= float(other)

    def __le__(self, other):
        return float(self.now()) >= float(other)

    # %
    def __mod__(self, other):
        new = self.math_op(other, "__mod__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(rMod)
        return new

    def __rmod__(self, other):
        new = self.math_op(other, "__rmod__")
        if not isinstance(other, (TimeVar, int, float)):
            return new
        new = self.new(other)
        new.evaluate = fetch(Mod)
        return new

    #  Comparisons -- todo: return TimeVar

    def __eq__(self, other):
        return other == self.now()

    def __ne__(self, other):
        return other != self.now()

    # Storing functions etc

    def __call__(self, *args, **kwargs):
        """ A TimeVar can store functions and will call the current item with this method """
        return self.now().__call__(*args, **kwargs)

    # Emulating container types

    def __getitem__(self, other):
        new = self.new(other)
        new.dependency = self
        new.evaluate = fetch(rGet)
        return new

    def __iter__(self):
        for item in self.now():
            yield item


class linvar(TimeVar):
    def now(self, time=None):
        """ Returns the value currently represented by this TimeVar """
        i = self.get_current_index(time)
        self.current_value = self.calculate(self.values[i])
        self.next_value    = self.calculate(self.values[i + 1])
        return self.get_timevar_value()

    def get_timevar_value(self):
        return (self.current_value * (1-self.proportion)) + (self.next_value * self.proportion)

class expvar(linvar):
    def get_timevar_value(self):
        self.proportion *= self.proportion
        return (self.current_value * (1-self.proportion)) + (self.next_value * self.proportion)

# TODO sinvar

class Pvar(TimeVar, Pattern):
    """ A TimeVar that represents Patterns that change over time e.g.
        ```
        >>> a = Pvar([ [0,1,2,3], [4,5] ], 4)
        >>> print a # time is 0
        P[0, 1, 2, 3]
        >>> print a # time is 4
        P[4, 5]
    """
    stream = PatternContainer
    def __init__(self, values, dur=None, **kwargs):

        try:

            data = [asStream(val) for val in values]

        except:

            data = [values]

        TimeVar.__init__(self, data, dur, **kwargs)

    def __getattribute__(self, attr):
        # If it's a method, only return the method if its new, transform, or a dunder
        if attr in Pattern.get_methods():

            if attr not in ("new", "now", "transform") and not attr.startswith("__"):

                # return a function that transforms the patterns of the  root Pvar

                def get_new_pvar(*args, **kwargs):

                    # If this is the root Pvar, change the values

                    if self.dependency is  None:

                        new_values = [getattr(pat, attr)(*args, **kwargs) for pat in self.values]

                        return Pvar(new_values, dur=self.dur)

                    else:

                    # Get the "parent" Pvar and re-apply the connecting function

                        new_pvar = getattr(self.dependency, attr)(*args, **kwargs)

                        new_item = self.func(new_pvar, self.original_value)

                        return new_item

                return get_new_pvar

        return object.__getattribute__(self, attr)

    def new(self, other):
        new = Pvar([other], dur=self.dur)
        new.original_value = other
        new.dependency = self
        return new

    def set_eval(self, func):
        self.evaluate = fetch(func)
        self.func     = func
        return

    def __add__(self, other):
        new = self.new(other)
        new.set_eval(Add)
        return new

    def __radd__(self, other):
        new = self.new((other))
        new.set_eval(rAdd)
        return new

    def __sub__(self, other):
        new = self.new((other))
        new.set_eval(Sub)
        return new

    def __rsub__(self, other):
        new = self.new((other))
        new.set_eval(rSub)
        return new

    def __mul__(self, other):
        new = self.new((other))
        new.set_eval(Mul)
        return new

    def __rmul__(self, other):
        new = self.new((other))
        new.set_eval(Mul)
        return new

    def __div__(self, other):
        new = self.new((other))
        new.set_eval(Div)
        return new

    def __rdiv__(self, other):
        new = self.new((other))
        new.set_eval(rDiv)
        return new

    def __truediv__(self, other):
        new = self.new((other))
        new.set_eval(Div)
        return new

    def __rtruediv__(self, other):
        new = self.new((other))
        new.set_eval(rDiv)
        return new

    def __floordiv__(self, other):
        new = self.new((other))
        new.set_eval(FloorDiv)
        return new

    def __rfloordiv__(self, other):
        new = self.new((other))
        new.set_eval(rFloorDiv)
        return new

    def __pow__(self, other):
        new = self.new((other))
        new.set_eval(Pow)
        return new

    def __rpow__(self, other):
        new = self.new((other))
        new.set_eval(rPow)
        return new

    def __mod__(self, other):
        new = self.new((other))
        new.set_eval(Mod)
        return new

    def __rmod__(self, other):
        new = self.new((other))
        new.set_eval(rMod)
        return new

    def __or__(self, other):
        # Used when piping patterns together
        new = self.new(PatternContainer(other))
        new.set_eval(rOr)
        return new

    def __ror__(self, other):
        # Used when piping patterns together
        new = self.new(PatternContainer(other))
        new.set_eval(Or)
        return new

    def transform(self, func):
        """ Returns a Pvar based on a transformation function, as opposed to
            a mathematical operation"""
        new = self.new(self)
        new.set_eval(func)
        return new


class PvarGenerator(Pvar):
    """ If a TimeVar is used in a Pattern function e.g. `PDur(var([3,5]), 8)`
        then a `PvarGenerator` is returned. Each argument is stored as a TimeVar
        and the function is called whenever the arguments are changed
    """
    def __init__(self, func, *args):
        self.p_func = func # p_func is the Pattern function e.g. PDur but self.func is created when operating on this PvarGenerator
        self.args = [(arg if isinstance(arg, TimeVar) else TimeVar(arg)) for arg in args]
        self.last_args = []
        self.last_data = []
        self.evaluate = fetch(Nil)
        self.dependency = None

    def info(self):
        return "<{} {}>".format(self.__class__.__name__, self.func.__name__ + str(tuple(self.args)))

    def now(self):
        new_args = [arg.now() for arg in self.args]
        if new_args != self.last_args:
            self.last_args = new_args
            self.last_data = self.p_func(*self.last_args)
        pat = self.calculate(self.last_data)
        return pat

    def new(self, other):
        # new = Pvar([other]) # TODO -- test this
        new = self.__class__(lambda x: x, other)
        new.original_value = other
        new.dependency = self
        return new

    def set_eval(self, func):
        self.evaluate = fetch(func)
        self.func     = func
        return

    def __getattribute__(self, attr):
        # If it's a method, only return the method if its new, transform, or a dunder
        if attr in Pattern.get_methods():

            if attr not in ("new", "now", "transform") and not attr.startswith("__"):

                # return a function that transforms the patterns of the  root Pvar

                def get_new_pvar_gen(*args, **kwargs):

                    # If this is the root Pvar, change the values

                    if self.dependency is None:

                        # Create a new function that combines the original *plus* the method

                        def new_func(*old_args, **old_kwargs):

                            return getattr(self.p_func(*old_args, **old_kwargs), attr)(*args, **kwargs)

                        return PvarGenerator(new_func, *self.args)

                    else:

                        # Get the "parent" Pvar and re-apply the connecting function

                        new_pvar_gen = getattr(self.dependency, attr)(*args, **kwargs)

                        return self.func(new_pvar_gen, self.original_value)

                return get_new_pvar_gen

        return object.__getattribute__(self, attr)

class PvarGeneratorEx(PvarGenerator):
    """ Un-Documented """
    def __init__(self, func, *args):
        self.func = func
        self.args = list(args)
        self.last_args = []
        self.last_data = []
        self.evaluate = fetch(Nil)
        self.dependency = 1


class _inf(int):
    """ Un-implemented """
    zero = 0
    here = 1
    wait = 2
    done = 3
    def __new__(cls):
        return int.__new__(cls, 0)
    def __add__(self, other):
        return self
    def __radd__(self,other):
        return self
    def __sub__(self, other):
        return self
    def __rsub__(self, other):
        return self
    def __mul__(self, other):
        return self
    def __rmul__(self, other):
        return self
    def __div__(self, other):
        return self
    def __rdiv__(self, other):
        return 0

inf = _inf()

# Store and updates TimeVars

class _var_dict(object):
    """
        This is the TimeVar generator used in FoxDot. Calling it like `var()`
        returns a TimeVar but setting an attribute `var.foo = var([1,2],4)` will
        update the TimeVar that is already in `var.foo`.

        In short, using `var.name = var([i, j])` means you don't have to delete
        some of the text and replace it with `var.name.update([k, l])` you can
        just use `var.name = var([k, l])` and the contents of the var will be
        updated everywhere else in the program.
    """

    def __init__(self):
        self.__vars = {}
    @staticmethod
    def __call__(*args, **kwargs):
        return TimeVar(*args, **kwargs)
    def __setattr__(self, name, value):
        if name != "__vars" and isinstance(value, TimeVar):
            if name in self.__vars:
                if value.__class__ != self.__vars[name].__class__:
                    self.__vars[name].__class__ = value.__class__
                self.__vars[name].__dict__ = value.__dict__
            else:
                self.__vars[name] = value
            return
        object.__setattr__(self, name, value)
    def __getattr__(self, name):
        if name in self.__vars:
            value = self.__vars[name]
        else:
            value = object.__getattr__(self, name)
        return value

var = _var_dict()

# Give Main.Pattern a reference to TimeVar classes
Pattern.TimeVar       = TimeVar
Pattern.PvarGenerator = PvarGenerator
Pattern.Pvar          = Pvar
