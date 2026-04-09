#!/usr/bin/env python3
"""
ELO Swiss tournament manager for mobile game screening.

Workflow:
  python elo.py init <game1> <game2> ... <gameN>   # initialize tournament
  python elo.py pair                                # get next round pairings
  python elo.py match <a> <b> <A|B> "<reason>"      # record a match
  python elo.py state                               # show current standings
  python elo.py final                               # finalize and print top 3

Files (in screenings/YYYYMMDD/):
  elo-state.json  - machine state (do not edit)
  elo-log.md      - human-readable log (auto-regenerated)

Run from the screening project root (where the screenings/ folder lives).
Dependencies: Python 3 standard library only.
"""

import json
import os
import random
import sys
from datetime import date

INITIAL_ELO = 1500
K_FACTOR = 32
ROUNDS_PLANNED = 6
SCREENINGS_DIR = "screenings"
MARKER_FILE = os.path.join(SCREENINGS_DIR, ".current")
STATE_FILENAME = "elo-state.json"
LOG_FILENAME = "elo-log.md"


def expected(elo_a, elo_b):
    """Expected win probability of A against B."""
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))


def update_elo(elo_a, elo_b, winner, k=K_FACTOR):
    """Return new ELOs after a match. winner is 'A' or 'B'."""
    e_a = expected(elo_a, elo_b)
    s_a = 1 if winner == "A" else 0
    new_a = round(elo_a + k * (s_a - e_a))
    new_b = round(elo_b + k * ((1 - s_a) - (1 - e_a)))
    return new_a, new_b


