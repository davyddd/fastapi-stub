import re
from typing import Any, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

SEMVER_PATTERN = re.compile(
    r"""
            ^v?
            (?P<major>0|[1-9]\d*)
            \.
            (?P<minor>0|[1-9]\d*)
            (?:\.
                (?P<patch>0|[1-9]\d*)
            )?
            (?:-[0-9A-Za-z.-]+)?        # optional pre-release
            (?:\+[0-9A-Za-z.-]+)?       # optional build metadata
            $
            """,
    re.VERBOSE,
)


class LenientSemver(str):
    version: str
    version_tuple: tuple[int, int, int]
    is_semantic_valid: bool

    """
    A lenient semver validator that follows https://semver.org with relaxed constraints.

    Accepts version strings that may be different from the accepted semver format
    while maintaining core versioning principles.
    """

    def __init__(self, version: str, /, **data: Any):
        self.version = version
        cleaned_input = version.strip().strip('\'"')

        match = SEMVER_PATTERN.match(cleaned_input)
        if match:
            major = int(match.group('major'))
            minor = int(match.group('minor'))
            patch = int(match.group('patch') or 0)  # default to 0 if missing

            self.version_tuple = (major, minor, patch)
            self.is_semantic_valid = True
        else:
            self.version_tuple = (0, 0, 0)
            self.is_semantic_valid = False

        self.major, self.minor, self.patch = self.version_tuple
        super().__init__(**data)

    @classmethod
    def __get_pydantic_core_schema__(cls, _source: type[Any], _handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def _validate(cls, value: str | Self | Any) -> Self:
        if isinstance(value, cls):
            return value
        elif not isinstance(value, str):
            raise ValueError('can only be string value.')

        return cls(value)

    __hash__ = str.__hash__

    def __str__(self):
        return self.version

    def __repr__(self):
        return f'{self.__class__.__name__}({self.version!r})'

    def __eq__(self, other: Self | Any) -> bool:
        if not isinstance(other, LenientSemver) or not other.is_semantic_valid:
            return self.version == other

        return self.version == other.version

    def __ne__(self, other: Self | Any) -> bool:
        if not isinstance(other, LenientSemver) or not other.is_semantic_valid:
            return self.version != other

        return self.version != other.version

    def __gt__(self, other: Self | Any):
        if not isinstance(other, LenientSemver) or not other.is_semantic_valid:
            return False

        return self.version_tuple > other.version_tuple

    def __ge__(self, other: Self | Any):
        if not isinstance(other, LenientSemver) or not other.is_semantic_valid:
            return False

        return self.version_tuple >= other.version_tuple

    def __lt__(self, other: Self | Any):
        if not isinstance(other, LenientSemver) or not other.is_semantic_valid:
            return False

        return self.version_tuple < other.version_tuple

    def __le__(self, other: Self | Any):
        if not isinstance(other, LenientSemver) or not other.is_semantic_valid:
            return False

        return self.version_tuple <= other.version_tuple
