import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent import run

# each test: (question, assertion_fn, description)
TESTS = [
    # validation
    (
        "what is the capital of france",
        lambda r: r["error"] is not None,
        "reject irrelevant question"
    ),
    (
        "delete all teams",
        lambda r: r["error"] is not None,
        "reject destructive query"
    ),

    # basic team queries
    (
        "which teams are in group A",
        lambda r: len(r["rows"]) == 4,
        "group A has 4 teams"
    ),
    (
        "who coaches brazil",
        lambda r: len(r["rows"]) == 1 and r["rows"][0] is not None,
        "brazil coach returns 1 row"
    ),
    (
        "which teams advanced from the group stage",
        lambda r: len(r["rows"]) == 32,
        "32 teams advanced from group stage"
    ),

    # match queries
    (
        "what matches did brazil play in the group stage",
        lambda r: len(r["rows"]) == 3,
        "brazil played 3 group stage matches"
    ),
    (
        "what was the score of brazil vs japan",
        lambda r: any(
            (row.get("home_score") == 2 and row.get("away_score") == 1) or
            (row.get("home_score") == 1 and row.get("away_score") == 2)
            for row in r["rows"]
        ),
        "brazil vs japan score is 2-1"
    ),

    # player/goal queries
    (
        "who scored for brazil",
        lambda r: len(r["rows"]) > 0,
        "brazil scorers returns results"
    ),
    (
        "how many goals has messi scored",
        lambda r: len(r["rows"]) > 0 and r["rows"][0] is not None,
        "messi goals returns result"
    ),
    (
        "which player has the most yellow cards",
        lambda r: len(r["rows"]) > 0,
        "yellow cards leaderboard returns results"
    ),

    # stats queries
    (
        "show match stats for brazil vs morocco",
        lambda r: len(r["rows"]) == 2,
        "brazil vs morocco stats has 2 rows (one per team)"
    ),
    (
        "which team had the best possession on average",
        lambda r: len(r["rows"]) > 0,
        "possession ranking returns results"
    ),

    # standings
    (
        "show standings for group B",
        lambda r: len(r["rows"]) == 4,
        "group B standings has 4 rows"
    ),

    # partial name matching
    (
        "goals scored by vini",
        lambda r: len(r["rows"]) > 0,
        "partial name vini matches vinicius"
    ),
    (
        "how many minutes did de bruyne play each match",
        lambda r: len(r["rows"]) == 3 and all(
            r2.get("minutes_played") and int(str(r2["minutes_played"])) > 0
            for r2 in r["rows"]
        ),
        "de bruyne minutes played is positive in all 3 matches"
    ),
]

def run_tests():
    passed = 0
    failed = 0
    errors = 0

    for question, assertion, description in TESTS:
        try:
            result = run(question)
            if assertion(result):
                print(f"  PASS  {description}")
                passed += 1
            else:
                print(f"  FAIL  {description}")
                print(f"         question: {question}")
                print(f"         rows: {result['rows'][:2]}")
                print(f"         error: {result.get('error')}")
                failed += 1
        except Exception as e:
            print(f"  ERROR {description}: {e}")
            errors += 1

    print(f"\n{passed} passed, {failed} failed, {errors} errors out of {len(TESTS)} tests")
    return failed + errors == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)