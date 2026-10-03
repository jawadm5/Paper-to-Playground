"""Full-paper HTML renderer for validated LessonRenderSpec documents."""

import argparse
import json
from html import escape
from pathlib import Path
from string import Template
from typing import Any, Callable, Dict, Iterable, List, Tuple, Union

from src.schema import (
    Boundary,
    Control,
    Equation,
    InteractiveBlock,
    LessonRenderSpec,
    LessonSection,
)


TEMPLATE_PATH = Path(__file__).parent / "templates" / "base.html"
RUNTIME_PATH = Path(__file__).parent / "runtime" / "runtime.js"


def _escape(value: str) -> str:
    return escape(value, quote=True)


def _json_for_html(value: Any) -> str:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _numeric_attributes(control: Control) -> str:
    attributes = []
    for name in ("min", "max", "step"):
        value = getattr(control, name)
        if value is not None:
            attributes.append(f'{name}="{value}"')
    return " " + " ".join(attributes) if attributes else ""


def _require_number(control: Control, value: Any) -> Union[int, float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"Control '{control.id}' of type '{control.type}' requires a scalar variable"
        )
    return value


def _render_slider(control: Control, value: Any) -> str:
    numeric_value = _require_number(control, value)
    return """
      <article class="control-card lesson-control" data-control-id="{id}" data-control-type="slider" data-variable="{variable}">
        <div class="control-heading">
          <label for="{id}">{label}</label>
          <output id="{id}-value" for="{id}">{value}</output>
        </div>
        <input id="{id}" type="range" value="{value}"{attributes}>
      </article>
    """.format(
        id=_escape(control.id),
        variable=_escape(control.variable),
        label=_escape(control.label),
        value=numeric_value,
        attributes=_numeric_attributes(control),
    )


def _render_number_input(control: Control, value: Any) -> str:
    numeric_value = _require_number(control, value)
    step_attribute = "" if control.step is not None else ' step="any"'
    return """
      <article class="control-card lesson-control" data-control-id="{id}" data-control-type="number_input" data-variable="{variable}">
        <label for="{id}">{label}</label>
        <input id="{id}" type="number" value="{value}"{attributes}{step_attribute}>
      </article>
    """.format(
        id=_escape(control.id),
        variable=_escape(control.variable),
        label=_escape(control.label),
        value=numeric_value,
        attributes=_numeric_attributes(control),
        step_attribute=step_attribute,
    )


def _render_toggle(control: Control, value: Any) -> str:
    if not isinstance(value, bool):
        raise ValueError(
            f"Control '{control.id}' of type 'toggle' requires a boolean variable"
        )
    checked = " checked" if value else ""
    return """
      <article class="control-card lesson-control toggle-control" data-control-id="{id}" data-control-type="toggle" data-variable="{variable}">
        <label class="toggle-label" for="{id}">
          <span>{label}</span>
          <span class="toggle-switch">
            <input id="{id}" type="checkbox"{checked}>
            <span class="toggle-track" aria-hidden="true"></span>
          </span>
        </label>
      </article>
    """.format(
        id=_escape(control.id),
        variable=_escape(control.variable),
        label=_escape(control.label),
        checked=checked,
    )


def _render_matrix_editor(control: Control, value: Any) -> str:
    if not isinstance(value, list) or not all(isinstance(row, list) for row in value):
        raise ValueError(
            f"Control '{control.id}' of type 'matrix_editor' requires a matrix variable"
        )

    rows = []
    for row_index, row in enumerate(value):
        cells = []
        for column_index, cell_value in enumerate(row):
            cell_id = f"{control.id}-r{row_index}-c{column_index}"
            cell_label = (
                f"{control.label}, row {row_index + 1}, column {column_index + 1}"
            )
            cells.append(
                """
                <td>
                  <label class="visually-hidden" for="{cell_id}">{cell_label}</label>
                  <input id="{cell_id}" type="number" step="any" value="{value}" data-row="{row}" data-column="{column}">
                </td>
                """.format(
                    cell_id=_escape(cell_id),
                    cell_label=_escape(cell_label),
                    value=cell_value,
                    row=row_index,
                    column=column_index,
                )
            )
        rows.append(f"<tr>{''.join(cells)}</tr>")

    return """
      <article class="control-card lesson-control matrix-control" id="{id}" data-control-id="{id}" data-control-type="matrix_editor" data-variable="{variable}">
        <h4>{label}</h4>
        <div class="matrix-scroll">
          <table aria-label="{label}"><tbody>{rows}</tbody></table>
        </div>
      </article>
    """.format(
        id=_escape(control.id),
        variable=_escape(control.variable),
        label=_escape(control.label),
        rows="".join(rows),
    )


