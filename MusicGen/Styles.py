#!/usr/bin/env python3
import abc
import math
import random

from .MusLib import PitchSet, DurationSet, choose_from_list
from .Generators import PhraseGenerator, PitchGenerator, RhythmGenerator

# TODO: add ability to recall motifs later
# TODO: add ability to define register for a layer - will probably need to implement a class Layer
# TODO: make Minimalist class (at least) able to generate a small motif that gets repeated to form a phrase
# TODO: add variable repetitiveness, etc
# TODO: make copies of the pitch and rhythm generators so they can be independent


class BaseStyle(abc.ABC):
    def __init__(self, pitch_sets, dur_sets, min_layers=1, max_layers=5):
        if isinstance(pitch_sets, list):
            if not all([isinstance(x, PitchSet) for x in pitch_sets]):
                raise TypeError('pitch_sets must be an instance of MusLib.PitchSet or a list of PitchSet instances')
        elif not isinstance(pitch_sets, PitchSet):
            raise TypeError('pitch_sets must be an instance of MusLib.PitchSet or a list of PitchSet instances')

        if not isinstance(pitch_sets, list):
            pitch_sets = [pitch_sets]

        self.pitch_sets = pitch_sets

        if isinstance(dur_sets, list):
            if not all([isinstance(x, DurationSet) for x in dur_sets]):
                raise TypeError('pitch_sets must be an instance of MusLib.PitchSet or a list of PitchSet instances')
        elif not isinstance(dur_sets, DurationSet):
            raise TypeError('pitch_sets must be an instance of MusLib.PitchSet or a list of PitchSet instances')

        if not isinstance(dur_sets, list):
            dur_sets = [dur_sets]
        self.dur_sets = dur_sets

        self.min_layers = min_layers
        self.max_layers = max_layers

    def _gen_layers(self, density=1.0, same_pitch_set=True, phrase_len=3072):
        self.current_layers = []
        common_pitch_gen = PitchGenerator(choose_from_list(self.pitch_sets),1.0,1.0,1.0)
        common_dur_gen = RhythmGenerator(choose_from_list(self.dur_sets),1.0,1.0)
        for i in range(self.max_layers):
            # Once we have our minimum number of layers, allow the possibility that
            # some layers will not be activated. The chance decreases as more layers are
            # added, the rate at which it declines is controlled by density: higher density =
            # less chance a layer won't activate
            if i > self.min_layers-1:
                chance = math.exp(-(len(self.current_layers) + 1 - self.min_layers)/density)
                print('i = {}, chance = {}'.format(i, chance))
                if random.random() > chance:
                    continue

            if same_pitch_set:
                pgen = common_pitch_gen
            else:
                pgen = choose_from_list(self.pitch_sets)

            self.current_layers.append(PhraseGenerator(phrase_len, pgen, common_dur_gen))



class Minimalist(BaseStyle):
    pass
