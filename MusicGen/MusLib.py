#!/usr/bin/env python3
import abc
import math
import random
import re
import warnings

note_zero = 'C0'
precision = 1e-6
max_allowed_duration = 2**32-1


class Pitch:
    note_re = '^[a-gA-G][#b]?\d{0,2}$'
    note_semitones = {'C':0, 'D':2, 'E':4, 'F':5, 'G':7, 'A':9, 'B':11}

    def __init__(self, pitch_id):
        if isinstance(pitch_id, int):
            self.note = pitch_id
        elif isinstance(pitch_id, str):
            self.note = Pitch.note_name_to_midi(pitch_id)

    def __repr__(self):
        return '{} {} at {:#x}'.format(self.__class__, self.as_name(), id(self))

    def as_name(self, prefer_sharps=True):
        # Need the zero note info
        [z_pc, z_acc, z_oct] = Pitch.parse_note_name(note_zero)

        # Get our info
        octave = math.floor(self.note/12) - z_oct
        pitch_class = self.note % 12

        # Get the note name
        shifted_st = {k: (v-(z_pc+z_acc)) % 12 for k, v in Pitch.note_semitones.items()}

        # First look and see if the note is a natural note. If not, try sharps or flats
        found_it = False
        for note, num in shifted_st.items():
            if num == pitch_class:
                note_name = note
                found_it = True
                break

        if not found_it:
            if prefer_sharps:
                acc_str = '#'
                to_add = 1
            else:
                acc_str = 'b'
                to_add = -1

            for note, num in shifted_st.items():
                if num + to_add == pitch_class:
                    note_name = note + acc_str
                    found_it = True
                    break

        if not found_it:
            raise RuntimeError('Failure representing note number {0} as name (note_zero = {1}'.
                               format(self.note, note_zero))

        return '{0}{1}'.format(note_name, octave)

    @staticmethod
    def parse_note_name(name):
        # TODO: fix to handle negative octaves
        pitch_class = name[0].upper()
        pitch_class = Pitch.note_semitones[pitch_class]

        accidental = re.search('[#b]?', name[1:]).group()
        if accidental == '':
            accidental = 0
        elif accidental == '#':
            accidental = 1
        elif accidental == 'b':
            accidental = -1

        octave = re.search('\d{0,2}$', name[1:]).group() # the '$' seems necessary to get this to match for some reason
        if octave == '':
            octave = 0
        else:
            octave = 12 * int(octave)

        return pitch_class, accidental, octave

    @staticmethod
    def note_name_to_midi(name):
        if not isinstance(name, str):
            raise TypeError('name must be an instance of str')
        elif not re.match(Pitch.note_re, name):
            raise ValueError('name must conform to the regex pattern {0}; '
                             'that is, a note letter optionally followed by an accidental and octave number'
                             .format(Pitch.note_re))

        [pitch_class, accidental, octave] = Pitch.parse_note_name(name)

        if name == note_zero:
            n0_val = 0
        else:
            n0_val = Pitch.note_name_to_midi(note_zero)

        return pitch_class + accidental + octave - n0_val