CONTROL_RENDERERS: Dict[str, Callable[[Control, Any], str]] = {
    "slider": _render_slider,
    "number_input": _render_number_input,
    "toggle": _render_toggle,
    "matrix_editor": _render_matrix_editor,
}


def _section_tree(
    sections: List[LessonSection],
) -> Tuple[List[Tuple[LessonSection, int]], Dict[Union[str, None], List[LessonSection]]]:
    children: Dict[Union[str, None], List[LessonSection]] = {None: []}
    for section in sections:
        children.setdefault(section.parent_id, []).append(section)
        children.setdefault(section.id, [])

    ordered: List[Tuple[LessonSection, int]] = []
    visiting = set()
    visited = set()

    def visit(section: LessonSection, depth: int) -> None:
        if section.id in visiting:
            raise ValueError(f"Section hierarchy contains a cycle at '{section.id}'")
        if section.id in visited:
            return
        visiting.add(section.id)
        ordered.append((section, depth))
        for child in children[section.id]:
            visit(child, depth + 1)
        visiting.remove(section.id)
        visited.add(section.id)

    for root in children[None]:
        visit(root, 0)

    if len(visited) != len(sections):
        remaining = next(section.id for section in sections if section.id not in visited)
        visit(next(section for section in sections if section.id == remaining), 0)
        raise ValueError(f"Section hierarchy contains a cycle at '{remaining}'")

    return ordered, children


def _render_learning_outcomes(spec: LessonRenderSpec) -> str:
    return "".join(
        """
        <li class="outcome-card">
          <span class="outcome-level">{level}</span>
          <p>{description}</p>
        </li>
        """.format(
            level=_escape(outcome.level),
            description=_escape(outcome.description),
        )
        for outcome in spec.learning_outcomes
    )


def _wrap_node_name(name: str, line_length: int = 24, max_lines: int = 3) -> List[str]:
    words = name.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > line_length:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(1, line_length - 1)].rstrip() + "…"
    return lines or [name]


