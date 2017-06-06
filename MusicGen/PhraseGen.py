#!/usr/bin/env python3

from .MusLib import PitchGenerator, RhythmGenerator, Duration

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