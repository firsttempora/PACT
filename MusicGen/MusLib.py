#!/usr/bin/env python3
import abc
import math
import random
import re

note_zero = 'C0'
precision = 1e-6


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


class Rhythm:
    def __init__(self, start, duration):
        if not isinstance(start, (int, float)):
            raise TypeError('start must be a numeric type (int or float)')
        if not isinstance(duration, (int, float)):
            raise TypeError('duration must be a numeric type (int or float)')
        self.start = float(start)
        self.duration = float(duration)
        # Ultimately, durations should use "duration units" like Finale. If we want to allow
        # 128th triplets as the smallest note, then 128th = 6 DU, that way triplets are 4 DU
        # and dotted 128th can be 9. This means a quarter note would be 768 DU


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
    def notes(self):
        return self._notes_so_far

    @notes.setter
    def notes(self):
        raise RuntimeError('PitchGenerator.notes may not be set directly')

    def __init__(self, pitches, repetitiveness, repeat_decay, leapiness):
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

    def add_note(self, note):
        if not isinstance(note, Note):
            raise TypeError('note must be an instance of Note')

        self._notes_so_far.append(note)

    def gen_next_note(self):
        # First see if we are going to repeat the previous note
        if len(self.notes) > 0:
            n_rep = self.count_repeated_notes()
            chance = (1 - math.exp(self.repeat_wt))*math.exp(-n_rep/self.repeat_decay)
            if random.random() < chance:
                self.add_note(self.notes[-1])
                return



    def count_repeated_notes(self):
        n = 0
        for note in self.notes[-2::-1]:
            if note == self.notes[-1]:
                n += 1
            else:
                break

        return n



class RhythmGenerator(object):
    """
    Starting beat of a measure is considered beat 0
    """
    def __init__(self):
        pass

    @staticmethod
    def gen_phrase_rhythm(length, meter):
        pass

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