def _render_mind_map(spec: LessonRenderSpec, anchors: Dict[str, str]) -> str:
    concepts = spec.mind_map.concepts
    relationships = spec.mind_map.relationships
    column_count = min(3, len(concepts))
    node_width = 250
    node_height = 88
    horizontal_gap = 72
    vertical_gap = 112
    margin_x = 62
    margin_y = 58
    row_count = (len(concepts) + column_count - 1) // column_count
    width = margin_x * 2 + column_count * node_width + (column_count - 1) * horizontal_gap
    height = margin_y * 2 + row_count * node_height + (row_count - 1) * vertical_gap

    positions: Dict[str, Tuple[float, float, int, int]] = {}
    nodes = []
    for index, concept in enumerate(concepts):
        row = index // column_count
        column = index % column_count
        concepts_in_row = min(column_count, len(concepts) - row * column_count)
        row_width = concepts_in_row * node_width + (concepts_in_row - 1) * horizontal_gap
        row_start = (width - row_width) / 2
        x = row_start + column * (node_width + horizontal_gap)
        y = margin_y + row * (node_height + vertical_gap)
        positions[concept.id] = (x, y, row, column)
        text_lines = _wrap_node_name(concept.name)
        line_start = y + node_height / 2 - (len(text_lines) - 1) * 10
        text = "".join(
            '<tspan x="{x}" y="{y}">{line}</tspan>'.format(
                x=x + node_width / 2,
                y=line_start + line_index * 20,
                line=_escape(line),
            )
            for line_index, line in enumerate(text_lines)
        )
        section_target = anchors.get(concept.section_id, "") if concept.section_id else ""
        navigation_label = (
            f"Open section for {concept.name}"
            if section_target
            else f"Show details for {concept.name}"
        )
        nodes.append(
            """
            <g class="mind-map-node" tabindex="0" role="button"
               aria-label="{navigation_label}" data-concept-id="{concept_id}"
               data-concept-name="{name}" data-concept-summary="{summary}"
               data-section-target="{section_target}">
              <rect x="{x}" y="{y}" width="{width}" height="{height}" rx="16"></rect>
              <text class="mind-map-node-label" text-anchor="middle">{text}</text>
            </g>
            """.format(
                navigation_label=_escape(navigation_label),
                concept_id=_escape(concept.id),
                name=_escape(concept.name),
                summary=_escape(concept.summary),
                section_target=section_target,
                x=x,
                y=y,
                width=node_width,
                height=node_height,
                text=text,
            )
        )

    edges = []
    for index, relationship in enumerate(relationships, start=1):
        source_x, source_y, source_row, source_column = positions[relationship.from_id]
        target_x, target_y, target_row, target_column = positions[relationship.to_id]
        if source_row == target_row:
            moving_right = target_column > source_column
            start_x = source_x + (node_width if moving_right else 0)
            start_y = source_y + node_height / 2
            end_x = target_x + (0 if moving_right else node_width)
            end_y = target_y + node_height / 2
            bend = 42 if moving_right else -42
            path = (
                f"M {start_x} {start_y} C {start_x + bend} {start_y - 46}, "
                f"{end_x - bend} {end_y - 46}, {end_x} {end_y}"
            )
            label_x = (start_x + end_x) / 2
            label_y = start_y - 49
        else:
            moving_down = target_y > source_y
            start_x = source_x + node_width / 2
            start_y = source_y + (node_height if moving_down else 0)
            end_x = target_x + node_width / 2
            end_y = target_y + (0 if moving_down else node_height)
            middle_y = (start_y + end_y) / 2
            path = (
                f"M {start_x} {start_y} C {start_x} {middle_y}, "
                f"{end_x} {middle_y}, {end_x} {end_y}"
            )
            label_x = (start_x + end_x) / 2
            label_y = middle_y - 7

        display_label = relationship.label
        if len(display_label) > 38:
            display_label = display_label[:37].rstrip() + "…"
        tooltip_parts = [relationship.label, f"Basis: {relationship.basis}"]
        if relationship.source_refs:
            tooltip_parts.append("Sources: " + ", ".join(relationship.source_refs))
        edges.append(
            """
            <g class="mind-map-edge">
              <title>{tooltip}</title>
              <path id="mind-map-edge-{index}" class="mind-map-edge-path" d="{path}" marker-end="url(#mind-map-arrow)"></path>
              <text class="mind-map-edge-label" x="{label_x}" y="{label_y}" text-anchor="middle">{label}</text>
            </g>
            """.format(
                tooltip=_escape(" · ".join(tooltip_parts)),
                index=index,
                path=path,
                label_x=label_x,
                label_y=label_y,
                label=_escape(display_label),
            )
        )

    return """
      <section class="mind-map-section" data-section="mind-map" aria-labelledby="mind-map-title">
        <div class="section-heading">
          <div>
            <p class="section-kicker">Concept graph</p>
            <h2 id="mind-map-title">How the ideas connect</h2>
          </div>
          <p>Select a concept to see its summary and move to its linked paper section.</p>
        </div>
        <div class="mind-map-shell">
          <div class="mind-map-canvas">
            <svg class="mind-map-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Concept relationship map">
              <defs>
                <marker id="mind-map-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z"></path>
                </marker>
              </defs>
              <g class="mind-map-edges">{edges}</g>
              <g class="mind-map-nodes">{nodes}</g>
            </svg>
          </div>
          <aside class="mind-map-details" id="mind-map-details" aria-live="polite">
            <span class="content-label">Selected concept</span>
            <h3 id="mind-map-detail-name">Select a concept</h3>
            <p id="mind-map-detail-summary">Choose any node in the map to inspect its summary.</p>
            <p id="mind-map-detail-note" class="mind-map-detail-note" hidden></p>
          </aside>
        </div>
      </section>
    """.format(
        width=width,
        height=height,
        edges="".join(edges),
        nodes="".join(nodes),
    )


