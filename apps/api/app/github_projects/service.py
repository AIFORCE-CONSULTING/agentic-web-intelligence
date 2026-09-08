"""A narrow GitHub Projects V2 REST/GraphQL adapter owned by the API server."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from app.github_projects.contracts import (
    GitHubDraftItem,
    GitHubDraftItemList,
    GitHubProjectInfo,
    GitHubProjectStatus,
)
from app.secrets import DeploymentSecrets, SecretName
from app.settings import Settings

_OWNER_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_GITHUB_API_VERSION = "2026-03-10"


class GitHubProjectsConfigurationError(ValueError):
    """Raised when a connector operation is attempted without a safe configuration."""


class GitHubProjectsProviderError(RuntimeError):
    """A provider failure intentionally stripped of token and upstream response details."""


@dataclass(frozen=True)
class GitHubProjectsConfiguration:
    """The fixed Project target and server-only credential for this deployment."""

    owner: str
    project_number: int
    token: str

    @property
    def project_url(self) -> str:
        return f"https://github.com/orgs/{self.owner}/projects/{self.project_number}"


@dataclass(frozen=True)
class _PriorityField:
    node_id: str
    options: dict[str, str]


class GitHubProjectsBoundary:
    """Validate one configured organization Project without exposing credentials."""

    def __init__(self, settings: Settings, secrets: DeploymentSecrets | None = None) -> None:
        self._settings = settings
        self._secrets = secrets or DeploymentSecrets(settings)

    def configuration(self) -> GitHubProjectsConfiguration | None:
        """Return complete configuration, None when disabled, or a safe configuration error."""

        values = {
            "GITHUB_PROJECT_OWNER": self._settings.github_project_owner,
            "GITHUB_PROJECT_NUMBER": self._settings.github_project_number,
            "GITHUB_CONNECTOR_TOKEN": self._secrets.get(SecretName.GITHUB_CONNECTOR_TOKEN),
        }
        supplied = {name: value for name, value in values.items() if value not in {None, ""}}
        if not supplied:
            return None
        missing = [name for name, value in values.items() if value in {None, ""}]
        if missing:
            raise GitHubProjectsConfigurationError(
                "GitHub Projects configuration is incomplete; missing " + ", ".join(missing) + "."
            )
        owner = (self._settings.github_project_owner or "").strip()
        if not _OWNER_PATTERN.fullmatch(owner):
            raise GitHubProjectsConfigurationError(
                "GITHUB_PROJECT_OWNER must be a valid GitHub organization login."
            )
        project_number_value = self._settings.github_project_number
        try:
            project_number = int(project_number_value or "")
        except ValueError as error:
            raise GitHubProjectsConfigurationError(
                "GITHUB_PROJECT_NUMBER must be a positive Project number."
            ) from error
        if project_number < 1:
            raise GitHubProjectsConfigurationError(
                "GITHUB_PROJECT_NUMBER must be a positive Project number."
            )
        token = self._secrets.get(SecretName.GITHUB_CONNECTOR_TOKEN)
        assert token is not None
        return GitHubProjectsConfiguration(owner, project_number, token)

    def status(self) -> GitHubProjectStatus:
        """Return safe readiness information without performing a GitHub request."""

        try:
            configuration = self.configuration()
        except GitHubProjectsConfigurationError as error:
            return GitHubProjectStatus(mode="invalid", detail=str(error))
        if configuration is None:
            return GitHubProjectStatus(
                mode="disabled",
                detail="GitHub Projects is not configured for this deployment.",
            )
        return GitHubProjectStatus(
            mode="ready",
            owner=configuration.owner,
            project_number=configuration.project_number,
            project_url=configuration.project_url,
            detail="One GitHub Project is configured for human-operated roadmap draft items.",
        )


class GitHubProjectsService:
    """Call only the approved Project V2 endpoints; never expose this service to MCP."""

    def __init__(
        self,
        boundary: GitHubProjectsBoundary,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._boundary = boundary
        self._transport = transport

    async def project_info(self) -> GitHubProjectInfo:
        """Fetch the configured Project and its allowed Priority options."""

        configuration = self._require_configuration()
        project = await self._request(
            configuration,
            "GET",
            f"/orgs/{configuration.owner}/projectsV2/{configuration.project_number}",
        )
        priority_field = await self._priority_field(configuration)
        title = project.get("title")
        if not isinstance(title, str) or not title.strip():
            raise GitHubProjectsProviderError("GitHub returned an invalid Project response.")
        return GitHubProjectInfo(
            title=title,
            owner=configuration.owner,
            project_number=configuration.project_number,
            project_url=configuration.project_url,
            priority_options=sorted(priority_field.options),
        )

    async def create_draft_item(
        self, title: str, body: str | None, priority: str | None
    ) -> GitHubDraftItem:
        """Create one GitHub draft item and optionally set an existing Priority value."""

        configuration = self._require_configuration()
        priority_field = await self._priority_field(configuration) if priority else None
        if priority_field is not None:
            self._require_priority_option(priority_field, priority or "")
        created = await self._request(
            configuration,
            "POST",
            f"/orgs/{configuration.owner}/projectsV2/{configuration.project_number}/drafts",
            {"title": title, **({"body": body} if body else {})},
        )
        value = created.get("value")
        if not isinstance(value, Mapping):
            raise GitHubProjectsProviderError("GitHub returned an invalid draft-item response.")
        item_id = value.get("node_id")
        content = value.get("content")
        item_title = content.get("title") if isinstance(content, Mapping) else None
        if not isinstance(item_id, str):
            raise GitHubProjectsProviderError("GitHub returned an invalid draft-item response.")
        if priority_field is not None:
            await self._set_priority(configuration, item_id, priority_field, priority or "")
        # GitHub may omit the nested draft content from this mutation response.
        # The request title has already passed the API contract, so returning it
        # preserves a stable result without depending on an optional echo.
        return GitHubDraftItem(
            id=item_id,
            title=item_title if isinstance(item_title, str) else title,
            priority=priority,
        )

    async def list_draft_items(self) -> GitHubDraftItemList:
        """Return at most 50 draft cards and their Priority values from the configured Project."""

        configuration = self._require_configuration()
        project = await self._request(
            configuration,
            "GET",
            f"/orgs/{configuration.owner}/projectsV2/{configuration.project_number}",
        )
        project_id = project.get("node_id")
        if not isinstance(project_id, str):
            raise GitHubProjectsProviderError("GitHub returned an invalid Project response.")
        payload = {
            "query": (
                "query DraftItems($projectId: ID!) { node(id: $projectId) { ... on ProjectV2 { "
                "items(first: 50) { nodes { id content { ... on DraftIssue { title } } "
                "fieldValues(first: 20) { nodes { ... on ProjectV2ItemFieldSingleSelectValue { "
                "name field { ... on ProjectV2FieldCommon { name } } } } } } } } } }"
            ),
            "variables": {"projectId": project_id},
        }
        response = await self._request(configuration, "POST", "/graphql", payload)
        if response.get("errors"):
            raise GitHubProjectsProviderError("GitHub rejected the roadmap read.")
        data = response.get("data")
        node = data.get("node") if isinstance(data, Mapping) else None
        items = node.get("items") if isinstance(node, Mapping) else None
        nodes = items.get("nodes") if isinstance(items, Mapping) else None
        if not isinstance(nodes, list):
            raise GitHubProjectsProviderError("GitHub returned an invalid roadmap response.")
        draft_items: list[GitHubDraftItem] = []
        for item in nodes:
            if not isinstance(item, Mapping):
                continue
            item_id = item.get("id")
            content = item.get("content")
            title = content.get("title") if isinstance(content, Mapping) else None
            if not isinstance(item_id, str) or not isinstance(title, str):
                continue
            priority = None
            field_values = item.get("fieldValues")
            values = field_values.get("nodes") if isinstance(field_values, Mapping) else None
            if isinstance(values, list):
                for value in values:
                    if not isinstance(value, Mapping):
                        continue
                    field = value.get("field")
                    if isinstance(field, Mapping) and field.get("name") == "Priority":
                        name = value.get("name")
                        priority = name if isinstance(name, str) else None
                        break
            draft_items.append(GitHubDraftItem(id=item_id, title=title, priority=priority))
        return GitHubDraftItemList(items=draft_items)

    async def update_draft_item_priority(self, item_id: str, priority: str) -> GitHubDraftItem:
        """Set only the configured Project's existing Priority single-select field."""

        configuration = self._require_configuration()
        priority_field = await self._priority_field(configuration)
        self._require_priority_option(priority_field, priority)
        await self._set_priority(configuration, item_id, priority_field, priority)
        return GitHubDraftItem(id=item_id, title="", priority=priority)

    def _require_configuration(self) -> GitHubProjectsConfiguration:
        configuration = self._boundary.configuration()
        if configuration is None:
            raise GitHubProjectsConfigurationError(
                "GitHub Projects is not configured for this deployment."
            )
        return configuration

    async def _priority_field(self, configuration: GitHubProjectsConfiguration) -> _PriorityField:
        fields = await self._request(
            configuration,
            "GET",
            f"/orgs/{configuration.owner}/projectsV2/{configuration.project_number}/fields",
        )
        if not isinstance(fields, list):
            raise GitHubProjectsProviderError("GitHub returned an invalid Project-fields response.")
        for field in fields:
            if not isinstance(field, Mapping):
                continue
            if field.get("name") != "Priority" or field.get("data_type") != "single_select":
                continue
            node_id = field.get("node_id")
            options = field.get("options")
            if not isinstance(node_id, str) or not isinstance(options, list):
                break
            parsed_options: dict[str, str] = {}
            for option in options:
                if not isinstance(option, Mapping):
                    continue
                option_id = option.get("id")
                name = option.get("name")
                raw_name = name.get("raw") if isinstance(name, Mapping) else name
                if isinstance(option_id, str) and isinstance(raw_name, str):
                    parsed_options[raw_name] = option_id
            if parsed_options:
                return _PriorityField(node_id=node_id, options=parsed_options)
        raise GitHubProjectsConfigurationError(
            "The configured GitHub Project must have a Priority single-select field with options."
        )

    @staticmethod
    def _require_priority_option(field: _PriorityField, priority: str) -> None:
        if priority not in field.options:
            raise GitHubProjectsConfigurationError(
                "Priority must match an option configured in the GitHub Project."
            )

    async def _set_priority(
        self,
        configuration: GitHubProjectsConfiguration,
        item_id: str,
        field: _PriorityField,
        priority: str,
    ) -> None:
        project = await self._request(
            configuration,
            "GET",
            f"/orgs/{configuration.owner}/projectsV2/{configuration.project_number}",
        )
        project_id = project.get("node_id")
        if not isinstance(project_id, str):
            raise GitHubProjectsProviderError("GitHub returned an invalid Project response.")
        payload = {
            "query": (
                "mutation UpdatePriority($projectId: ID!, $itemId: ID!, $fieldId: ID!, "
                "$optionId: String!) { updateProjectV2ItemFieldValue(input: { "
                "projectId: $projectId, itemId: $itemId, fieldId: $fieldId, "
                "value: { singleSelectOptionId: $optionId } }) { projectV2Item { id } } }"
            ),
            "variables": {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field.node_id,
                "optionId": field.options[priority],
            },
        }
        response = await self._request(configuration, "POST", "/graphql", payload)
        if response.get("errors"):
            raise GitHubProjectsProviderError("GitHub rejected the Priority update.")
        data = response.get("data")
        updated_value = (
            data.get("updateProjectV2ItemFieldValue") if isinstance(data, Mapping) else None
        )
        if not isinstance(updated_value, Mapping):
            raise GitHubProjectsProviderError(
                "GitHub returned an invalid Priority-update response."
            )

    async def _request(
        self,
        configuration: GitHubProjectsConfiguration,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {configuration.token}",
            "X-GitHub-Api-Version": _GITHUB_API_VERSION,
        }
        try:
            async with httpx.AsyncClient(
                base_url="https://api.github.com",
                headers=headers,
                timeout=10.0,
                transport=self._transport,
            ) as client:
                response = await client.request(method, path, json=payload)
        except httpx.HTTPError as error:
            raise GitHubProjectsProviderError("GitHub Projects is unavailable.") from error
        if response.status_code in {401, 403}:
            raise GitHubProjectsProviderError("GitHub did not authorize this connector.")
        if response.status_code >= 500:
            raise GitHubProjectsProviderError("GitHub Projects is unavailable.")
        if response.status_code >= 400:
            raise GitHubProjectsProviderError("GitHub rejected the connector request.")
        try:
            return response.json()
        except ValueError as error:
            raise GitHubProjectsProviderError("GitHub returned an invalid response.") from error
