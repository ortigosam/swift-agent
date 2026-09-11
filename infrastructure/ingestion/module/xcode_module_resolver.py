from __future__ import annotations

import re
from pathlib import Path

from infrastructure.ingestion.module.module_resolver import (
    ModuleResolver,
)


class XcodeModuleResolver(ModuleResolver):

    SOURCE_GROUP_TYPES = {
        "PBXGroup",
        "PBXVariantGroup",
        "PBXFileSystemSynchronizedRootGroup",
    }

    def __init__(self, xcodeproj_path: str):
        self.xcodeproj_path = Path(xcodeproj_path).resolve()

        self.pbxproj_path = (
            self.xcodeproj_path / "project.pbxproj"
        )

        self.project_root = self.xcodeproj_path.parent

        self.objects: dict[str, dict] = {}

        self._file_reference_ids_by_path: dict[
            str,
            list[str],
        ] = {}

        self.available = False

        # Xcode project does not exist.
        if not self.xcodeproj_path.is_dir():
            return

        # Invalid Xcode project path.
        if self.xcodeproj_path.suffix != ".xcodeproj":
            return

        # project.pbxproj does not exist.
        if not self.pbxproj_path.is_file():
            return

        self.objects = self._load_objects()

        self._build_indexes()

        self.available = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, source_path: str) -> str | None:
        """
        Resolve the Xcode target/module containing source_path.

        Returns None if:
        - the Xcode project does not exist
        - project.pbxproj does not exist
        - the file cannot be resolved
        - the file does not belong to a target
        """

        if not self.available:
            return None

        relative_path = self._relative_path(source_path)

        if relative_path is None:
            return None

        file_reference_ids = (
            self._find_file_references(relative_path)
        )

        if not file_reference_ids:
            modules = self._find_synchronized_target_names(
                relative_path
            )

            if modules:
                return modules[0]

            return None

        build_file_ids = self._find_build_files(
            file_reference_ids
        )

        if not build_file_ids:
            return None

        source_phase_ids = self._find_source_build_phases(
            build_file_ids
        )

        if not source_phase_ids:
            modules = self._find_synchronized_target_names(
                relative_path
            )

            if modules:
                return modules[0]

            return None

        modules = self._find_target_names(
            source_phase_ids
        )

        if not modules:
            modules = self._find_synchronized_target_names(
                relative_path
            )

            if modules:
                return modules[0]

            return None

        # A file can technically belong to multiple targets.
        # The current CodeChunk model expects one module,
        # so we use the first deterministic result.
        return modules[0]

    def _find_synchronized_target_names(
        self,
        relative_path: Path,
    ) -> list[str]:

        normalized = self._normalize_path(
            relative_path
        )

        return self._synchronized_targets_by_path.get(
            normalized,
            [],
        )

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_objects(self) -> dict[str, dict]:
        content = self.pbxproj_path.read_text(
            encoding="utf-8"
        )

        objects_content = self._extract_objects_section(
            content
        )

        return self._parse_objects(
            objects_content
        )

    def _extract_objects_section(
        self,
        content: str,
    ) -> str:

        match = re.search(
            r"\bobjects\s*=\s*\{",
            content,
        )

        if match is None:
            raise ValueError(
                "Could not find objects section "
                "in project.pbxproj"
            )

        start = match.end()

        end = self._find_matching_brace(
            content,
            start - 1,
        )

        return content[start:end]

    # ------------------------------------------------------------------
    # Object parser
    # ------------------------------------------------------------------

    def _parse_objects(
        self,
        content: str,
    ) -> dict[str, dict]:

        objects: dict[str, dict] = {}

        index = 0
        length = len(content)

        while index < length:

            match = re.search(
                r"(?m)^\s*"
                r"([A-Fa-f0-9]{8,32})"
                r"(?:\s*/\*.*?\*/)?"
                r"\s*=\s*\{",
                content[index:],
            )

            if match is None:
                break

            object_id = match.group(1)

            opening_brace = (
                index
                + match.end()
                - 1
            )

            closing_brace = self._find_matching_brace(
                content,
                opening_brace,
            )

            body = content[
                opening_brace + 1:
                closing_brace
            ]

            objects[object_id] = (
                self._parse_object_body(body)
            )

            index = closing_brace + 1

        return objects

    def _parse_object_body(
        self,
        body: str,
    ) -> dict:

        attributes: dict = {}

        isa_match = re.search(
            r"\bisa\s*=\s*([A-Za-z0-9_]+)\s*;",
            body,
        )

        if isa_match:
            attributes["isa"] = isa_match.group(1)

        attributes["path"] = self._parse_scalar(
            body,
            "path",
        )

        attributes["name"] = self._parse_scalar(
            body,
            "name",
        )

        attributes["sourceTree"] = self._parse_scalar(
            body,
            "sourceTree",
        )

        attributes["fileRef"] = self._parse_scalar(
            body,
            "fileRef",
        )

        attributes["target"] = self._parse_scalar(
            body,
            "target",
        )

        attributes["children"] = self._parse_array(
            body,
            "children",
        )

        attributes["files"] = self._parse_array(
            body,
            "files",
        )

        attributes["buildPhases"] = self._parse_array(
            body,
            "buildPhases",
        )

        attributes["exceptions"] = self._parse_array(
            body,
            "exceptions",
        )

        attributes["fileSystemSynchronizedGroups"] = (
            self._parse_array(
                body,
                "fileSystemSynchronizedGroups",
            )
        )

        attributes["membershipExceptions"] = (
            self._parse_value_array(
                body,
                "membershipExceptions",
            )
        )

        return attributes

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------

    def _build_indexes(self) -> None:

        self.file_references = {
            object_id: obj
            for object_id, obj in self.objects.items()
            if obj.get("isa") == "PBXFileReference"
        }

        self.build_files = {
            object_id: obj
            for object_id, obj in self.objects.items()
            if obj.get("isa") == "PBXBuildFile"
        }

        self.sources_build_phases = {
            object_id: obj
            for object_id, obj in self.objects.items()
            if obj.get("isa") == "PBXSourcesBuildPhase"
        }

        self.native_targets = {
            object_id: obj
            for object_id, obj in self.objects.items()
            if obj.get("isa") == "PBXNativeTarget"
        }

        self.synchronized_root_groups = {
            object_id: obj
            for object_id, obj in self.objects.items()
            if (
                obj.get("isa")
                == "PBXFileSystemSynchronizedRootGroup"
            )
        }

        self.synchronized_exception_sets = {
            object_id: obj
            for object_id, obj in self.objects.items()
            if (
                obj.get("isa")
                == "PBXFileSystemSynchronizedBuildFileExceptionSet"
            )
        }

        self.parent_groups = {}

        for group_id, group in self.objects.items():

            if group.get("isa") not in self.SOURCE_GROUP_TYPES:
                continue

            for child_id in group.get("children", []):
                self.parent_groups[child_id] = group_id

        self._file_reference_ids_by_path = {}

        for file_id in self.file_references:

            path = self._resolve_file_reference_path(
                file_id
            )

            if path is None:
                continue

            normalized = self._normalize_path(path)

            self._file_reference_ids_by_path.setdefault(
                normalized,
                [],
            ).append(file_id)

        self._synchronized_targets_by_path: dict[
            str,
            list[str],
        ] = {}

        self._build_synchronized_root_indexes()

    def _build_synchronized_root_indexes(self) -> None:

        for root_id, root in (
            self.synchronized_root_groups.items()
        ):
            root_path = self._resolve_group_path(
                root_id
            )

            if root_path is None:
                continue

            self._index_synchronized_group_targets(
                root_id=root_id,
                root_path=root_path,
            )

            self._index_synchronized_exceptions(
                root=root,
                root_path=root_path,
            )

    def _index_synchronized_group_targets(
        self,
        root_id: str,
        root_path: Path,
    ) -> None:

        root_dir = self.project_root / root_path

        if not root_dir.is_dir():
            return

        target_names = self._find_targets_for_synchronized_group(
            root_id
        )

        if not target_names:
            return

        for source_file in root_dir.rglob("*.swift"):
            relative_path = source_file.relative_to(
                self.project_root
            )
            self._add_synchronized_target_path(
                relative_path=relative_path,
                target_names=target_names,
            )

    def _index_synchronized_exceptions(
        self,
        root: dict,
        root_path: Path,
    ) -> None:

        for exception_id in root.get("exceptions", []):
            exception = self.synchronized_exception_sets.get(
                exception_id
            )

            if exception is None:
                continue

            target_id = self._extract_id(
                exception.get("target")
            )

            target_names = self._target_names_by_ids(
                [target_id] if target_id else []
            )

            if not target_names:
                continue

            for member_path in exception.get(
                "membershipExceptions",
                [],
            ):
                relative_path = root_path / member_path

                self._add_synchronized_target_path(
                    relative_path=relative_path,
                    target_names=target_names,
                )

    def _add_synchronized_target_path(
        self,
        relative_path: Path,
        target_names: list[str],
    ) -> None:

        normalized = self._normalize_path(
            relative_path
        )

        current = self._synchronized_targets_by_path.setdefault(
            normalized,
            [],
        )

        current.extend(target_names)

        self._synchronized_targets_by_path[normalized] = sorted(
            set(current)
        )

    # ------------------------------------------------------------------
    # File resolution
    # ------------------------------------------------------------------

    def _relative_path(
        self,
        source_path: str,
    ) -> Path | None:

        path = Path(source_path)

        if not path.is_absolute():
            path = self.project_root / path

        path = path.resolve()

        try:
            return path.relative_to(
                self.project_root
            )
        except ValueError:
            return None

    def _find_file_references(
        self,
        relative_path: Path,
    ) -> list[str]:

        normalized = self._normalize_path(
            relative_path
        )

        return self._file_reference_ids_by_path.get(
            normalized,
            [],
        )

    def _resolve_file_reference_path(
        self,
        file_reference_id: str,
    ) -> Path | None:

        file_reference = self.file_references.get(
            file_reference_id
        )

        if file_reference is None:
            return None

        path = (
            file_reference.get("path")
            or file_reference.get("name")
        )

        if not path:
            return None

        path = Path(
            self._clean_value(path)
        )

        parent_id = self.parent_groups.get(
            file_reference_id
        )

        visited: set[str] = set()

        while parent_id:

            if parent_id in visited:
                break

            visited.add(parent_id)

            parent = self.objects.get(
                parent_id
            )

            if parent is None:
                break

            parent_path = (
                parent.get("path")
                or parent.get("name")
            )

            if parent_path:
                parent_path = Path(
                    self._clean_value(parent_path)
                )

                path = (
                    parent_path / path
                )

            parent_id = self.parent_groups.get(
                parent_id
            )

        return path

    def _resolve_group_path(
        self,
        group_id: str,
    ) -> Path | None:

        group = self.objects.get(group_id)

        if group is None:
            return None

        path_value = (
            group.get("path")
            or group.get("name")
        )

        if not path_value:
            return None

        path = Path(
            self._clean_value(path_value)
        )

        parent_id = self.parent_groups.get(
            group_id
        )

        visited: set[str] = set()

        while parent_id:

            if parent_id in visited:
                break

            visited.add(parent_id)

            parent = self.objects.get(
                parent_id
            )

            if parent is None:
                break

            parent_path = (
                parent.get("path")
                or parent.get("name")
            )

            if parent_path:
                path = (
                    Path(self._clean_value(parent_path))
                    / path
                )

            parent_id = self.parent_groups.get(
                parent_id
            )

        return path

    # ------------------------------------------------------------------
    # Build phases / targets
    # ------------------------------------------------------------------

    def _find_build_files(
        self,
        file_reference_ids: list[str],
    ) -> list[str]:

        result = []

        file_reference_ids_set = set(
            file_reference_ids
        )

        for build_file_id, build_file in (
            self.build_files.items()
        ):
            file_ref = self._extract_id(
                build_file.get("fileRef")
            )

            if file_ref in file_reference_ids_set:
                result.append(build_file_id)

        return result

    def _find_source_build_phases(
        self,
        build_file_ids: list[str],
    ) -> list[str]:

        result = []

        build_file_ids_set = set(
            build_file_ids
        )

        for phase_id, phase in (
            self.sources_build_phases.items()
        ):
            files = set(
                phase.get("files", [])
            )

            if files & build_file_ids_set:
                result.append(phase_id)

        return result

    def _find_target_names(
        self,
        source_phase_ids: list[str],
    ) -> list[str]:

        result = []

        source_phase_ids_set = set(
            source_phase_ids
        )

        for target in self.native_targets.values():

            build_phases = set(
                target.get("buildPhases", [])
            )

            if not (
                build_phases
                & source_phase_ids_set
            ):
                continue

            name = target.get("name")

            if not name:
                name = target.get("productName")

            if name:
                result.append(
                    self._clean_value(name)
                )

        return sorted(
            set(result)
        )

    def _find_targets_for_synchronized_group(
        self,
        group_id: str,
    ) -> list[str]:

        result = []

        for target_id, target in (
            self.native_targets.items()
        ):
            synchronized_groups = set(
                target.get(
                    "fileSystemSynchronizedGroups",
                    [],
                )
            )

            if group_id not in synchronized_groups:
                continue

            result.extend(
                self._target_names_by_ids([target_id])
            )

        return sorted(
            set(result)
        )

    def _target_names_by_ids(
        self,
        target_ids: list[str],
    ) -> list[str]:

        result = []

        for target_id in target_ids:
            target = self.native_targets.get(target_id)

            if target is None:
                continue

            name = target.get("name")

            if not name:
                name = target.get("productName")

            if name:
                result.append(
                    self._clean_value(name)
                )

        return sorted(
            set(result)
        )

    # ------------------------------------------------------------------
    # Primitive parser helpers
    # ------------------------------------------------------------------

    def _parse_scalar(
        self,
        body: str,
        key: str,
    ) -> str | None:

        pattern = (
            rf"\b{re.escape(key)}\s*=\s*"
            rf"([^;]+);"
        )

        match = re.search(
            pattern,
            body,
            re.DOTALL,
        )

        if match is None:
            return None

        return self._clean_value(
            match.group(1)
        )

    def _parse_array(
        self,
        body: str,
        key: str,
    ) -> list[str]:

        pattern = (
            rf"\b{re.escape(key)}\s*=\s*\("
            rf"(.*?)"
            rf"\);"
        )

        match = re.search(
            pattern,
            body,
            re.DOTALL,
        )

        if match is None:
            return []

        return re.findall(
            r"\b[A-Fa-f0-9]{8,32}\b",
            match.group(1),
        )

    def _parse_value_array(
        self,
        body: str,
        key: str,
    ) -> list[str]:

        pattern = (
            rf"\b{re.escape(key)}\s*=\s*\("
            rf"(.*?)"
            rf"\);"
        )

        match = re.search(
            pattern,
            body,
            re.DOTALL,
        )

        if match is None:
            return []

        result = []

        for raw_value in match.group(1).split(","):
            value = self._clean_value(raw_value)

            if not value:
                continue

            result.append(value)

        return result

    def _extract_id(
        self,
        value: str | None,
    ) -> str | None:

        if not value:
            return None

        match = re.search(
            r"\b[A-Fa-f0-9]{8,32}\b",
            value,
        )

        if match is None:
            return None

        return match.group(0)

    # ------------------------------------------------------------------
    # General helpers
    # ------------------------------------------------------------------

    def _find_matching_brace(
        self,
        content: str,
        opening_brace: int,
    ) -> int:

        depth = 0
        in_string = False
        escaped = False

        index = opening_brace

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

            elif char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

                if depth == 0:
                    return index

            index += 1

        raise ValueError(
            "Malformed project.pbxproj: "
            "unclosed brace"
        )

    def _clean_value(
        self,
        value: str,
    ) -> str:

        value = value.strip()

        # Remove Xcode comments.
        value = re.sub(
            r"/\*.*?\*/",
            "",
            value,
            flags=re.DOTALL,
        ).strip()

        if (
            len(value) >= 2
            and value[0] == '"'
            and value[-1] == '"'
        ):
            value = value[1:-1]

        return value

    def _normalize_path(
        self,
        path: Path,
    ) -> str:

        return str(
            Path(path).as_posix()
        ).strip("/")