class Duration:
    """
    Use this class to represent a duration (length in time).
    Durations are represented internally in duration units,
    an arbitrary unit chosen to be able to represent most
    common durations as integers. The DU value of a quarter
    note is given by Duration.qnote_dur; you may alter this
    if you wish, but be warned, instances of Duration created
    before the change will not update their instance durations.
    """
    # To be able to resolve 64th note triplets and dotted 64th notes, a 64th note
    # must be represented by a number of duration units divisible by 2 and 3. Since
    # 6 is the least common multiple of 2 and 3, that means 1 64th note = 6 DU, and
    # therefore 1 quarter note = 16 * 6 = 96.
    qnote_dur = 96
    simple_names = {'octuple whole':8, 'quadruple whole':4, 'double whole':2, 'whole':1,
                    'half':1/2, 'quarter':1/4, 'eighth':1/8, 'sixteenth':1/16, 'thirty second':1/32,
                    'sixty fourth':1/64}
    fancy_names = {'maxima':8, 'longa':4, 'breve':2, 'semibreve':1, 'minim':1/2, 'crotchet':1/4,
                   'quaver':1/8, 'semiquaver':1/16, 'demisemiquaver':1/32, 'hemidemisemiquaver':1/64}

    @property
    def is_dotted(self):
        return self._is_dotted

    @is_dotted.setter
    def is_dotted(self):
        raise RuntimeError('Duration.is_dotted may not be set manually')

    @property
    def is_triplet(self):
        return self._is_triplet

    @is_triplet.setter
    def is_triplet(self):
        raise RuntimeError('Duration.is_triplet may not be set manually')

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self):
        raise RuntimeError('Duration.duration may not be set manually, only through __init__()')

    def __init__(self, duration):
        """
        Create an instance of Duration with a specified duration.
        :param duration: the desired duration. Can be given as an integer, in which case it is
        interpreted as duration units (DU, see class help), or a string. The string interpreter
        is reasonably flexible, and can be either:
            1) a fraction, i.e. '1/4', that represents the modern note representation. I.e., '1/4' is
            a quarter note, '1/16' a sixteenth note, '1' a whole note, '2' a double whole note, etc.
            Dotted or triple notes would have to be given as, e.g. '3/8' would be a dotted quarter,
            and 1/12 would be an eighth note triplet.
            2) as a name, e.g. 'eighth', 'eighth note', 'quaver', etc. This will recognize both the
             regular English names and the older names ('quaver','crotchet', etc.). The name may end
             in 'note' or not (i.e., 'half note' and 'half' are equivalent) and breaks in between words
             may be omitted, or included as spaces, dashes, or underscores (i.e. 'thirty second',
             'thirtysecond', 'thirty_second', and 'thirty-second' are all the same). Finally, the
             keywords 'tuple' or 'triplet' anywhere in the string will make it a triplet of that note,
             and 'dot' or 'dotted' will do the same for dotted notes.
        :return:
        """
        if not isinstance(duration, (int,str)):
            raise TypeError('duration must be an int or str')

        self._is_dotted = False
        self._is_triplet = False
        if isinstance(duration, str):
            duration = self._parse_duration_string(duration)

        if duration > max_allowed_duration:
            raise ValueError('Duration requested exceeds max allowed ({})'.format(max_allowed_duration))

        self._duration = duration

    def __repr__(self):
        return '<{!s} ({!r} DU) at {:#x}>'.format(self.__class__, self.duration, id(self))

    def __eq__(self, other):
        if isinstance(other, Duration):
            return self.duration == other.duration
        else:
            return False

    def _parse_duration_string(self, dur_str):
        dur_str_in = dur_str
        dur_str = dur_str.lower()
        frac = None
        if re.match('^\d+/?\d*$', dur_str):
            try:
                frac = [int(x) for x in dur_str.split('/') if len(x) > 0]
            except ValueError:
                raise ValueError('Could not parse duration string')
            else:
                if len(frac) == 1:
                    frac = frac[0]
                else:
                    frac = frac[0]/frac[1]

        else:
            # First, is it dotted or a triplet?
            m = re.search('dotted|dot', dur_str)
            if m is not None:
                self._is_dotted = True
                dur_str = dur_str.replace(m.group(), '').strip()

            m = re.search('triplet|tuple', dur_str)
            if m is not None:
                self._is_triplet = True
                dur_str = dur_str.replace(m.group(), '').strip()

            # Now, more complicatedly, we have to figure out which note it actually is. We'll
            # use the names defined for the class
            for k, v in Duration.simple_names.items():
                regex = Duration._note_name_regex(k)
                if re.match(regex, dur_str):
                    frac = v
                    break

            for k, v in Duration.fancy_names.items():
                regex = Duration._note_name_regex(k)
                if re.match(regex, dur_str):
                    frac = v
                    break

            # Calculate the duration as by taking the ratio of the requested duration
            # to a quarter note times the quarter note duration
            if self._is_triplet and frac is not None:
                frac *= 2/3
            if self._is_dotted and frac is not None:
                frac *= 1.5

        # Did parsing fail?
        if frac is None:
            raise RuntimeError('Could not parse duration string "{}"'.format(dur_str_in))

        # Check that there's no partial duration units
        dur = frac * 4 * Duration.qnote_dur
        if dur % 1 != 0:
            warnings.warn('Fractional duration unit detected; will be truncated with int()')

        return int(dur)

    @staticmethod
    def _note_name_regex(note_name):
        # The regex for note names allows any space to be a space, dash, underscore, or omitted
        # and for "note" to be at the end or not
        note_name = note_name.replace(' ','[ \-_]?')
        return '^' + note_name + '([ \-_]note)?$'


