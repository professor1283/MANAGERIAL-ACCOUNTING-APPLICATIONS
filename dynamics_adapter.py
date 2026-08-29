"""Optional Microsoft Dataverse / Dynamics 365 Web API adapter.

The local application works without a Dynamics tenant.  When a tenant is
available, set DATAVERSE_URL and DATAVERSE_ACCESS_TOKEN, create the custom
entity sets described in docs/dataverse_table_mapping.csv, and call the
functions in this module from an administrative synchronization workflow.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class DataverseConfig:
    organization_url: str
    access_token: str
    api_version: str = "v9.2"

    @classmethod
    def from_environment(cls) -> "DataverseConfig":
        url = os.environ.get("DATAVERSE_URL", "").rstrip("/")
        token = os.environ.get("DATAVERSE_ACCESS_TOKEN", "")
        if not url or not token:
            raise RuntimeError("Set DATAVERSE_URL and DATAVERSE_ACCESS_TOKEN before synchronizing.")
        return cls(url, token)


class DataverseClient:
    def __init__(self, config: DataverseConfig):
        self.config = config

    def _request(self, method: str, relative_path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.config.organization_url}/api/data/{self.config.api_version}/{relative_path.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.config.access_token}")
        request.add_header("Accept", "application/json")
        request.add_header("OData-MaxVersion", "4.0")
        request.add_header("OData-Version", "4.0")
        if data is not None:
            request.add_header("Content-Type", "application/json; charset=utf-8")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return {
                    "status": response.status,
                    "headers": dict(response.headers.items()),
                    "body": json.loads(raw) if raw else None,
                }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Dataverse request failed ({exc.code}): {body}") from exc

    def create_row(self, entity_set: str, values: Dict[str, Any]) -> Dict[str, Any]:
        """POST one row to a Dataverse entity set."""
        return self._request("POST", entity_set, values)

    def update_row(self, entity_set: str, row_id: str, values: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH an existing Dataverse row."""
        return self._request("PATCH", f"{entity_set}({row_id})", values)

    def retrieve_rows(self, entity_set: str, query: str = "") -> Dict[str, Any]:
        suffix = f"?{query.lstrip('?')}" if query else ""
        return self._request("GET", f"{entity_set}{suffix}")


ENTITY_SET_MAP = {
    "scenarios": "nb_budgetscenarios",
    "users": "nb_budgetusers",
    "student_entries": "nb_budgetentries",
    "submissions": "nb_budgetsubmissions",
    "submission_schedule_scores": "nb_budgetschedulescores",
    "audit_log": "nb_budgetauditlogs",
}


def map_submission_to_dataverse(submission: Dict[str, Any], student: Dict[str, Any]) -> Dict[str, Any]:
    """Map a local submission to the suggested custom Dataverse table columns."""
    return {
        "nb_name": f"{student['display_name']} - Attempt {submission['attempt_number']}",
        "nb_username": student["username"],
        "nb_studentname": student["display_name"],
        "nb_attemptnumber": int(submission["attempt_number"]),
        "nb_score": float(submission["score"]),
        "nb_submittedatutc": submission["submitted_at"],
        "nb_entriesjson": submission["entries_json"],
        "nb_gradingjson": submission["grading_json"],
    }
