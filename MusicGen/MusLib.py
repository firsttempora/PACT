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


class PitchGenerator:
    """
    A basic generator of pitches. Parameters:
        repetitiveness: base chance how likely it is that the next pitch will repeat the
            previous one. This value must be >= 0. Works with repeat_decay to set how likely
            it is that a repeat will be forced (see repeat_decay).
        repeat_decay: a "life time" of repeated notes. Must be > 0. Together with repetitiveness,
            this sets the chance that the next note must repeat by the formula
            (1 - exp(-r))*exp(-n/rd), where r is repetitiveness, rd is repeat_decay, and n is
            the number of notes that have repeated immediately before this one. A repeat note
            is guaranteed if a random integer between 0 and 1 is less than this value of
            (1 - exp(-r))*exp(-n/rd).
        leapiness: defines what size intervals the generator prefers. Negative values lead
            to preference for smaller intervals, positive values lead to preference for
            larger ones. Used after repetitiveness, that is, the generator checks if it
            should repeat first, and only if not does it consider how large an interval
            it should choose.
    """
    @property
    def pitches(self):
        return self._notes_so_far

    @pitches.setter
    def pitches(self):
        raise RuntimeError('PitchGenerator.notes may not be set directly')

    def __init__(self, pitches, repetitiveness, repeat_decay, leapiness):
        if isinstance(pitches, abc.ABCMeta):
            raise ValueError('pitches must be an instance of a class derived from PitchSet: did you call e.g. '
                             'MusLib.MajorScale instead of MusLib.MajorScale() (without the parentheses?)')
        if not isinstance(pitches, PitchSet):
            raise TypeError('pitches must be an instance of PitchSet')
        if not isinstance(repetitiveness, (int, float)):
            raise TypeError('repetitiveness must be a numeric type (int or float)')
        if not isinstance(leapiness, (int, float)):
            raise TypeError('leapiness must be a numeric type (int or float)')

        self.pitch_set = pitches
        self.repeat_wt = float(repetitiveness)
        self.repeat_decay = float(repeat_decay)
        self.leap_wt = float(leapiness)
        self._notes_so_far = []

    def add_pitch(self, note):
        if not isinstance(note, Pitch):
            raise TypeError('note must be an instance of Pitch')

        self._notes_so_far.append(note)

    def gen_next_pitch(self):
        # First see if we are going to repeat the previous note
        if len(self.pitches) > 0:
            n_rep = self.count_repeated_pitches()
            chance = (1 - math.exp(self.repeat_wt))*math.exp(-n_rep/self.repeat_decay)
            if random.random() < chance:
                self.add_pitch(self.pitches[-1])
                return

        self.add_pitch(self.pitch_set[random.randint(0, len(self.pitch_set) - 1)])

    def count_repeated_pitches(self):
        n = 0
        for pitch in self.pitches[-2::-1]:
            if pitch == self.pitches[-1]:
                n += 1
            else:
                break

        return n

    def iter_pitch_names(self):
        for p in self.pitches:
            yield p.as_name()