class DurationSet:
    @property
    def duration_set(self):
        return self._duration_set

    def __init__(self, *durations):
        """
        Currently a very basic container for a set of durations. Can expand later as needed,
        can either create instances of this directly or inherited classes
        :param durations: all durations that you wish to include
        :return: nothing
        """
        duration_set = []
        for dur in durations:
            if isinstance(dur, Duration):
                if dur not in duration_set:
                    duration_set.append(dur)
            else:
                raise TypeError('All arguments passed to DurationSet.__init__() must be instances of Duration')

        self._duration_set = duration_set

    def __iter__(self):
        self._iter_ind = 0
        return self

    def __next__(self):
        if self._iter_ind < len(self.duration_set):
            dur = self.duration_set[self._iter_ind]
            self._iter_ind += 1
            return dur
        else:
            raise StopIteration()

    def add_duration(self, dur):
        if not isinstance(dur, Duration):
            raise TypeError('dur must be an instance of Duration')
        elif dur not in self.duration_set:
            self._duration_set.append(dur)

    @staticmethod
    def duple_set(min_length=Duration('1/64'), max_length=Duration('2'), incl_dotted=True):
        """
        Construct a duration set with all duple durations between the minimum and maximum lengths
        Duple durations are defined as those with durations that are a quarter note time some power
        of 2.
        :param min_length: the shortest duration allowed. If a duple duration, will be included. Default is 64th note.
           Must be an instance of Duration.
        :param max_length: the longest duration allowed. If a duple duration, will be included. Default is double whole
           note. Must be an instance of Duration.
        :param incl_dotted: boolean, if True (default) dotted notes within the duration range will be included.
        :return: an instance of DurationSet
        """
        # Input checking
        if not isinstance(min_length, Duration):
            raise TypeError('min_length must be an instance of MusLib.Duration')
        elif not isinstance(max_length, Duration):
            raise TypeError('max_length must be an instance of MusLib.Duration')
        elif not isinstance(incl_dotted, bool):
            raise TypeError('incl_dotted must be a boolean')

        # Find the smallest duple value
        dur_len = Duration.qnote_dur
        while dur_len >= min_length.duration:
            dur_len //= 2

        # The last division will put us below the minimum value, so bring it back up one
        dur_len *= 2

        dur_list = []
        while dur_len <= max_length.duration:
            dur_list.append(Duration(dur_len))
            if incl_dotted and dur_len*1.5 <= max_length.duration:
                dur_list.append(Duration(int(dur_len*1.5)))
            dur_len *= 2

        return DurationSet(*dur_list)


