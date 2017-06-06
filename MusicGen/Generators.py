#!/usr/bin/env python3
import abc
import math
import random
from .MusLib import Pitch, PitchSet, Duration, DurationSet,\
    StartTime, Rhythm, max_allowed_duration, is_simple

class PhraseGenerator:
    @property
    def phrase_pitches(self):
        return self._pitch_gen._notes_so_far

    @property
    def phrase_rhythms(self):
        return self._rhythm_gen._rhythms_so_far

    def __init__(self, length, pitch_gen, rhythm_gen):
        if not isinstance(length, (int, Duration)):
            raise TypeError('length must be an int or an instance of Duration')
        if not isinstance(pitch_gen, PitchGenerator):
            raise TypeError('pitch_gen must be an instance of PitchGenerator')
        if not isinstance(rhythm_gen, RhythmGenerator):
            raise TypeError('rhythm_gen must be an instance of RhythmGenerator')

        self._length = length
        self._pitch_gen = pitch_gen
        self._rhythm_gen = rhythm_gen

    def gen_phrase(self):
        while self._rhythm_gen.get_next_start_time().start_du < self._length:
            max_len = self._length - self._rhythm_gen.get_next_start_time().start_du
            self._pitch_gen.gen_next_pitch()
            self._rhythm_gen.gen_next_rhythm(max_length=max_len)
            # TODO: combine into notes


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

    def __init__(self, duration_set, repetitiveness, repeat_decay, start_time=0):
        """
        Similarly to PitchGenerator, this will generate a phrase's durations
        :param duration_set: a list or tuple of allowed durations
        :param repetitiveness: base chance how likely it is that the next rhythm will repeat the
            previous one. This value must be >= 0. Works with repeat_decay to set how likely
            it is that a repeat will be forced (see repeat_decay).
        :param repeat_decay: a "life time" of repeated durations. Must be > 0. Together with
            repetitiveness, this sets the chance that the next rhythm must repeat by the formula
            (1 - exp(-r))*exp(-n/rd), where r is repetitiveness, rd is repeat_decay, and n is
            the number of duration_set that have repeated immediately before this one. A repeat rhythm
            is guaranteed if a random integer between 0 and 1 is less than this value of
            (1 - exp(-r))*exp(-n/rd).
        :return:
        """

        #TODO: add ability to restrict note length by remaining duration of phrase
        #TODO: add weighting for syncopation (to prefer or not notes that will avoid crossing a beat)

        if not isinstance(duration_set, DurationSet):
            raise TypeError('duration_set must be a list or tuple')

        if not isinstance(repetitiveness, (int, float)):
            raise TypeError('repetitiveness must be an int or float')
        if not isinstance(repeat_decay, (int, float)):
            raise TypeError('repeat_decay must be an int or float')
        if not isinstance(start_time, (int, StartTime)):
            raise TypeError('start_time must be an int or instance of StartTime')

        self.duration_set = duration_set
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