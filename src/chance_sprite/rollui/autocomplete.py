# autocomplete.py$
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Sequence

from chance_sprite.sprite_utils import normalize_key, levenshtein_distance, split_argstr

log = logging.getLogger(__name__)

ValueKind = Literal["flag", "int"]


@dataclass(frozen=True)
class ArgSpec:
    canonical_key: str
    kind: ValueKind
    aliases: tuple[str, ...] = ()
    suggested_values: tuple[int, ...] = ()


def parse_token_into_key_value(token_text: str) -> tuple[str, str | None]:
    key_text, equals_sign, value_text = token_text.partition("=")
    key_text = key_text.strip()
    if not equals_sign:
        return key_text, None
    return key_text, value_text.strip()  # may be "" if user typed "k="


def build_spec_index(arg_specs: Sequence[ArgSpec]) -> dict[str, ArgSpec]:
    index: dict[str, ArgSpec] = {}
    for arg_spec in arg_specs:
        index[normalize_key(arg_spec.canonical_key)] = arg_spec
        for alias in arg_spec.aliases:
            index[normalize_key(alias)] = arg_spec
    return index


def best_levenshtein_match(
        normalized_input_key: str,
        spec_index: dict[str, ArgSpec],
) -> tuple[ArgSpec, int, int] | None:
    # returns (best_spec, best_distance, second_best_distance)
    scored_candidates: dict[ArgSpec, int] = {}

    for candidate_text, spec in spec_index.items():
        distance = levenshtein_distance(normalized_input_key, candidate_text)
        scored_candidates[spec] = min(distance, scored_candidates.get(spec) or 99)

    if not scored_candidates:
        return None

    # Find best and second best without sorting the whole list
    best_spec: ArgSpec | None = None
    best_distance = 99
    second_best_distance = 99

    for spec, distance in scored_candidates.items():
        if distance < best_distance:
            second_best_distance = best_distance
            best_distance = distance
            best_spec = spec
        elif distance < second_best_distance:
            second_best_distance = distance

    # best_spec is not None here because dict is non-empty
    return best_spec, best_distance, second_best_distance


def find_best_matching_spec(
        raw_key_text: str,
        extra_specs: Sequence[ArgSpec],
        spec_index: dict[str, ArgSpec],
        *,
        max_levenshtein: int = 2,
) -> ArgSpec | None:
    normalized_input_key = normalize_key(raw_key_text)
    if not normalized_input_key:
        return None

    # 1) exact / alias match
    exact_match = spec_index.get(normalized_input_key)
    if exact_match is not None:
        return exact_match

    # 2) unambiguous prefix match
    prefix_matches: list[ArgSpec] = []
    for extra_spec in extra_specs:
        canonical_normalized = normalize_key(extra_spec.canonical_key)
        if canonical_normalized.startswith(normalized_input_key):
            prefix_matches.append(extra_spec)
            continue
        for alias in extra_spec.aliases:
            if normalize_key(alias).startswith(normalized_input_key):
                prefix_matches.append(extra_spec)
                break

    unique_prefix_matches = {match.canonical_key: match for match in prefix_matches}
    if len(unique_prefix_matches) == 1:
        return next(iter(unique_prefix_matches.values()))

    # 3) Levenshtein distance (for typos)
    if len(normalized_input_key) <= max_levenshtein:
        return None
    (best_spec, best_distance, second_best_distance) = best_levenshtein_match(normalized_input_key, spec_index)

    # require: close match and a margin so it is not ambiguous
    if best_distance <= max_levenshtein and (second_best_distance - best_distance) >= 2:
        return best_spec

    return None


def format_suggestion(arg_spec: ArgSpec, value_text: str | None) -> str:
    if arg_spec.kind == "flag":
        return f"{arg_spec.canonical_key},"

    # int
    if value_text is None or value_text == "":
        return f"{arg_spec.canonical_key}=?,"
    return f"{arg_spec.canonical_key}={value_text},"