class PitchSet(abc.ABC):
    @property
    def pitch_classes(self):
        try:
            return [(x + self.tonic)%12 for x in self._pitch_classes]
        except AttributeError as err:
            raise TypeError('{0} '
                            'Did you try to instantiate the abstract class PitchSet directly, '
                            'or forget to set _pitch_classes in an inherited class?'.format(err.args[0]))

    @pitch_classes.setter
    def pitch_classes(self, value):
        raise RuntimeError('"pitches" cannot be set')

    @property
    def range(self):
        return self._range

    @range.setter
    def range(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise TypeError('PitchSet.range value must be a list or tuple of length 2')

        myrange = []
        for v in value:
            if isinstance(v, int):
                myrange.append(v)
            elif isinstance(v, str):
                myrange.append(Pitch.note_name_to_midi(v))
            else:
                raise TypeError('The value for PitchSet.range must be a list or tuple of integers or valid note names as strings')

        if myrange[1] >= myrange[0]:
            self._range = tuple(myrange)
        else:
            self._range = tuple(myrange[::-1])

    @property
    def pitches(self):
        return [Pitch(p) for p in range(self.range[0], self.range[1]+1) if p%12 in self.pitch_classes]

    def __init__(self, tonic=0, range=None):
        if isinstance(tonic, str):
            tonic = Pitch.note_name_to_midi(tonic)
        elif not isinstance(tonic, int):
            raise TypeError('tonic must be an instance of str or int')

        self.tonic = tonic % 12
        if range is None:
            self.range = (0, 11)
        else:
            self.range = range

    def __len__(self):
        l = 0
        for p in range(self.range[0], self.range[1]+1):
            if p%12 in self.pitch_classes:
                l += 1
        return l

    def __getitem__(self, item):
        return self.pitches[item]


class StartTime:
    """
    For now, this will just keep track of the starting time of a rhythm in duration units
    Eventually it can interact with meters to compute bars and beats
    """
    @property
    def start_du(self):
        return self._start_du

    def __init__(self, start_du):
        if not isinstance(start_du, int) or start_du < 0:
            raise TypeError('start_du must be an int >= 0')

        self._start_du = start_du


class Rhythm:
    @property
    def duration(self):
        """
        Returns the length of the rhythm in DUs
        :return: an integer
        """
        return self._duration_instance.duration

    @property
    def start(self):
        """
        Returns the start time of the rhythm in DUs from beginning of piece at 0
        :return: an integer
        """
        return self._start_time_instance.start_du

    def __init__(self, start, duration):
        if not isinstance(start, StartTime):
            raise TypeError('start must be an instance of StartTime')
        if not isinstance(duration, Duration):
            raise TypeError('duration must be an instance of MusLib.Duration')
        self._start_time_instance = start
        self._duration_instance = duration

    def __repr__(self):
        return '<{} start={}, dur={} at {:#x}>'.format(
            self.__class__, self.start, self.duration, id(self)
        )


class Meter:
    def __init__(self, pulse_per_bar, pulse_note):
        if not isinstance(pulse_per_bar, int):
            raise TypeError('pulse_per_bar must be an int')
        if not isinstance(pulse_note, int):
            raise TypeError('pulse_note must be an int')

        self.pulse_per_bar = pulse_per_bar
        self.pulse_note = pulse_note


class Note:
    def __init__(self, pitch, rhythm, articulation=None, dynamic=None):
        self.pitch = pitch
        self.rhythm = rhythm
        self.articulation = articulation
        self.dynamic = dynamic


def is_simple(length):
    return math.log2(length) % 1 < precision


def is_dotted(length):
    return math.log2(length * 2.0/3.0) % 1 < precision


def choose_from_list(the_list, weights=None, return_type='item'):
    if not isinstance(the_list, (list, tuple)):
        raise TypeError('the_list must be a list or tuple')

    if weights is None:
        weights = [1.0 for x in the_list]
    else:
        if not isinstance(weights, (list, tuple)):
            raise TypeError('weights must be an instance of list or tuple')
        elif not all([isinstance(w, float) for w in weights]):
            raise TypeError('all elements of weights must be floats')
        elif len(weights) != len(the_list):
            raise ValueError('weights must have the same length as the_list')

    allowed_return_types = ('item','index')
    if not isinstance(return_type, str):
        raise TypeError('return_type must be a string')
    elif return_type.lower() not in allowed_return_types:
        raise ValueError('return_type must be one of {}'.format(', '.join(allowed_return_types)))

    # See https://stackoverflow.com/questions/56692/random-weighted-choice
    total_weight = sum(weights)
    roll = random.random() * total_weight
    for i in range(len(the_list)):
        if roll < weights[i]:
            ind = i
            break
        else:
            roll -= weights[i]

    if return_type == 'ind':
        return ind
    elif return_type == 'item':
        return the_list[i]
    else:
        raise NotImplementedError('The return_type "{}" has not been implemented'.format(return_type))


class MajorScale(PitchSet):
    _pitch_classes = (0, 2, 4, 5, 7, 9, 11)


class MinorScale(PitchSet):
    _pitch_classes = (0, 2, 3, 5, 7, 8, 10)


class Ionian(PitchSet):
    _pitch_classes = (0, 2, 4, 5, 7, 9, 11)

class Aeolian(PitchSet):
    _pitch_classes = (0, 2, 3, 5, 7, 8, 10)
