"""Strict Pydantic contracts for complete paper lessons and interactive blocks."""

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
    model_validator,
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
    """Base model shared by every public contract model."""

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)


class LessonMeta(StrictModel):
    title: NonEmptyString
    subtitle: NonEmptyString


class LearningOutcome(StrictModel):
    id: NonEmptyString
    level: NonEmptyString
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
    condition: Optional[NonEmptyString] = None
    otherwise: Optional[NonEmptyString] = None

    @model_validator(mode="after")
    def conditional_fields_must_be_paired(self) -> "Computation":
        if (self.condition is None) != (self.otherwise is None):
            raise ValueError(
                "condition and otherwise must either both be provided or both be omitted"
            )
        return self


class Visualization(StrictModel):
    id: NonEmptyString
    type: VisualizationType
    data: Union[NonEmptyString, NonEmptyIdList]
    title: NonEmptyString
    labels: Optional[List[NonEmptyString]] = None


class IntermediateValue(StrictModel):
    label: NonEmptyString
    data: NonEmptyString


class GuidedExploration(StrictModel):
    title: NonEmptyString
    instruction: NonEmptyString
    observe: NonEmptyString
    explanation: NonEmptyString


class InteractiveBlock(StrictModel):
    """Reusable Stage 4 interaction contract nested within a paper section."""

    id: NonEmptyString
    title: NonEmptyString
    variables: List[Variable]
    controls: Annotated[List[Control], Field(min_length=2)]
    computations: List[Computation]
    visualizations: Annotated[List[Visualization], Field(min_length=1)]
    intermediate_values: List[IntermediateValue]
    guided_explorations: Annotated[List[GuidedExploration], Field(min_length=2)]


class Intuition(StrictModel):
    explanation: NonEmptyString
    basis: NonEmptyString
    source_refs: List[NonEmptyString]


class Equation(StrictModel):
    id: NonEmptyString
    latex: NonEmptyString
    explanation: NonEmptyString
    variable_ids: List[NonEmptyString]
    basis: NonEmptyString
    source_refs: List[NonEmptyString]


class Boundary(StrictModel):
    kind: NonEmptyString
    description: NonEmptyString
    basis: NonEmptyString
    source_refs: List[NonEmptyString]


class LessonSection(StrictModel):
    id: NonEmptyString
    title: NonEmptyString
    kind: NonEmptyString
    parent_id: Optional[NonEmptyString]
    paper_explanation: NonEmptyString
    simple_explanation: NonEmptyString
    intuition: Optional[Intuition] = None
    equations: Optional[Annotated[List[Equation], Field(min_length=1)]] = None
    interactive_blocks: Optional[
        Annotated[List[InteractiveBlock], Field(min_length=1)]
    ] = None
    boundaries: List[Boundary]
    source_refs: List[NonEmptyString]


class MindMapConcept(StrictModel):
    id: NonEmptyString
    name: NonEmptyString
    summary: NonEmptyString
    section_id: Optional[NonEmptyString]


class MindMapRelationship(StrictModel):
    from_id: NonEmptyString = Field(alias="from")
    to_id: NonEmptyString = Field(alias="to")
    label: NonEmptyString
    basis: NonEmptyString
    source_refs: List[NonEmptyString]


class MindMap(StrictModel):
    concepts: Annotated[List[MindMapConcept], Field(min_length=1)]
    relationships: List[MindMapRelationship]


class MultipleChoiceAssessmentItem(StrictModel):
    id: NonEmptyString
    learning_outcome_id: NonEmptyString
    type: Literal["multiple_choice"]
    question: NonEmptyString
    options: Annotated[List[NonEmptyString], Field(min_length=2)]
    correct_answer: NonEmptyString
    explanation: NonEmptyString

    @model_validator(mode="after")
    def correct_answer_must_be_an_option(self) -> "MultipleChoiceAssessmentItem":
        if len(set(self.options)) != len(self.options):
            raise ValueError("multiple-choice options must be unique")
        if self.correct_answer not in self.options:
            raise ValueError("multiple-choice correct_answer must match one option")
        return self


class NumericAssessmentItem(StrictModel):
    id: NonEmptyString
    learning_outcome_id: NonEmptyString
    type: Literal["numeric"]
    question: NonEmptyString
    correct_answer: Number
    explanation: NonEmptyString
    tolerance: Number = 1e-6

    @field_validator("tolerance")
    @classmethod
    def tolerance_must_be_non_negative(cls, value: Number) -> Number:
        if value < 0:
            raise ValueError("numeric assessment tolerance must be non-negative")
        return value