def build_args_autocomplete_suggestions(
        current_text: str,
        arg_specs: Sequence[ArgSpec],
        *,
        maximum_suggestions: int = 25
) -> list[str]:
    spec_index = build_spec_index(arg_specs)
    token_texts = split_argstr(current_text)
    active_token_text = token_texts[-1] if token_texts else None

    # Parse and normalize all tokens into a canonical mapping; last occurrence wins.
    parsed_values_by_key: dict[str, str | None] = {}
    for token_text in token_texts:
        raw_key_text, raw_value_text = parse_token_into_key_value(token_text)
        matching_spec = find_best_matching_spec(
            raw_key_text,
            arg_specs,
            spec_index
        )
        if matching_spec is None:
            continue
        parsed_values_by_key[matching_spec.canonical_key] = raw_value_text if matching_spec.kind == "int" else None

    def render_current_normalized_tokens() -> list[str]:
        rendered_tokens: list[str] = []
        for extra_spec in arg_specs:
            if extra_spec.canonical_key not in parsed_values_by_key:
                continue
            rendered_tokens.append(format_suggestion(extra_spec, parsed_values_by_key[extra_spec.canonical_key]))
        return rendered_tokens

    def join_tokens(rendered_tokens: list[str]) -> str:
        return " ".join(rendered_tokens).strip()

    normalized_rendered_tokens = render_current_normalized_tokens()
    suggestion_texts: list[str] = []

    # Always include the normalized "fix everything so far" option.
    suggestion_texts.append(join_tokens(normalized_rendered_tokens))

    # Active-token numeric expansions, only if:
    # - active token exists
    # - it matches an int spec
    # - and the value is missing (no '=' OR 'key=' with empty value OR 'key,' with no value)
    if active_token_text:
        active_raw_key_text, active_raw_value_text = parse_token_into_key_value(active_token_text)
        active_spec = find_best_matching_spec(
            active_raw_key_text,
            arg_specs,
            spec_index
        )

        if active_spec and active_spec.kind == "int":
            is_value_missing = (active_raw_value_text is None) or (active_raw_value_text == "")
            if is_value_missing:
                for suggested_value in active_spec.suggested_values:
                    candidate_values = dict(parsed_values_by_key)
                    candidate_values[active_spec.canonical_key] = str(suggested_value)

                    candidate_rendered_tokens: list[str] = []
                    for extra_spec in arg_specs:
                        if extra_spec.canonical_key not in candidate_values:
                            continue
                        candidate_rendered_tokens.append(
                            format_suggestion(extra_spec, candidate_values[extra_spec.canonical_key]))

                    suggestion_texts.append(join_tokens(candidate_rendered_tokens))

                # Also provide "fill placeholder" for that key (e.g., gremlins=?)
                candidate_values = dict(parsed_values_by_key)
                candidate_values[active_spec.canonical_key] = None

                candidate_rendered_tokens = []
                for extra_spec in arg_specs:
                    if extra_spec.canonical_key not in candidate_values:
                        continue
                    candidate_rendered_tokens.append(
                        format_suggestion(extra_spec, candidate_values[extra_spec.canonical_key]))

                suggestion_texts.append(join_tokens(candidate_rendered_tokens))

    # Add “complete remaining with placeholders” suggestions.
    missing_placeholder_tokens: list[str] = []
    for extra_spec in arg_specs:
        if extra_spec.canonical_key in parsed_values_by_key:
            continue
        missing_placeholder_tokens.append(format_suggestion(extra_spec, None))

    for token in missing_placeholder_tokens:
        suggestion_texts.append(join_tokens(normalized_rendered_tokens + [token]))

    if missing_placeholder_tokens:
        suggestion_texts.append(join_tokens(normalized_rendered_tokens + missing_placeholder_tokens))

    # De-dupe and cap
    unique_suggestions: list[str] = []
    seen = set()
    for suggestion_text in suggestion_texts:
        suggestion_text = suggestion_text.strip()
        if suggestion_text in seen:
            continue
        seen.add(suggestion_text)
        unique_suggestions.append(suggestion_text)
        if len(unique_suggestions) >= maximum_suggestions:
            break

    return unique_suggestions
