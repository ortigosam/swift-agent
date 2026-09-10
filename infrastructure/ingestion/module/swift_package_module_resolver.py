from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from infrastructure.ingestion.module.module_resolver import (
    ModuleResolver,
)


@dataclass(frozen=True)
class _SwiftPackageTarget:
    name: str
    root: Path


class SwiftPackageModuleResolver(ModuleResolver):

    TARGET_TYPES = {
        "target",
        "testTarget",
        "executableTarget",
    }

    def __init__(
        self,
        package_path: str,
    ):
        path = Path(package_path).resolve()

        if path.name == "Package.swift":
            self.package_manifest = path
            self.package_root = path.parent
        else:
            self.package_root = path
            self.package_manifest = path / "Package.swift"

        self.available = self.package_manifest.is_file()
        self.targets: list[_SwiftPackageTarget] = []

        if not self.available:
            return

        manifest = self.package_manifest.read_text(
            encoding="utf-8",
        )
        self.targets = self._parse_targets(manifest)

    def resolve(
        self,
        source_path: str,
    ) -> str | None:

        if not self.available:
            return None

        path = Path(source_path)

        if not path.is_absolute():
            path = self.package_root / path

        path = path.resolve()

        for target in sorted(
            self.targets,
            key=lambda target: len(target.root.parts),
            reverse=True,
        ):
            try:
                path.relative_to(target.root)
            except ValueError:
                continue

            return target.name

        return None

    def _parse_targets(
        self,
        manifest: str,
    ) -> list[_SwiftPackageTarget]:

        targets = []

        for target_type, body in self._target_bodies(manifest):
            name = self._extract_string_argument(
                body=body,
                argument="name",
            )

            if name is None:
                continue

            path = self._extract_string_argument(
                body=body,
                argument="path",
            )

            targets.append(
                _SwiftPackageTarget(
                    name=name,
                    root=self._target_root(
                        name=name,
                        target_type=target_type,
                        path=path,
                    ),
                )
            )

        return targets

    def _target_bodies(
        self,
        manifest: str,
    ) -> list[tuple[str, str]]:

        bodies = []
        pattern = re.compile(
            r"\.([A-Za-z]+Target|target)\s*\("
        )

        for match in pattern.finditer(manifest):
            target_type = match.group(1)

            if target_type not in self.TARGET_TYPES:
                continue

            opening_parenthesis = match.end() - 1
            closing_parenthesis = self._find_matching_parenthesis(
                content=manifest,
                opening_parenthesis=opening_parenthesis,
            )

            bodies.append(
                (
                    target_type,
                    manifest[
                        opening_parenthesis + 1:
                        closing_parenthesis
                    ],
                )
            )

        return bodies

    def _target_root(
        self,
        name: str,
        target_type: str,
        path: str | None,
    ) -> Path:

        if path:
            return (
                self.package_root
                / self._clean_path(path)
            ).resolve()

        if target_type == "testTarget":
            return (
                self.package_root
                / "Tests"
                / name
            ).resolve()

        return (
            self.package_root
            / "Sources"
            / name
        ).resolve()

    def _extract_string_argument(
        self,
        body: str,
        argument: str,
    ) -> str | None:

        match = re.search(
            rf"\b{re.escape(argument)}\s*:\s*"
            r'"([^"]+)"',
            body,
        )

        if match is None:
            return None

        return match.group(1)

    def _find_matching_parenthesis(
        self,
        content: str,
        opening_parenthesis: int,
    ) -> int:

        depth = 0
        in_string = False
        escaped = False

        index = opening_parenthesis

        while index < len(content):
            char = content[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False

                index += 1
                continue

            if char == '"':
                in_string = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1

                if depth == 0:
                    return index

            index += 1

        raise ValueError(
            "Malformed Package.swift: unclosed parenthesis"
        )

    def _clean_path(
        self,
        path: str,
    ) -> str:

        return path.strip().strip("/")
