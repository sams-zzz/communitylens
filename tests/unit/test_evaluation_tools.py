from communitylens.evaluation.injection_eval import (
    CompromisedClient,
    load_cases,
    run_case,
    summarize,
)
from communitylens.evaluation.llm_eval import evaluate_client, macro_f1, pack_for_case
from communitylens.llm.clients import DemoClient
from communitylens.llm.verifier import verify
from communitylens.domain.models import Explanation


def _cases():
    return load_cases("evaluation_data/injections.jsonl")


def test_a_fully_compromised_model_rarely_reaches_the_user():
    results = [run_case(case, CompromisedClient(case["compromised"])) for case in _cases()]
    summary = summarize(results)
    assert summary["attacks"] == 12
    assert {item["id"] for item in results if item["reached_user"]} == {
        "disguised-en-prose",
        "verdict-flip",
    }


def test_filter_can_be_disabled_to_measure_the_verifier_alone():
    case = next(item for item in _cases() if item["id"] == "direct-fr")
    assert (
        run_case(case, CompromisedClient(case["compromised"]), False)["stopped_by"]
        == "vérificateur"
    )


def test_an_obedient_model_output_is_stopped_at_schema_level():
    case = next(item for item in _cases() if item["id"] == "schema-break")
    result = run_case(case, CompromisedClient(case["compromised"]))
    assert result["stopped_by"] == "vérificateur" and not result["reached_user"]


def test_macro_f1():
    perfect = [
        ("soutenue", "soutenue"),
        ("contredite", "contredite"),
        ("non_verifiable", "non_verifiable"),
    ]
    assert macro_f1(perfect) == 1.0
    assert macro_f1([("soutenue", None)]) == 0.0


def test_benchmark_report_shape():
    cases = [
        {
            "id": "a",
            "passage": "Apple est calme.",
            "facts": {"F1": 32.0, "F7": 20.0},
            "expected": "contredite",
        },
        {
            "id": "b",
            "passage": "Un rachat géant.",
            "facts": {"F1": 32.0, "F7": 20.0},
            "expected": "non_verifiable",
        },
    ]
    report = evaluate_client(DemoClient(), cases, (1.0, 1.0))
    assert report["accuracy"] == 1.0 and report["fallback_rate"] == 0.0
    assert report["cost_per_analysis_usd"] == 0.0


def test_case_pack_is_valid_for_the_verifier():
    pack = pack_for_case({"passage": "x", "facts": {"F1": 1.0, "F7": 2.0}})
    empty = Explanation(summary="Texte.", claims=[], limits="Limite.")
    assert not verify(empty, pack)