def _render_navigation(
    children: Dict[Union[str, None], List[LessonSection]],
    anchors: Dict[str, str],
    parent_id: Union[str, None] = None,
    depth: int = 0,
) -> str:
    items = []
    for section in children[parent_id]:
        descendants = _render_navigation(children, anchors, section.id, depth + 1)
        items.append(
            """
            <li>
              <a href="#{anchor}"><span>{kind}</span>{title}</a>
              {descendants}
            </li>
            """.format(
                anchor=anchors[section.id],
                kind=_escape(section.kind),
                title=_escape(section.title),
                descendants=descendants,
            )
        )
    if not items:
        return ""
    class_name = "nav-list" if depth == 0 else "nav-children"
    return f'<ol class="{class_name}">{"".join(items)}</ol>'


def _render_source_refs(source_refs: Iterable[str]) -> str:
    refs = list(source_refs)
    if not refs:
        return '<span class="source-empty">Background / no direct source reference</span>'
    return "".join(f'<code class="source-ref">{_escape(ref)}</code>' for ref in refs)


def _render_equations(equations: Iterable[Equation]) -> str:
    cards = []
    for equation in equations:
        cards.append(
            """
            <article class="equation-card">
              <code class="equation-text">{latex}</code>
              <p>{explanation}</p>
              <div class="inline-sources">{sources}</div>
            </article>
            """.format(
                latex=_escape(equation.latex),
                explanation=_escape(equation.explanation),
                sources=_render_source_refs(equation.source_refs),
            )
        )
    return "".join(cards)


def _render_boundaries(boundaries: Iterable[Boundary]) -> str:
    cards = []
    for boundary in boundaries:
        cards.append(
            """
            <article class="boundary-card">
              <div class="boundary-heading">
                <span class="boundary-kind">{kind}</span>
                <span class="basis-label">{basis}</span>
              </div>
              <p>{description}</p>
              <div class="inline-sources">{sources}</div>
            </article>
            """.format(
                kind=_escape(boundary.kind),
                basis=_escape(boundary.basis),
                description=_escape(boundary.description),
                sources=_render_source_refs(boundary.source_refs),
            )
        )
    if not cards:
        return '<p class="empty-state">No boundaries were provided.</p>'
    return "".join(cards)


def _scope_reference(scope: str, reference: str) -> str:
    return f"{scope}.{reference}"