def get_work_dir():
    if not os.path.exists(MARKER_FILE):
        sys.exit(
            f"Error: No active screening. Run 'python {sys.argv[0]} init ...' first."
        )
    with open(MARKER_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def state_path(work_dir):
    return os.path.join(work_dir, STATE_FILENAME)


def log_path(work_dir):
    return os.path.join(work_dir, LOG_FILENAME)


def load_state():
    work_dir = get_work_dir()
    p = state_path(work_dir)
    if not os.path.exists(p):
        sys.exit(f"Error: {p} not found.")
    with open(p, "r", encoding="utf-8") as f:
        return work_dir, json.load(f)


def save_state(work_dir, state):
    with open(state_path(work_dir), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    regenerate_log(work_dir, state)


def regenerate_log(work_dir, state):
    """Rewrite elo-log.md from scratch based on current state."""
    lines = []
    lines.append(f"> ELO 토너먼트 로그. 스크리닝일: {state['date']}")
    lines.append("")
    lines.append("## 초기 상태")
    lines.append(f"{len(state['candidates'])}명 모두 ELO {state['initial_elo']}.")
    lines.append("")
    lines.append("후보:")
    for c in state["candidates"]:
        lines.append(f"- {c}")
    lines.append("")

    matches_per_round = len(state["candidates"]) // 2

    for round_num in range(1, state["current_round"] + 1):
        lines.append(f"## 라운드 {round_num}")
        lines.append("")

        round_history = [h for h in state["history"] if h["round"] == round_num]

        if round_history:
            lines.append("| 매치 | A | B | 승자 | 사유 | A→ | B→ |")
            lines.append("|---|---|---|---|---|---|---|")
            for h in round_history:
                lines.append(
                    f"| {h['match']} | {h['a']} | {h['b']} | {h['winner']} | "
                    f"{h['reason']} | {h['elo_a_after']} | {h['elo_b_after']} |"
                )
            lines.append("")

        # Pending pairings (current round only, if not all matches done)
        if (
            round_num == state["current_round"]
            and state.get("current_round_pairs")
            and len(round_history) < matches_per_round
        ):
            played = {tuple(sorted([h["a"], h["b"]])) for h in round_history}
            pending = [
                (a, b)
                for a, b in state["current_round_pairs"]
                if tuple(sorted([a, b])) not in played
            ]
            if pending:
                lines.append("미완료 페어링:")
                for i, (a, b) in enumerate(pending, len(round_history) + 1):
                    lines.append(f"- M{i}: {a} vs {b}")
                lines.append("")

        snapshot = state["round_snapshots"].get(str(round_num))
        if snapshot:
            lines.append(f"### 라운드 {round_num} 종료 시 ELO 순위")
            lines.append("")
            sorted_snap = sorted(snapshot.items(), key=lambda x: -x[1])
            for rank, (game, elo) in enumerate(sorted_snap, 1):
                lines.append(f"{rank}. {game} ({elo})")
            lines.append("")

    if state.get("finalized"):
        lines.append("## 최종 결과")
        lines.append("")
        lines.append("| 순위 | 게임명 | 최종 ELO | 선정 |")
        lines.append("|---|---|---|---|")
        sorted_elos = sorted(state["elos"].items(), key=lambda x: -x[1])
        for rank, (game, elo) in enumerate(sorted_elos, 1):
            label = "TOP3" if rank <= 3 else "후보 풀"
            lines.append(f"| {rank} | {game} | {elo} | {label} |")
        lines.append("")

    with open(log_path(work_dir), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def cmd_init(args):
    if len(args) < 2:
        sys.exit("Error: Need at least 2 candidates.")
    if len(args) % 2 != 0:
        sys.exit("Error: Need an even number of candidates.")
    if len(set(args)) != len(args):
        sys.exit("Error: Duplicate candidate names found.")

    today = date.today().strftime("%Y%m%d")
    work_dir = os.path.join(SCREENINGS_DIR, today)
    os.makedirs(work_dir, exist_ok=True)

    if os.path.exists(state_path(work_dir)):
        sys.exit(
            f"Error: {state_path(work_dir)} already exists. "
            f"Delete it manually if you want to reinitialize."
        )

    state = {
        "date": today,
        "candidates": list(args),
        "elos": {c: INITIAL_ELO for c in args},
        "current_round": 0,
        "rounds_planned": ROUNDS_PLANNED,
        "matchups": [],  # list of [a, b] (sorted) — pairs that have already met
        "current_round_pairs": [],
        "history": [],
        "round_snapshots": {},
        "finalized": False,
        "k_factor": K_FACTOR,
        "initial_elo": INITIAL_ELO,
    }
    save_state(work_dir, state)

    os.makedirs(SCREENINGS_DIR, exist_ok=True)
    with open(MARKER_FILE, "w", encoding="utf-8") as f:
        f.write(work_dir)

    print(f"Initialized: {len(args)} candidates, all ELO {INITIAL_ELO}")
    print(f"Work directory: {work_dir}")
    print(f"Run 'python {sys.argv[0]} pair' to start round 1.")


def pair_swiss(elos, matchups):
    """Swiss-system pairing: ELO descending, adjacent pairs, no rematch."""
    sorted_candidates = sorted(elos.keys(), key=lambda c: -elos[c])
    matchup_set = {tuple(sorted(m)) for m in matchups}

    def backtrack(remaining):
        if not remaining:
            return []
        a = remaining[0]
        for i in range(1, len(remaining)):
            b = remaining[i]
            if tuple(sorted([a, b])) not in matchup_set:
                rest = remaining[1:i] + remaining[i + 1 :]
                sub = backtrack(rest)
                if sub is not None:
                    return [[a, b]] + sub
        return None

    result = backtrack(sorted_candidates)
    if result is None:
        sys.exit(
            "Error: Could not find valid no-rematch pairing. "
            "(This should not happen with 6 rounds and 20 candidates.)"
        )
    return result


def cmd_pair(args):
    work_dir, state = load_state()

    if state["finalized"]:
        sys.exit("Error: Tournament already finalized.")

    matches_per_round = len(state["candidates"]) // 2

    if state["current_round"] > 0:
        current_matches = len(
            [h for h in state["history"] if h["round"] == state["current_round"]]
        )
        if current_matches < matches_per_round:
            sys.exit(
                f"Error: Round {state['current_round']} is incomplete "
                f"({current_matches}/{matches_per_round} matches). Finish it first."
            )

    if state["current_round"] >= state["rounds_planned"]:
        sys.exit(
            f"Error: All {state['rounds_planned']} rounds completed. "
            f"Run 'python {sys.argv[0]} final'."
        )

    state["current_round"] += 1
    round_num = state["current_round"]

    if round_num == 1:
        shuffled = state["candidates"][:]
        random.shuffle(shuffled)
        pairs = [
            [shuffled[i], shuffled[i + 1]] for i in range(0, len(shuffled), 2)
        ]
    else:
        pairs = pair_swiss(state["elos"], state["matchups"])

    state["current_round_pairs"] = pairs
    save_state(work_dir, state)

    print(f"Round {round_num} pairings ({len(pairs)} matches):")
    for i, (a, b) in enumerate(pairs, 1):
        print(f"  M{i}: {a} vs {b}")


def cmd_match(args):
    if len(args) < 4:
        sys.exit('Usage: python elo.py match <a> <b> <A|B> "<reason>"')

    a, b, winner = args[0], args[1], args[2].upper()
    reason = " ".join(args[3:])

    if winner not in ("A", "B"):
        sys.exit("Error: winner must be 'A' or 'B'.")

    work_dir, state = load_state()

    if a not in state["elos"] or b not in state["elos"]:
        sys.exit(
            f"Error: Unknown candidate(s). Valid: {list(state['elos'].keys())}"
        )

    # Verify the pair is in the current round's pairings
    pair_match = None
    for pair in state["current_round_pairs"]:
        if pair[0] == a and pair[1] == b:
            pair_match = "AB"
            break
        if pair[0] == b and pair[1] == a:
            pair_match = "BA"
            break
    if pair_match is None:
        sys.exit(
            f"Error: ({a}, {b}) is not a pairing in round {state['current_round']}."
        )

    # Normalize order to match canonical pairing order from current_round_pairs
    if pair_match == "BA":
        a, b = b, a
        winner = "B" if winner == "A" else "A"

    # Prevent duplicate match recording in same round
    for h in state["history"]:
        if h["round"] == state["current_round"] and {h["a"], h["b"]} == {a, b}:
            sys.exit(
                f"Error: Match {a} vs {b} already recorded for round {state['current_round']}."
            )

    elo_a_before = state["elos"][a]
    elo_b_before = state["elos"][b]
    elo_a_after, elo_b_after = update_elo(elo_a_before, elo_b_before, winner)

    state["elos"][a] = elo_a_after
    state["elos"][b] = elo_b_after
    state["matchups"].append(sorted([a, b]))

    matches_per_round = len(state["candidates"]) // 2
    match_num_in_round = (
        len([h for h in state["history"] if h["round"] == state["current_round"]])
        + 1
    )

    state["history"].append(
        {
            "round": state["current_round"],
            "match": match_num_in_round,
            "a": a,
            "b": b,
            "winner": winner,
            "reason": reason,
            "elo_a_before": elo_a_before,
            "elo_b_before": elo_b_before,
            "elo_a_after": elo_a_after,
            "elo_b_after": elo_b_after,
        }
    )

    matches_in_round = len(
        [h for h in state["history"] if h["round"] == state["current_round"]]
    )
    if matches_in_round == matches_per_round:
        state["round_snapshots"][str(state["current_round"])] = dict(state["elos"])

    save_state(work_dir, state)

    print("Match recorded:")
    print(f"  {a}: {elo_a_before} → {elo_a_after}")
    print(f"  {b}: {elo_b_before} → {elo_b_after}")
    if matches_in_round == matches_per_round:
        if state["current_round"] < state["rounds_planned"]:
            print(
                f"Round {state['current_round']} complete. "
                f"Run 'python {sys.argv[0]} pair' to start round {state['current_round'] + 1}."
            )
        else:
            print(
                f"All {state['rounds_planned']} rounds complete. "
                f"Run 'python {sys.argv[0]} final' to get top 3."
            )


def cmd_state(args):
    work_dir, state = load_state()
    matches_per_round = len(state["candidates"]) // 2

    print(f"Round: {state['current_round']}/{state['rounds_planned']}")
    if state["current_round"] > 0:
        current_matches = len(
            [h for h in state["history"] if h["round"] == state["current_round"]]
        )
        print(f"Current round matches: {current_matches}/{matches_per_round}")
    print(f"Total matches played: {len(state['history'])}")
    print(f"Finalized: {state['finalized']}")
    print()
    print("Standings (ELO descending):")
    sorted_elos = sorted(state["elos"].items(), key=lambda x: -x[1])
    for rank, (game, elo) in enumerate(sorted_elos, 1):
        print(f"  {rank:2d}. {game:30s} {elo}")


def cmd_final(args):
    work_dir, state = load_state()
    if state["current_round"] < state["rounds_planned"]:
        sys.exit(
            f"Error: Only {state['current_round']}/{state['rounds_planned']} rounds done."
        )
    matches_per_round = len(state["candidates"]) // 2
    matches_in_round = len(
        [h for h in state["history"] if h["round"] == state["current_round"]]
    )
    if matches_in_round < matches_per_round:
        sys.exit(
            f"Error: Final round incomplete ({matches_in_round}/{matches_per_round} matches)."
        )

    state["finalized"] = True
    save_state(work_dir, state)

    sorted_elos = sorted(state["elos"].items(), key=lambda x: -x[1])
    print("Final ranking:")
    for rank, (game, elo) in enumerate(sorted_elos, 1):
        label = "TOP3" if rank <= 3 else "후보 풀"
        print(f"  {rank:2d}. {game:30s} {elo}  [{label}]")
    print()
    print("Top 3:")
    for rank, (game, elo) in enumerate(sorted_elos[:3], 1):
        print(f"  {rank}. {game} ({elo})")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "init": cmd_init,
        "pair": cmd_pair,
        "match": cmd_match,
        "state": cmd_state,
        "final": cmd_final,
    }

    if cmd not in commands:
        print(f"Unknown command: {cmd}")
        print()
        print(__doc__.strip())
        sys.exit(1)

    commands[cmd](args)


if __name__ == "__main__":
    main()