class RhythmGenerator(object):
    """
    Starting beat of a measure is considered beat 0
    """
    @property
    def rhythms(self):
        return self._rhythms_so_far

    @rhythms.setter
    def rhythms(self):
        raise RuntimeError('RhythmGenerator.rhythms may not be set directly')

    @property
    def start_time(self):
        return self._start_time

    def __init__(self, durations, repetitiveness, repeat_decay, start_time=0):
        """
        Similarly to PitchGenerator, this will generate a phrase's durations
        :param durations: a list or tuple of allowed durations
        :param repetitiveness: base chance how likely it is that the next rhythm will repeat the
            previous one. This value must be >= 0. Works with repeat_decay to set how likely
            it is that a repeat will be forced (see repeat_decay).
        :param repeat_decay: a "life time" of repeated durations. Must be > 0. Together with
            repetitiveness, this sets the chance that the next rhythm must repeat by the formula
            (1 - exp(-r))*exp(-n/rd), where r is repetitiveness, rd is repeat_decay, and n is
            the number of durations that have repeated immediately before this one. A repeat rhythm
            is guaranteed if a random integer between 0 and 1 is less than this value of
            (1 - exp(-r))*exp(-n/rd).
        :return:
        """

        #TODO: add ability to restrict note length by remaining duration of phrase
        #TODO: add weighting for syncopation (to prefer or not notes that will avoid crossing a beat)

        if not isinstance(durations, (tuple, list)):
            raise TypeError('durations must be a list or tuple')
        else:
            if not all([isinstance(x, Duration) for x in durations]):
                raise TypeError('durations must contain only instances of MusLib.Duration')

        if not isinstance(repetitiveness, (int, float)):
            raise TypeError('repetitiveness must be an int or float')
        if not isinstance(repeat_decay, (int, float)):
            raise TypeError('repeat_decay must be an int or float')
        if not isinstance(start_time, (int, StartTime)):
            raise TypeError('start_time must be an int or instance of StartTime')

        self.duration_set = durations
        self.repeat_wt = float(repetitiveness)
        self.repeat_decay = float(repeat_decay)
        self._rhythms_so_far = []
        if isinstance(start_time, StartTime):
            self._start_time = start_time
        else:
            self._start_time = StartTime(start_time)

    def add_duration(self, dur):
        if not isinstance(dur, (Duration, Rhythm)):
            raise TypeError('dur must be an instance of MusLib.Duration or MusLib.Rhythm')
        if isinstance(dur, Rhythm):
            dur = Rhythm._duration_instance

        new_rhythm = Rhythm(self.get_next_start_time(), dur)
        self._rhythms_so_far.append(new_rhythm)

    def gen_next_rhythm(self, max_length=max_allowed_duration):
        """

        :param max_length: maxmimum length in DUs (useful to avoid having a rhythm exceed a phrase length)
        :return:
        """
        # First, as in PitchGenerator we see if we should repeat the previous rhythm,
        # but we need to check if doing so would exceed the max requested length
        if len(self._rhythms_so_far) > 0 and self._rhythms_so_far[-1].duration <= max_length:
            n_rep = self.count_repeated_rhythms()
            chance = (1 - math.exp(self.repeat_wt))*math.exp(-n_rep/self.repeat_decay)
            if random.random() < chance:
                self.add_duration(self._rhythms_so_far[-1])
                return

        # Construct a list of durations that are less than or equal to the requested max length
        this_dur_set = [dur for dur in self.duration_set if dur.duration <= max_length]

        i = random.randint(0, len(this_dur_set) - 1)
        self.add_duration(this_dur_set[i])

    def count_repeated_rhythms(self):
        n = 0
        for rhythm in self._rhythms_so_far[-2::-1]:
            if rhythm.duration == self._rhythms_so_far[-1].duration:
                n += 1
            else:
                break

        return n

    def get_next_start_time(self):
        if len(self._rhythms_so_far) == 0:
            return self._start_time
        else:
            new_stime = self._rhythms_so_far[-1].start + self._rhythms_so_far[-1].duration
            return StartTime(new_stime)


    @staticmethod
    def calculate_syncopation(length, beat, meter, linear=False):

        # Something is syncopated if it starts on a fraction of
        # time smaller than its length; i.e. a quarter note is
        # syncopated starting on an upbeat, an eighth note on
        # a 2nd or 4th sixteenth, a half note on beat 2 or 4...
        #
        # We will consider it more syncopated the further from its
        # length the starting point is - so a quarter starting on the
        # 2nd sixteenth is more syncopated than one starting on a 2nd
        # eighth.
        #
        # Finally, we will consider both the start and end point of the note
        # and calculate the syncopation in the same way. This should allow
        # dotted notes to be less syncopated than their full length cousins.
        # We will give more weight to the start than the end point; e q. is
        # more syncopated than q. e

        # This is written without regard for what note has the beat. The "beat" is
        # always taken as notes of length 1.

        #QUESTION: how should meter interact? should notes that cross a bar line
        #be given a higher syncopation? if so, should all notes, or just long ones
        #(>=1.0 length)?

        start_wt = 2.0  # weighting of the starting point relative to the end

        start = beat.as_integer_ratio()
        end = (beat + length).as_integer_ratio()
        duration = length.as_integer_ratio()

        if is_simple(length):
            start_score = max(0, float(start[1])/float(duration[1]) - 1.0)
            end_score = max(0, float(end[1])/float(duration[1]) - 1.0)
        else:
            raise NotImplementedError('Multi-beat durations')

        # Shorter syncopations generally feel more syncopated
        score = (start_score * start_wt + end_score) * 1/length
        if linear and score > 0.0:
            score = math.log2(score)

        return score


def is_simple(length):
    return math.log2(length) % 1 < precision


def is_dotted(length):
    return math.log2(length * 2.0/3.0) % 1 < precision


class MajorScale(PitchSet):
    _pitch_classes = (0, 2, 4, 5, 7, 9, 11)


class MinorScale(PitchSet):
    _pitch_classes = (0, 2, 3, 5, 7, 8, 10)


class Ionian(PitchSet):
    _pitch_classes = (0, 2, 4, 5, 7, 9, 11)

class Aeolian(PitchSet):
    _pitch_classes = (0, 2, 3, 5, 7, 8, 10)