class ShortAnswerAssessmentItem(StrictModel):
    id: NonEmptyString
    learning_outcome_id: NonEmptyString
    type: Literal["short_answer"]
    question: NonEmptyString
    correct_answer: NonEmptyString
    explanation: NonEmptyString


AssessmentItem = Annotated[
    Union[
        MultipleChoiceAssessmentItem,
        NumericAssessmentItem,
        ShortAnswerAssessmentItem,
    ],
    Field(discriminator="type"),
]


class LessonRenderSpec(StrictModel):
    """Complete learning-document contract derived from Call 1 output."""

    meta: LessonMeta
    learning_outcomes: Annotated[List[LearningOutcome], Field(min_length=1)]
    sections: Annotated[List[LessonSection], Field(min_length=1)]
    mind_map: MindMap
    assessment: Annotated[List[AssessmentItem], Field(min_length=1)]

    @model_validator(mode="after")
    def references_must_resolve(self) -> "LessonRenderSpec":
        outcome_ids = [outcome.id for outcome in self.learning_outcomes]
        section_ids = [section.id for section in self.sections]
        concept_ids = [concept.id for concept in self.mind_map.concepts]
        assessment_ids = [item.id for item in self.assessment]

        self._require_unique(outcome_ids, "learning outcome")
        self._require_unique(section_ids, "section")
        self._require_unique(concept_ids, "mind-map concept")
        self._require_unique(assessment_ids, "assessment item")

        section_id_set = set(section_ids)
        for section in self.sections:
            if section.parent_id is not None and section.parent_id not in section_id_set:
                raise ValueError(
                    f"Section '{section.id}' references missing parent section "
                    f"'{section.parent_id}'"
                )
            if section.parent_id == section.id:
                raise ValueError(f"Section '{section.id}' cannot be its own parent")

        for concept in self.mind_map.concepts:
            if concept.section_id is not None and concept.section_id not in section_id_set:
                raise ValueError(
                    f"Mind-map concept '{concept.id}' references missing section "
                    f"'{concept.section_id}'"
                )

        concept_id_set = set(concept_ids)
        for relationship in self.mind_map.relationships:
            if relationship.from_id not in concept_id_set:
                raise ValueError(
                    f"Mind-map relationship references missing concept "
                    f"'{relationship.from_id}'"
                )
            if relationship.to_id not in concept_id_set:
                raise ValueError(
                    f"Mind-map relationship references missing concept "
                    f"'{relationship.to_id}'"
                )

        outcome_id_set = set(outcome_ids)
        for item in self.assessment:
            if item.learning_outcome_id not in outcome_id_set:
                raise ValueError(
                    f"Assessment item '{item.id}' references missing learning outcome "
                    f"'{item.learning_outcome_id}'"
                )
        return self

    @staticmethod
    def _require_unique(ids: List[str], label: str) -> None:
        seen = set()
        for item_id in ids:
            if item_id in seen:
                raise ValueError(f"Duplicate {label} id '{item_id}'")
            seen.add(item_id)


# Temporary compatibility model for the already-approved Stage 4 renderer. The
# new full-paper renderer will consume LessonRenderSpec in a later stage.
class LessonIntro(StrictModel):
    why_it_matters: NonEmptyString
    overview: NonEmptyString


class SymbolDefinition(StrictModel):
    symbol: NonEmptyString
    label: NonEmptyString
    description: NonEmptyString


class Limitation(StrictModel):
    text: NonEmptyString


class Source(StrictModel):
    paper: NonEmptyString
    section: NonEmptyString
    url: NonEmptyString


class LegacyLessonRenderSpec(StrictModel):
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
    "AssessmentItem",
    "Boundary",
    "Computation",
    "ComputationOperation",
    "Control",
    "ControlType",
    "Equation",
    "GuidedExploration",
    "InteractiveBlock",
    "IntermediateValue",
    "Intuition",
    "LearningOutcome",
    "LegacyLessonRenderSpec",
    "LessonMeta",
    "LessonRenderSpec",
    "LessonSection",
    "MindMap",
    "MindMapConcept",
    "MindMapRelationship",
    "MultipleChoiceAssessmentItem",
    "NumericAssessmentItem",
    "ShortAnswerAssessmentItem",
    "Variable",
    "Visualization",
    "VisualizationType",
]
