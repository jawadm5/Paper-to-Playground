"""Strict Pydantic contract for a renderable interactive lesson."""

from typing import Annotated, List, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
    field_validator,
)


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Number = Union[StrictInt, StrictFloat]
NonEmptyIdList = Annotated[List[NonEmptyString], Field(min_length=1)]

ControlType = Literal["slider", "number_input", "toggle", "matrix_editor"]
VisualizationType = Literal[
    "bar_chart",
    "line_chart",
    "heatmap",
    "matrix_display",
    "step_pipeline",
]
ComputationOperation = Literal[
    "add",
    "subtract",
    "multiply",
    "divide",
    "sqrt",
    "sum",
    "normalize",
    "softmax",
    "row_softmax",
    "transpose",
    "matrix_multiply",
    "matmul_transpose",
]


class StrictModel(BaseModel):
    """Base model shared by every part of the public contract."""

    model_config = ConfigDict(extra="forbid", strict=True)


class LessonMeta(StrictModel):
    title: NonEmptyString
    subtitle: NonEmptyString


class LessonIntro(StrictModel):
    why_it_matters: NonEmptyString
    overview: NonEmptyString


class SymbolDefinition(StrictModel):
    symbol: NonEmptyString
    label: NonEmptyString
    description: NonEmptyString


class ScalarVariable(StrictModel):
    id: NonEmptyString
    type: Literal["scalar"]
    default: Number


class BooleanVariable(StrictModel):
    id: NonEmptyString
    type: Literal["boolean"]
    default: StrictBool


class VectorVariable(StrictModel):
    id: NonEmptyString
    type: Literal["vector"]
    default: Annotated[List[Number], Field(min_length=1)]


class MatrixVariable(StrictModel):
    id: NonEmptyString
    type: Literal["matrix"]
    default: Annotated[List[List[Number]], Field(min_length=1)]

    @field_validator("default")
    @classmethod
    def matrix_must_be_non_empty_and_rectangular(
        cls, value: List[List[Number]]
    ) -> List[List[Number]]:
        if any(len(row) == 0 for row in value):
            raise ValueError("matrix rows must not be empty")
        row_widths = {len(row) for row in value}
        if len(row_widths) != 1:
            raise ValueError("matrix rows must all have the same length")
        return value


Variable = Annotated[
    Union[ScalarVariable, BooleanVariable, VectorVariable, MatrixVariable],
    Field(discriminator="type"),
]


class Control(StrictModel):
    id: NonEmptyString
    type: ControlType
    variable: NonEmptyString
    label: NonEmptyString
    min: Optional[Number] = None
    max: Optional[Number] = None
    step: Optional[Number] = None


class Computation(StrictModel):
    id: NonEmptyString
    op: ComputationOperation
    inputs: NonEmptyIdList


class Visualization(StrictModel):
    id: NonEmptyString
    type: VisualizationType
    data: Union[NonEmptyString, NonEmptyIdList]
    title: NonEmptyString


class IntermediateValue(StrictModel):
    label: NonEmptyString
    data: NonEmptyString


class GuidedExploration(StrictModel):
    title: NonEmptyString
    instruction: NonEmptyString
    observe: NonEmptyString
    explanation: NonEmptyString


class Limitation(StrictModel):
    text: NonEmptyString


class Source(StrictModel):
    paper: NonEmptyString
    section: NonEmptyString
    url: NonEmptyString


class LessonRenderSpec(StrictModel):
    """Version 0.1 contract exchanged between LLM2 and the renderer."""

    schema_version: Literal["0.1"]
    meta: LessonMeta
    intro: LessonIntro
    symbols: List[SymbolDefinition]
    variables: List[Variable]
    controls: Annotated[List[Control], Field(min_length=2)]
    computations: List[Computation]
    visualizations: Annotated[List[Visualization], Field(min_length=1)]
    intermediate_values: List[IntermediateValue]
    guided_explorations: Annotated[List[GuidedExploration], Field(min_length=2)]
    limitation: Limitation
    source: Source


__all__ = [
    "Computation",
    "ComputationOperation",
    "Control",
    "ControlType",
    "GuidedExploration",
    "IntermediateValue",
    "LessonIntro",
    "LessonMeta",
    "LessonRenderSpec",
    "Limitation",
    "Source",
    "SymbolDefinition",
    "Variable",
    "Visualization",
    "VisualizationType",
]