def _render_interactive_block(
    block: InteractiveBlock,
    scope: str,
    runtime_state: Dict[str, Any],
    runtime_computations: List[Dict[str, Any]],
    runtime_outputs: Dict[str, List[Dict[str, Any]]],
) -> str:
    local_values = {variable.id: variable.default for variable in block.variables}
    if len(local_values) != len(block.variables):
        raise ValueError(f"Interactive block '{block.id}' contains duplicate variable IDs")

    for variable_id, value in local_values.items():
        runtime_state[_scope_reference(scope, variable_id)] = value

    controls = []
    for index, control in enumerate(block.controls, start=1):
        if control.variable not in local_values:
            raise ValueError(
                f"Control '{control.id}' references unknown variable '{control.variable}' "
                f"in interactive block '{block.id}'"
            )
        scoped_control = control.model_copy(
            update={
                "id": f"{scope}__control_{index}",
                "variable": _scope_reference(scope, control.variable),
            }
        )
        controls.append(CONTROL_RENDERERS[control.type](scoped_control, local_values[control.variable]))

    for computation in block.computations:
        definition = computation.model_dump(mode="json", exclude_none=True)
        definition["id"] = _scope_reference(scope, computation.id)
        definition["inputs"] = [
            _scope_reference(scope, input_id) for input_id in computation.inputs
        ]
        if computation.condition is not None:
            definition["condition"] = _scope_reference(scope, computation.condition)
            definition["otherwise"] = _scope_reference(scope, computation.otherwise)
        runtime_computations.append(definition)

    available_data_ids = set(local_values)
    available_data_ids.update(computation.id for computation in block.computations)

    intermediate_values = []
    for index, intermediate in enumerate(block.intermediate_values, start=1):
        if intermediate.data not in available_data_ids:
            raise ValueError(
                f"Intermediate value '{intermediate.label}' in interactive block "
                f"'{block.id}' references missing data ID '{intermediate.data}'"
            )
        element_id = f"{scope}__intermediate_{index}"
        runtime_outputs["intermediate_values"].append(
            {
                "element_id": element_id,
                "data": _scope_reference(scope, intermediate.data),
                "label": intermediate.label,
            }
        )
        intermediate_values.append(
            """
            <article class="intermediate-card">
              <span>{label}</span>
              <div id="{element_id}" class="live-data" aria-live="polite"></div>
            </article>
            """.format(
                label=_escape(intermediate.label),
                element_id=element_id,
            )
        )

    visualizations = []
    for index, visualization in enumerate(block.visualizations, start=1):
        element_id = f"{scope}__visualization_{index}"
        if isinstance(visualization.data, list):
            missing_ids = [
                data_id
                for data_id in visualization.data
                if data_id not in available_data_ids
            ]
            if missing_ids:
                raise ValueError(
                    f"Visualization '{visualization.id}' in interactive block "
                    f"'{block.id}' references missing data ID '{missing_ids[0]}'"
                )
            scoped_data: Union[str, List[str]] = [
                _scope_reference(scope, data_id) for data_id in visualization.data
            ]
            default_labels = list(visualization.data)
        else:
            if visualization.data not in available_data_ids:
                raise ValueError(
                    f"Visualization '{visualization.id}' in interactive block "
                    f"'{block.id}' references missing data ID '{visualization.data}'"
                )
            scoped_data = _scope_reference(scope, visualization.data)
            default_labels = [visualization.data]
        labels = (
            list(visualization.labels)
            if visualization.labels is not None
            else default_labels
        )
        runtime_outputs["visualizations"].append(
            {
                "element_id": element_id,
                "type": visualization.type,
                "data": scoped_data,
                "labels": labels,
            }
        )
        visualizations.append(
            """
            <article class="visualization-card" data-visualization-id="{visualization_id}" data-visualization-type="{visualization_type}">
              <h4>{title}</h4>
              <div id="{element_id}" class="visualization-body" aria-live="polite"></div>
            </article>
            """.format(
                visualization_id=_escape(visualization.id),
                visualization_type=visualization.type,
                title=_escape(visualization.title),
                element_id=element_id,
            )
        )

    guided_explorations = "".join(
        """
        <article class="guided-card">
          <h4>{title}</h4>
          <p><strong>Try:</strong> {instruction}</p>
          <p><strong>Observe:</strong> {observe}</p>
          <p><strong>Why:</strong> {explanation}</p>
        </article>
        """.format(
            title=_escape(exploration.title),
            instruction=_escape(exploration.instruction),
            observe=_escape(exploration.observe),
            explanation=_escape(exploration.explanation),
        )
        for exploration in block.guided_explorations
    )

    return """
      <section class="interactive-block" data-interactive-block-id="{block_id}">
        <div class="interactive-heading">
          <span class="content-label">Interactive block</span>
          <h3>{title}</h3>
          <p>Change the inputs to recompute this block's data context.</p>
        </div>
        <div class="control-grid">{controls}</div>
        <div class="block-output-section">
          <h4>Intermediate values</h4>
          <div class="intermediate-grid">{intermediate_values}</div>
        </div>
        <div class="block-output-section">
          <h4>Visual explanations</h4>
          <div class="visualization-grid">{visualizations}</div>
        </div>
        <div class="guided-grid">{guided_explorations}</div>
      </section>
    """.format(
        block_id=_escape(block.id),
        title=_escape(block.title),
        controls="".join(controls),
        intermediate_values="".join(intermediate_values),
        visualizations="".join(visualizations),
        guided_explorations=guided_explorations,
    )


