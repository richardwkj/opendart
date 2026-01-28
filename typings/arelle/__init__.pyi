from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class ModelType(Protocol):
    name: str


class ModelConcept(Protocol):
    type: ModelType | None
    qname: object

    def label(self) -> str | None: ...


class ModelFact(Protocol):
    concept: ModelConcept | None
    value: object
    contextID: str | None


class ModelXbrl(Protocol):
    @property
    def facts(self) -> Iterable[ModelFact]: ...


class ModelManager(Protocol):
    def load(self, filesource: str, *args: object, **kwargs: object) -> ModelXbrl | None: ...

    def close(self, modelXbrl: ModelXbrl | None = None) -> None: ...


class Cntlr:
    modelManager: ModelManager

    def __init__(self, logFileName: str | None = None) -> None: ...
