"""
Policy engine for ArcOps MCP.

Evaluates policy rules against check results to produce verdicts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class Verdict(str, Enum):
    """Policy verdict outcomes."""

    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


@dataclass
class RuleResult:
    """Result of evaluating a single policy rule."""

    rule_name: str
    passed: bool
    verdict: str
    reason: str
    severity: str = "medium"


@dataclass
class PolicyResult:
    """Result of evaluating all policy rules."""

    policy_name: str
    policy_version: str
    rules_evaluated: int
    rules_passed: int
    rules_failed: int
    verdict: str
    results: list[RuleResult] = field(default_factory=list)
    failures: list[dict[str, str]] = field(default_factory=list)


class PolicyEngine:
    """Evaluates policy rules against data."""

    def __init__(self, policy_path: str | Path | None = None):
        self.policy: dict[str, Any] = {}
        self.policy_path = policy_path

        if policy_path:
            self.load_policy(policy_path)

    def load_policy(self, policy_path: str | Path) -> None:
        """Load policy from YAML file."""
        path = Path(policy_path)
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {policy_path}")

        with open(path, "r", encoding="utf-8") as f:
            self.policy = yaml.safe_load(f)
        self.policy_path = str(path)

    def load_policy_from_dict(self, policy: dict[str, Any]) -> None:
        """Load policy from dictionary."""
        self.policy = policy

    def _get_nested_value(self, data: dict[str, Any], path: str) -> Any:
        """Get value from nested dict using dot notation (e.g., 'sbom.vulnerabilities.critical')."""
        parts = path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _evaluate_condition(self, condition: str, data: dict[str, Any]) -> bool:
        """
        Evaluate a simple condition against data.

        Supports:
        - field == value
        - field != value
        - field > value
        - field >= value
        - field < value
        - field <= value
        - field in list
        - field == true/false
        """
        # Parse condition
        patterns = [
            (r"(\S+)\s*==\s*true", lambda m, d: self._get_nested_value(d, m.group(1)) is True),
            (r"(\S+)\s*==\s*false", lambda m, d: self._get_nested_value(d, m.group(1)) is False),
            (
                r"(\S+)\s*==\s*(\d+)",
                lambda m, d: self._get_nested_value(d, m.group(1)) == int(m.group(2)),
            ),
            (
                r"(\S+)\s*!=\s*(\d+)",
                lambda m, d: self._get_nested_value(d, m.group(1)) != int(m.group(2)),
            ),
            (
                r"(\S+)\s*>=\s*(\d+)",
                lambda m, d: (v := self._get_nested_value(d, m.group(1))) is not None
                and v >= int(m.group(2)),
            ),
            (
                r"(\S+)\s*<=\s*(\d+)",
                lambda m, d: (v := self._get_nested_value(d, m.group(1))) is not None
                and v <= int(m.group(2)),
            ),
            (
                r"(\S+)\s*>\s*(\d+)",
                lambda m, d: (v := self._get_nested_value(d, m.group(1))) is not None
                and v > int(m.group(2)),
            ),
            (
                r"(\S+)\s*<\s*(\d+)",
                lambda m, d: (v := self._get_nested_value(d, m.group(1))) is not None
                and v < int(m.group(2)),
            ),
            (
                r"(\S+)\s+in\s+(\w+)",
                lambda m, d: self._get_nested_value(d, m.group(1)) in self._get_setting(m.group(2)),
            ),
        ]

        for pattern, evaluator in patterns:
            match = re.match(pattern, condition.strip())
            if match:
                try:
                    return evaluator(match, data)
                except (TypeError, ValueError):
                    return False

        # Default: condition not understood, fail safe
        return False

    def _get_setting(self, setting_name: str) -> list[Any]:
        """Get a setting value from policy settings."""
        settings = self.policy.get("settings", {})
        return settings.get(setting_name, [])

    def evaluate(self, data: dict[str, Any]) -> PolicyResult:
        """
        Evaluate all policy rules against provided data.

        Args:
            data: The data to evaluate (e.g., signature validation results)

        Returns:
            PolicyResult with overall verdict and per-rule results
        """
        rules = self.policy.get("rules", [])
        results: list[RuleResult] = []
        failures: list[dict[str, str]] = []

        final_verdict = Verdict.GREEN.value
        verdict_priority = {Verdict.GREEN.value: 0, Verdict.AMBER.value: 1, Verdict.RED.value: 2}

        for rule in rules:
            rule_name = rule.get("name", "unnamed")
            condition = rule.get("condition", "")
            pass_verdict = rule.get("verdict", Verdict.GREEN.value)
            fail_verdict = rule.get("failVerdict", Verdict.RED.value)
            description = rule.get("description", "")
            severity = rule.get("severity", "medium")

            passed = self._evaluate_condition(condition, data)

            result = RuleResult(
                rule_name=rule_name,
                passed=passed,
                verdict=pass_verdict if passed else fail_verdict,
                reason=description if passed else f"Failed: {description}",
                severity=severity,
            )
            results.append(result)

            if not passed:
                failures.append(
                    {
                        "rule": rule_name,
                        "reason": description or f"Condition not met: {condition}",
                        "severity": severity,
                    }
                )
                # Update final verdict if this failure is worse
                if verdict_priority.get(fail_verdict, 0) > verdict_priority.get(final_verdict, 0):
                    final_verdict = fail_verdict

        return PolicyResult(
            policy_name=self.policy.get("name", "unknown"),
            policy_version=self.policy.get("version", "1.0"),
            rules_evaluated=len(rules),
            rules_passed=sum(1 for r in results if r.passed),
            rules_failed=sum(1 for r in results if not r.passed),
            verdict=final_verdict,
            results=results,
            failures=failures,
        )


def evaluate_policy(data: dict[str, Any], policy_path: str | Path) -> PolicyResult:
    """Convenience function to evaluate data against a policy file."""
    engine = PolicyEngine(policy_path)
    return engine.evaluate(data)