def _render_section(
    section: LessonSection,
    depth: int,
    anchor: str,
    section_number: int,
    runtime_state: Dict[str, Any],
    runtime_computations: List[Dict[str, Any]],
    runtime_outputs: Dict[str, List[Dict[str, Any]]],
) -> str:
    intuition = ""
    if section.intuition is not None:
        intuition = """
          <aside class="intuition-card">
            <span class="content-label">Intuition · {basis}</span>
            <p>{explanation}</p>
            <div class="inline-sources">{sources}</div>
          </aside>
        """.format(
            basis=_escape(section.intuition.basis),
            explanation=_escape(section.intuition.explanation),
            sources=_render_source_refs(section.intuition.source_refs),
        )

    equations = ""
    if section.equations:
        equations = """
          <div class="section-subgroup">
            <h3>Key equations</h3>
            <div class="equation-grid">{cards}</div>
          </div>
        """.format(cards=_render_equations(section.equations))

    interactive_blocks = ""
    if section.interactive_blocks:
        interactive_blocks = "".join(
            _render_interactive_block(
                block,
                f"block_{section_number}_{block_index}",
                runtime_state,
                runtime_computations,
                runtime_outputs,
            )
            for block_index, block in enumerate(section.interactive_blocks, start=1)
        )

    parent_attribute = (
        f' data-parent-id="{_escape(section.parent_id)}"'
        if section.parent_id is not None
        else ""
    )
    return """
      <article class="paper-section depth-{depth}" id="{anchor}" data-section-id="{section_id}"{parent_attribute}>
        <header class="paper-section-header">
          <div class="section-number">{number:02d}</div>
          <div>
            <span class="section-kind">{kind}</span>
            <h2>{title}</h2>
          </div>
        </header>

        <div class="explanation-grid">
          <section class="explanation-card paper-voice">
            <span class="content-label">From the paper</span>
            <p>{paper_explanation}</p>
          </section>
          <section class="explanation-card simple-voice">
            <span class="content-label">In plain language</span>
            <p>{simple_explanation}</p>
          </section>
        </div>

        {intuition}
        {equations}
        {interactive_blocks}

        <div class="section-subgroup">
          <h3>Boundaries &amp; assumptions</h3>
          <div class="boundary-grid">{boundaries}</div>
        </div>

        <footer class="section-sources">
          <span>Section sources</span>
          <div>{sources}</div>
        </footer>
      </article>
    """.format(
        depth=min(depth, 3),
        anchor=anchor,
        section_id=_escape(section.id),
        parent_attribute=parent_attribute,
        number=section_number,
        kind=_escape(section.kind),
        title=_escape(section.title),
        paper_explanation=_escape(section.paper_explanation),
        simple_explanation=_escape(section.simple_explanation),
        intuition=intuition,
        equations=equations,
        interactive_blocks=interactive_blocks,
        boundaries=_render_boundaries(section.boundaries),
        sources=_render_source_refs(section.source_refs),
    )


def render_to_html(spec: LessonRenderSpec) -> str:
    """Render a complete validated paper lesson into one self-contained page."""

    if not isinstance(spec, LessonRenderSpec):
        raise TypeError("render_to_html expects a validated LessonRenderSpec")

    ordered_sections, children = _section_tree(spec.sections)
    anchors = {
        section.id: f"section-{index}"
        for index, (section, _) in enumerate(ordered_sections, start=1)
    }
    runtime_state: Dict[str, Any] = {}
    runtime_computations: List[Dict[str, Any]] = []
    runtime_outputs: Dict[str, List[Dict[str, Any]]] = {
        "intermediate_values": [],
        "visualizations": [],
    }
    rendered_sections = "".join(
        _render_section(
            section,
            depth,
            anchors[section.id],
            index,
            runtime_state,
            runtime_computations,
            runtime_outputs,
        )
        for index, (section, depth) in enumerate(ordered_sections, start=1)
    )

    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    return template.substitute(
        document_title=_escape(spec.meta.title),
        title=_escape(spec.meta.title),
        subtitle=_escape(spec.meta.subtitle),
        outcome_count=len(spec.learning_outcomes),
        section_count=len(spec.sections),
        learning_outcomes=_render_learning_outcomes(spec),
        mind_map=_render_mind_map(spec, anchors),
        navigation=_render_navigation(children, anchors),
        sections=rendered_sections,
        initial_state=_json_for_html(runtime_state),
        computations=_json_for_html(runtime_computations),
        outputs=_json_for_html(runtime_outputs),
        runtime_javascript=RUNTIME_PATH.read_text(encoding="utf-8"),
    )


def write_html(spec: LessonRenderSpec, output_path: Union[str, Path]) -> None:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_to_html(spec), encoding="utf-8")


def _load_spec(input_path: Union[str, Path]) -> LessonRenderSpec:
    try:
        payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not load render specification: {exc}") from exc
    return LessonRenderSpec.model_validate(payload)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render a complete LessonRenderSpec JSON file to HTML."
    )
    parser.add_argument("input_path", help="Path to a LessonRenderSpec JSON file")
    parser.add_argument("output_path", help="Destination path for the HTML file")
    args = parser.parse_args()
    write_html(_load_spec(args.input_path), args.output_path)


if __name__ == "__main__":
    main()
