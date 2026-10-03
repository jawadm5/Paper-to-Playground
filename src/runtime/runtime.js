(function () {
  "use strict";

  function readEmbeddedJson(elementId) {
    const element = document.getElementById(elementId);
    if (!element) {
      throw new Error("Missing embedded data element '" + elementId + "'");
    }
    try {
      return JSON.parse(element.textContent);
    } catch (error) {
      throw new Error("Invalid JSON in embedded data element '" + elementId + "'");
    }
  }

  function isFiniteNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
  }

  function shapeOf(value, label) {
    if (isFiniteNumber(value)) {
      return [];
    }
    if (!Array.isArray(value) || value.length === 0) {
      throw new Error(label + " must be a finite number or a non-empty numeric array");
    }
    if (value.every(isFiniteNumber)) {
      return [value.length];
    }
    if (!value.every(Array.isArray)) {
      throw new Error(label + " contains mixed or invalid numeric values");
    }

    const width = value[0].length;
    if (width === 0) {
      throw new Error(label + " contains an empty matrix row");
    }
    value.forEach(function (row) {
      if (row.length !== width) {
        throw new Error(label + " must be a rectangular matrix");
      }
      if (!row.every(isFiniteNumber)) {
        throw new Error(label + " contains an invalid numeric value");
      }
    });
    return [value.length, width];
  }

  function sameShape(leftShape, rightShape) {
    return leftShape.length === rightShape.length && leftShape.every(function (size, index) {
      return size === rightShape[index];
    });
  }

  function mapNumeric(value, transform) {
    if (isFiniteNumber(value)) {
      return transform(value);
    }
    return value.map(function (item) {
      return mapNumeric(item, transform);
    });
  }

  function binaryElementwise(left, right, transform, operationName) {
    const leftShape = shapeOf(left, operationName + " left input");
    const rightShape = shapeOf(right, operationName + " right input");

    if (leftShape.length === 0 && rightShape.length === 0) {
      return transform(left, right);
    }
    if (leftShape.length === 0) {
      return mapNumeric(right, function (value) {
        return transform(left, value);
      });
    }
    if (rightShape.length === 0) {
      return mapNumeric(left, function (value) {
        return transform(value, right);
      });
    }
    if (!sameShape(leftShape, rightShape)) {
      throw new Error(
        operationName + " dimension mismatch: [" + leftShape + "] versus [" + rightShape + "]"
      );
    }
    return left.map(function (value, index) {
      return binaryElementwise(value, right[index], transform, operationName);
    });
  }

  function add(left, right) {
    return binaryElementwise(left, right, function (a, b) {
      return a + b;
    }, "add");
  }

  function subtract(left, right) {
    return binaryElementwise(left, right, function (a, b) {
      return a - b;
    }, "subtract");
  }

  function multiply(left, right) {
    return binaryElementwise(left, right, function (a, b) {
      return a * b;
    }, "multiply");
  }

  function divide(left, right) {
    return binaryElementwise(left, right, function (a, b) {
      if (b === 0) {
        throw new Error("divide cannot use a zero divisor");
      }
      return a / b;
    }, "divide");
  }

  function squareRoot(value) {
    shapeOf(value, "sqrt input");
    return mapNumeric(value, function (item) {
      if (item < 0) {
        throw new Error("sqrt cannot use a negative input");
      }
      return Math.sqrt(item);
    });
  }

  function sum(value) {
    shapeOf(value, "sum input");
    if (isFiniteNumber(value)) {
      return value;
    }
    return value.reduce(function (total, item) {
      return total + sum(item);
    }, 0);
  }

  function normalize(value) {
    shapeOf(value, "normalize input");
    const total = sum(value);
    if (total === 0) {
      throw new Error("normalize cannot use values that sum to zero");
    }
    return mapNumeric(value, function (item) {
      return item / total;
    });
  }

  function softmax(vector) {
    const shape = shapeOf(vector, "softmax input");
    if (shape.length !== 1) {
      throw new Error("softmax requires a vector");
    }
    const maximum = Math.max.apply(null, vector);
    const exponentials = vector.map(function (value) {
      return Math.exp(value - maximum);
    });
    const total = exponentials.reduce(function (result, value) {
      return result + value;
    }, 0);
    return exponentials.map(function (value) {
      return value / total;
    });
  }

  function rowSoftmax(matrix) {
    const shape = shapeOf(matrix, "row_softmax input");
    if (shape.length !== 2) {
      throw new Error("row_softmax requires a matrix");
    }
    return matrix.map(softmax);
  }

  function transpose(matrix) {
    const shape = shapeOf(matrix, "transpose input");
    if (shape.length !== 2) {
      throw new Error("transpose requires a matrix");
    }
    return Array.from({ length: shape[1] }, function (_, column) {
      return matrix.map(function (row) {
        return row[column];
      });
    });
  }

  function matrixMultiply(left, right) {
    const leftShape = shapeOf(left, "matrix_multiply left input");
    const rightShape = shapeOf(right, "matrix_multiply right input");
    if (leftShape.length !== 2 || rightShape.length !== 2) {
      throw new Error("matrix_multiply requires two matrices");
    }
    if (leftShape[1] !== rightShape[0]) {
      throw new Error(
        "matrix_multiply dimension mismatch: [" + leftShape + "] cannot multiply [" + rightShape + "]"
      );
    }

    return left.map(function (leftRow) {
      return Array.from({ length: rightShape[1] }, function (_, column) {
        return leftRow.reduce(function (total, value, index) {
          return total + value * right[index][column];
        }, 0);
      });
    });
  }

  function matmulTranspose(left, right) {
    const leftShape = shapeOf(left, "matmul_transpose left input");
    const rightShape = shapeOf(right, "matmul_transpose right input");
    if (leftShape.length !== 2 || rightShape.length !== 2) {
      throw new Error("matmul_transpose requires two matrices");
    }
    if (leftShape[1] !== rightShape[1]) {
      throw new Error(
        "matmul_transpose dimension mismatch: [" + leftShape + "] cannot multiply the transpose of [" + rightShape + "]"
      );
    }
    return left.map(function (leftRow) {
      return right.map(function (rightRow) {
        return leftRow.reduce(function (total, value, index) {
          return total + value * rightRow[index];
        }, 0);
      });
    });
  }

  const operationRegistry = Object.freeze({
    add: add,
    subtract: subtract,
    multiply: multiply,
    divide: divide,
    sqrt: squareRoot,
    sum: sum,
    normalize: normalize,
    softmax: softmax,
    row_softmax: rowSoftmax,
    transpose: transpose,
    matrix_multiply: matrixMultiply,
    matmul_transpose: matmulTranspose,
  });

  const operationArity = Object.freeze({
    add: 2,
    subtract: 2,
    multiply: 2,
    divide: 2,
    sqrt: 1,
    sum: 1,
    normalize: 1,
    softmax: 1,
    row_softmax: 1,
    transpose: 1,
    matrix_multiply: 2,
    matmul_transpose: 2,
  });

  const dataContext = readEmbeddedJson("lesson-initial-state");
  const computationDefinitions = readEmbeddedJson("lesson-computations");
  const outputDefinitions = readEmbeddedJson("lesson-outputs");
  const variableIds = new Set(Object.keys(dataContext));
  const computationIds = [];
  const knownComputationIds = new Set();

  computationDefinitions.forEach(function (definition) {
    if (variableIds.has(definition.id)) {
      throw new Error("Computation id '" + definition.id + "' conflicts with a variable id");
    }
    if (knownComputationIds.has(definition.id)) {
      throw new Error("Duplicate computation id '" + definition.id + "'");
    }
    knownComputationIds.add(definition.id);
    computationIds.push(definition.id);
  });

  function resolveId(id, computationId) {
    if (!Object.prototype.hasOwnProperty.call(dataContext, id)) {
      throw new Error("Computation '" + computationId + "' references missing ID '" + id + "'");
    }
    return dataContext[id];
  }

  function executeComputation(definition) {
    if (definition.condition !== undefined) {
      const condition = resolveId(definition.condition, definition.id);
      if (typeof condition !== "boolean") {
        throw new Error("Computation '" + definition.id + "' condition must resolve to a boolean");
      }
      if (!condition) {
        return resolveId(definition.otherwise, definition.id);
      }
    }

    const operation = operationRegistry[definition.op];
    if (!operation) {
      throw new Error("Computation '" + definition.id + "' uses unsupported operation '" + definition.op + "'");
    }
    if (!Array.isArray(definition.inputs) || definition.inputs.length !== operationArity[definition.op]) {
      throw new Error(
        "Computation '" + definition.id + "' operation '" + definition.op + "' expects " +
        operationArity[definition.op] + " input(s)"
      );
    }
    const inputs = definition.inputs.map(function (inputId) {
      return resolveId(inputId, definition.id);
    });
    return operation.apply(null, inputs);
  }

  function recompute() {
    computationIds.forEach(function (id) {
      delete dataContext[id];
    });
    computationDefinitions.forEach(function (definition) {
      dataContext[definition.id] = executeComputation(definition);
    });
    return dataContext;
  }

  function readNumericInput(input, variableId) {
    if (input.value.trim() === "") {
      throw new Error("Control for '" + variableId + "' requires a numeric value");
    }
    const value = Number(input.value);
    if (!Number.isFinite(value)) {
      throw new Error("Control for '" + variableId + "' requires a finite number");
    }
    dataContext[variableId] = value;
  }

  function readToggle(input, variableId) {
    dataContext[variableId] = input.checked;
  }

  function readMatrixCell(input, variableId) {
    const row = Number(input.dataset.row);
    const column = Number(input.dataset.column);
    if (input.value.trim() === "") {
      throw new Error("Matrix control for '" + variableId + "' requires a numeric value");
    }
    const value = Number(input.value);
    if (!Number.isInteger(row) || !Number.isInteger(column) || !Number.isFinite(value)) {
      throw new Error("Matrix control for '" + variableId + "' received an invalid numeric value");
    }
    dataContext[variableId][row][column] = value;
  }

  const controlReaders = Object.freeze({
    slider: readNumericInput,
    number_input: readNumericInput,
    toggle: readToggle,
    matrix_editor: readMatrixCell,
  });

  function resolveOutputId(id, consumer) {
    if (!Object.prototype.hasOwnProperty.call(dataContext, id)) {
      throw new Error(consumer + " references missing ID '" + id + "'");
    }
    return dataContext[id];
  }

  function formatNumber(value) {
    if (!isFiniteNumber(value)) {
      throw new Error("Cannot display an invalid numeric value");
    }
    if (value === 0 || Number.isInteger(value)) {
      return String(value);
    }
    if (Math.abs(value) >= 10000 || Math.abs(value) < 0.0001) {
      return value.toExponential(3);
    }
    return String(Number(value.toFixed(4)));
  }

  function asMatrix(value, consumer) {
    const shape = shapeOf(value, consumer);
    if (shape.length === 0) {
      return [[value]];
    }
    if (shape.length === 1) {
      return [value];
    }
    if (shape.length === 2) {
      return value;
    }
    throw new Error(consumer + " supports only scalars, vectors, or matrices");
  }

  function clearElement(element) {
    while (element.firstChild) {
      element.removeChild(element.firstChild);
    }
  }

  function appendDataTable(element, value, className, heatmap) {
    const matrix = asMatrix(value, className);
    const flatValues = matrix.reduce(function (values, row) {
      return values.concat(row);
    }, []);
    const minimum = Math.min.apply(null, flatValues);
    const maximum = Math.max.apply(null, flatValues);
    const range = maximum - minimum;
    const table = document.createElement("table");
    table.className = className;
    const body = document.createElement("tbody");

    matrix.forEach(function (row) {
      const tableRow = document.createElement("tr");
      row.forEach(function (valueItem) {
        const cell = document.createElement("td");
        cell.textContent = formatNumber(valueItem);
        if (heatmap) {
          const ratio = range === 0 ? 0.5 : (valueItem - minimum) / range;
          cell.style.backgroundColor = "rgba(53, 88, 212, " + (0.14 + ratio * 0.76) + ")";
          cell.style.color = ratio > 0.56 ? "#ffffff" : "#172033";
        }
        tableRow.appendChild(cell);
      });
      body.appendChild(tableRow);
    });
    table.appendChild(body);
    element.appendChild(table);
  }

  function numericSeries(value, consumer) {
    const shape = shapeOf(value, consumer);
    if (shape.length !== 1) {
      throw new Error(consumer + " requires a numeric vector");
    }
    return value;
  }

  function createSvgElement(name) {
    return document.createElementNS("http://www.w3.org/2000/svg", name);
  }

  function setSvgAttributes(element, attributes) {
    Object.keys(attributes).forEach(function (name) {
      element.setAttribute(name, String(attributes[name]));
    });
  }

  function chartScale(values, height, padding) {
    let minimum = Math.min.apply(null, values);
    let maximum = Math.max.apply(null, values);
    if (minimum === maximum) {
      minimum -= 1;
      maximum += 1;
    }
    return {
      minimum: minimum,
      maximum: maximum,
      y: function (value) {
        return padding + (maximum - value) * (height - padding * 2) / (maximum - minimum);
      },
    };
  }

  function baseChart(values) {
    const width = 600;
    const height = 240;
    const padding = 34;
    const svg = createSvgElement("svg");
    setSvgAttributes(svg, {
      viewBox: "0 0 " + width + " " + height,
      role: "img",
      "aria-label": "Data chart",
      class: "chart-svg",
    });
    return { svg: svg, width: width, height: height, padding: padding, scale: chartScale(values, height, padding) };
  }

  function renderMatrixDisplay(element, values) {
    appendDataTable(element, values[0], "data-table", false);
  }

  function renderHeatmap(element, values) {
    appendDataTable(element, values[0], "heatmap-table", true);
  }

  function chartLabels(definition, length) {
    if (!Array.isArray(definition.labels) || definition.labels.length === 0) {
      return Array.from({ length: length }, function (_, index) {
        return String(index + 1);
      });
    }
    if (definition.labels.length !== length) {
      throw new Error(
        "Visualization '" + definition.element_id + "' has " + definition.labels.length +
        " labels for " + length + " values"
      );
    }
    return definition.labels;
  }

  function renderBarChart(element, values, definition) {
    const series = numericSeries(values[0], "bar_chart");
    const labels = chartLabels(definition, series.length);
    const chart = baseChart(series.concat([0]));
    const baseline = chart.scale.y(0);
    const slotWidth = (chart.width - chart.padding * 2) / series.length;
    const axis = createSvgElement("line");
    setSvgAttributes(axis, {
      x1: chart.padding,
      x2: chart.width - chart.padding,
      y1: baseline,
      y2: baseline,
      class: "chart-axis",
    });
    chart.svg.appendChild(axis);

    series.forEach(function (value, index) {
      const valueY = chart.scale.y(value);
      const bar = createSvgElement("rect");
      setSvgAttributes(bar, {
        x: chart.padding + index * slotWidth + slotWidth * 0.16,
        y: Math.min(valueY, baseline),
        width: slotWidth * 0.68,
        height: Math.max(1, Math.abs(baseline - valueY)),
        rx: 4,
        class: "chart-bar",
      });
      const label = createSvgElement("text");
      setSvgAttributes(label, {
        x: chart.padding + index * slotWidth + slotWidth / 2,
        y: chart.height - 8,
        "text-anchor": "middle",
        class: "chart-label",
      });
      label.textContent = labels[index];
      const title = createSvgElement("title");
      title.textContent = labels[index] + ": " + formatNumber(value);
      bar.appendChild(title);
      chart.svg.appendChild(bar);
      chart.svg.appendChild(label);
    });
    element.appendChild(chart.svg);
  }

  function renderLineChart(element, values, definition) {
    const series = numericSeries(values[0], "line_chart");
    const labels = chartLabels(definition, series.length);
    const chart = baseChart(series);
    const usableWidth = chart.width - chart.padding * 2;
    const xAt = function (index) {
      return series.length === 1
        ? chart.width / 2
        : chart.padding + index * usableWidth / (series.length - 1);
    };
    const points = series.map(function (value, index) {
      return xAt(index) + "," + chart.scale.y(value);
    }).join(" ");
    const polyline = createSvgElement("polyline");
    setSvgAttributes(polyline, { points: points, class: "chart-line" });
    chart.svg.appendChild(polyline);
    series.forEach(function (value, index) {
      const point = createSvgElement("circle");
      setSvgAttributes(point, {
        cx: xAt(index),
        cy: chart.scale.y(value),
        r: 4,
        class: "chart-point",
      });
      const title = createSvgElement("title");
      title.textContent = labels[index] + ": " + formatNumber(value);
      point.appendChild(title);
      chart.svg.appendChild(point);
    });
    element.appendChild(chart.svg);
  }

  function summarizeValue(value) {
    if (isFiniteNumber(value)) {
      return formatNumber(value);
    }
    const shape = shapeOf(value, "step_pipeline value");
    if (shape.length === 1 && shape[0] <= 4) {
      return "[" + value.map(formatNumber).join(", ") + "]";
    }
    return shape.join(" × ");
  }

  function renderStepPipeline(element, values, definition) {
    if (definition.labels.length !== values.length) {
      throw new Error(
        "Visualization '" + definition.element_id + "' must provide one label per pipeline stage"
      );
    }
    const pipeline = document.createElement("div");
    pipeline.className = "pipeline";
    values.forEach(function (value, index) {
      if (index > 0) {
        const arrow = document.createElement("div");
        arrow.className = "pipeline-arrow";
        arrow.setAttribute("aria-hidden", "true");
        arrow.textContent = "→";
        pipeline.appendChild(arrow);
      }
      const step = document.createElement("div");
      step.className = "pipeline-step";
      const label = document.createElement("span");
      label.textContent = definition.labels[index] || "Step " + (index + 1);
      const summary = document.createElement("code");
      summary.textContent = summarizeValue(value);
      step.appendChild(label);
      step.appendChild(summary);
      pipeline.appendChild(step);
    });
    element.appendChild(pipeline);
  }

  const visualizationRegistry = Object.freeze({
    bar_chart: renderBarChart,
    line_chart: renderLineChart,
    heatmap: renderHeatmap,
    matrix_display: renderMatrixDisplay,
    step_pipeline: renderStepPipeline,
  });

  function visualizationValues(definition) {
    const ids = Array.isArray(definition.data) ? definition.data : [definition.data];
    const resolvedValues = ids.map(function (id) {
      return resolveOutputId(id, "Visualization '" + definition.element_id + "'");
    });
    if ((definition.type === "bar_chart" || definition.type === "line_chart") && ids.length > 1) {
      if (!resolvedValues.every(isFiniteNumber)) {
        throw new Error(
          "Visualization '" + definition.element_id + "' requires scalar IDs when multiple data IDs are used"
        );
      }
      return [resolvedValues];
    }
    if (definition.type !== "step_pipeline" && ids.length !== 1) {
      throw new Error("Visualization '" + definition.element_id + "' requires one data ID");
    }
    return resolvedValues;
  }

  function renderIntermediateValues() {
    outputDefinitions.intermediate_values.forEach(function (definition) {
      const element = document.getElementById(definition.element_id);
      if (!element) {
        throw new Error("Missing intermediate value element '" + definition.element_id + "'");
      }
      clearElement(element);
      const value = resolveOutputId(
        definition.data,
        "Intermediate value '" + definition.label + "'"
      );
      appendDataTable(element, value, "data-table", false);
    });
  }

  function renderVisualizations() {
    outputDefinitions.visualizations.forEach(function (definition) {
      const renderer = visualizationRegistry[definition.type];
      if (!renderer) {
        throw new Error("Unsupported visualization type '" + definition.type + "'");
      }
      const element = document.getElementById(definition.element_id);
      if (!element) {
        throw new Error("Missing visualization element '" + definition.element_id + "'");
      }
      clearElement(element);
      renderer(element, visualizationValues(definition), definition);
    });
  }

  function clearRuntimeError() {
    const errorElement = document.getElementById("runtime-error");
    if (errorElement) {
      errorElement.hidden = true;
      errorElement.textContent = "";
    }
  }

  function showRuntimeError(error) {
    const message = error instanceof Error ? error.message : String(error);
    const errorElement = document.getElementById("runtime-error");
    if (errorElement) {
      errorElement.textContent = message;
      errorElement.hidden = false;
    }
    console.error(message);
  }

  function updateStateFromControl(control, input) {
    const reader = controlReaders[control.dataset.controlType];
    if (!reader) {
      throw new Error("Unsupported control type: " + control.dataset.controlType);
    }
    reader(input, control.dataset.variable);
    recompute();
    clearRuntimeError();
    render();
  }

  function render() {
    document.querySelectorAll(".lesson-control").forEach(function (control) {
      const variableId = control.dataset.variable;
      const value = dataContext[variableId];
      const type = control.dataset.controlType;

      if (type === "slider" || type === "number_input") {
        const input = control.querySelector("input");
        if (document.activeElement !== input) {
          input.value = String(value);
        }
        const output = control.querySelector("output");
        if (output) {
          output.value = String(value);
          output.textContent = String(value);
        }
      } else if (type === "toggle") {
        control.querySelector("input").checked = Boolean(value);
      } else if (type === "matrix_editor") {
        control.querySelectorAll("input[data-row][data-column]").forEach(function (input) {
          if (document.activeElement !== input) {
            const row = Number(input.dataset.row);
            const column = Number(input.dataset.column);
            input.value = String(value[row][column]);
          }
        });
      }
    });
    renderIntermediateValues();
    renderVisualizations();
  }

  function initializeControls() {
    document.querySelectorAll(".lesson-control").forEach(function (control) {
      const type = control.dataset.controlType;
      const eventName = type === "toggle" ? "change" : "input";
      control.addEventListener(eventName, function (event) {
        if (event.target instanceof HTMLInputElement) {
          try {
            updateStateFromControl(control, event.target);
          } catch (error) {
            showRuntimeError(error);
          }
        }
      });
    });

    try {
      recompute();
      render();
      clearRuntimeError();
    } catch (error) {
      showRuntimeError(error);
    }
  }

  function initializeMindMap() {
    const nodes = document.querySelectorAll(".mind-map-node");
    const detailName = document.getElementById("mind-map-detail-name");
    const detailSummary = document.getElementById("mind-map-detail-summary");
    const detailNote = document.getElementById("mind-map-detail-note");

    function selectNode(node) {
      nodes.forEach(function (candidate) {
        candidate.classList.remove("is-selected");
      });
      node.classList.add("is-selected");

      if (detailName) {
        detailName.textContent = node.dataset.conceptName;
      }
      if (detailSummary) {
        detailSummary.textContent = node.dataset.conceptSummary;
      }

      const targetId = node.dataset.sectionTarget;
      const target = targetId ? document.getElementById(targetId) : null;
      if (target) {
        if (detailNote) {
          detailNote.hidden = true;
          detailNote.textContent = "";
        }
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      } else if (detailNote) {
        detailNote.textContent = targetId
          ? "The linked section is unavailable in this document."
          : "This concept has no linked section.";
        detailNote.hidden = false;
      }
    }

    nodes.forEach(function (node) {
      node.addEventListener("click", function () {
        selectNode(node);
      });
      node.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectNode(node);
        }
      });
    });
  }

  window.lessonRuntime = Object.freeze({
    state: dataContext,
    context: dataContext,
    operations: operationRegistry,
    visualizations: visualizationRegistry,
    recompute: recompute,
    render: render,
  });

  initializeControls();
  initializeMindMap();
}());
