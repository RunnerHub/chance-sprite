from __future__ import annotations

import random

from msgspec import to_builtins

from chance_sprite.result_types import _default_random, HitsResult, BreakTheLimitHitsResult, SecondChanceHitsResult, \
    PushTheLimitHitsResult, CloseCallResult, AdditiveResult


def roll_hits(dice: int, *, limit: int = 0, gremlins: int = 0, rng: random.Random = _default_random) -> HitsResult:
    rolls = [rng.randint(1, 6) for _ in range(dice)]
    return HitsResult(original_dice=dice, rolls=rolls, limit=limit, gremlins=gremlins)


def roll_exploding(dice: int, *, limit: int = 0, gremlins: int = 0,
                   rng: random.Random = _default_random) -> BreakTheLimitHitsResult:
    rolls = [rng.randint(1, 6) for _ in range(dice)]
    exploded_dice = []
    sixes = sum(1 for r in rolls if r == 6)
    while True:
        rerolls = [rng.randint(1, 6) for _ in range(sixes)]
        exploded_dice.append(rerolls)
        sixes = sum(1 for r in rerolls if r == 6)
        if sixes == 0:
            break
    return BreakTheLimitHitsResult(original_dice=dice, rolls=rolls, limit=limit, gremlins=gremlins,
                                   exploded_dice=exploded_dice)


def second_chance(hits_result: HitsResult, rng: random.Random = _default_random):
    rerolls = [rng.randint(1, 6) for _ in range(hits_result.dice - hits_result.dice_hits)]
    new_hits = sum(1 for r in rerolls if r in (5, 6))
    return SecondChanceHitsResult(**to_builtins(hits_result), rerolled_dice=rerolls, rerolled_hits=new_hits)


def push_the_limit(hits_result, edge: int, rng: random.Random = _default_random):
    explosion_iterations = []
    sixes = edge
    total_hits = 0
    while True:
        rerolls = [rng.randint(1, 6) for _ in range(sixes)]
        explosion_iterations.append(rerolls)
        sixes = sum(1 for r in rerolls if r == 6)
        total_hits += sum(1 for r in rerolls if r in (5, 6))
        if sixes == 0:
            break

    return PushTheLimitHitsResult(**to_builtins(hits_result), exploded_dice=explosion_iterations,
                                  rerolled_hits=total_hits)


def close_call(hits_result: HitsResult):
    return CloseCallResult(**to_builtins(hits_result))


def additive_roll(dice: int, *, rng: random.Random = _default_random) -> AdditiveResult:
    rolls = [rng.randint(1, 6) for _ in range(dice)]
    return AdditiveResult(dice=dice, rolls=rolls)
