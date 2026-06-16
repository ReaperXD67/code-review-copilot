import asyncio
import hashlib
import hmac
import importlib
import json
import os
import sys
import types
import unittest
from types import SimpleNamespace

from fastapi import BackgroundTasks, HTTPException
from starlette.requests import Request


def build_request(body: bytes) -> Request:
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {"type": "http", "method": "POST", "path": "/webhook/github", "headers": []},
        receive,
    )


def signature_for(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def load_main_with_fake_services(secret: str = "unit-test-secret"):
    calls = {}

    fake_github = types.ModuleType("app.services.github")

    def get_pr_diff(repo, pr):
        calls["get_pr_diff"] = (repo, pr)
        return "[1] +change"

    def post_pr_review(repo, pr, review):
        calls["post_pr_review"] = (repo, pr, review.risk_summary)

    fake_github.get_pr_diff = get_pr_diff
    fake_github.post_pr_review = post_pr_review

    fake_reviewer = types.ModuleType("app.services.reviewer")

    def analyze_pr_diff(diff, house_rules="None"):
        calls["analyze_pr_diff"] = (diff, house_rules)
        return SimpleNamespace(risk_summary="No major risks")

    fake_reviewer.analyze_pr_diff = analyze_pr_diff

    fake_chroma = types.ModuleType("app.services.chroma")

    def learn_convention(rule, repo):
        calls["learn_convention"] = (rule, repo)

    def retrieve_relevant_rules(diff, repo):
        calls["retrieve_relevant_rules"] = (diff, repo)
        return "- Use structured logging"

    fake_chroma.learn_convention = learn_convention
    fake_chroma.retrieve_relevant_rules = retrieve_relevant_rules

    fake_history = types.ModuleType("app.services.history")
    fake_history.extract_rules_from_history_task = lambda repo: calls.setdefault(
        "extract_rules_from_history_task", repo
    )

    for module_name in [
        "app.main",
        "app.services.github",
        "app.services.reviewer",
        "app.services.chroma",
        "app.services.history",
    ]:
        sys.modules.pop(module_name, None)

    sys.modules["app.services.github"] = fake_github
    sys.modules["app.services.reviewer"] = fake_reviewer
    sys.modules["app.services.chroma"] = fake_chroma
    sys.modules["app.services.history"] = fake_history

    os.environ["WEBHOOK_SECRET"] = secret
    return importlib.import_module("app.main"), calls


class MainApiTests(unittest.TestCase):
    def test_add_house_rule_passes_repo_namespace(self):
        main, calls = load_main_with_fake_services()
        request = main.ConventionRequest(
            repo_name="ExampleOrg/example-repo",
            rule="Use structured logging instead of print",
        )

        response = asyncio.run(main.add_house_rule(request))

        self.assertEqual(
            calls["learn_convention"],
            ("Use structured logging instead of print", "ExampleOrg/example-repo"),
        )
        self.assertEqual(response["repo_name"], "ExampleOrg/example-repo")

    def test_verify_github_signature_accepts_only_matching_digest(self):
        secret = "signature-secret"
        main, _ = load_main_with_fake_services(secret=secret)
        body = b'{"action":"opened"}'

        self.assertTrue(main.verify_github_signature(body, signature_for(secret, body)))
        self.assertFalse(main.verify_github_signature(body, "sha256=wrong"))
        self.assertFalse(main.verify_github_signature(body, None))

    def test_webhook_rejects_malformed_json(self):
        secret = "webhook-secret"
        main, _ = load_main_with_fake_services(secret=secret)
        body = b"{not-json"

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                main.github_webhook(
                    build_request(body),
                    BackgroundTasks(),
                    x_hub_signature_256=signature_for(secret, body),
                )
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "Invalid JSON payload")

    def test_webhook_requires_pr_number_for_reviewable_actions(self):
        secret = "webhook-secret"
        main, _ = load_main_with_fake_services(secret=secret)
        body = json.dumps(
            {
                "action": "opened",
                "repository": {"full_name": "ExampleOrg/example-repo"},
                "pull_request": {},
            }
        ).encode("utf-8")

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                main.github_webhook(
                    build_request(body),
                    BackgroundTasks(),
                    x_hub_signature_256=signature_for(secret, body),
                )
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(
            raised.exception.detail, "Pull request number missing from payload"
        )

    def test_webhook_runs_review_flow_for_opened_pr(self):
        secret = "webhook-secret"
        main, calls = load_main_with_fake_services(secret=secret)
        background_tasks = BackgroundTasks()
        body = json.dumps(
            {
                "action": "opened",
                "repository": {"full_name": "ExampleOrg/example-repo"},
                "pull_request": {"number": 42},
            }
        ).encode("utf-8")

        response = asyncio.run(
            main.github_webhook(
                build_request(body),
                background_tasks,
                x_hub_signature_256=signature_for(secret, body),
            )
        )

        self.assertEqual(response["status"], "review_triggered_and_history_checked")
        self.assertEqual(calls["get_pr_diff"], ("ExampleOrg/example-repo", 42))
        self.assertEqual(calls["retrieve_relevant_rules"], ("[1] +change", "ExampleOrg/example-repo"))
        self.assertEqual(calls["analyze_pr_diff"], ("[1] +change", "- Use structured logging"))
        self.assertEqual(calls["post_pr_review"], ("ExampleOrg/example-repo", 42, "No major risks"))
        self.assertEqual(len(background_tasks.tasks), 1)


if __name__ == "__main__":
    unittest.main()
