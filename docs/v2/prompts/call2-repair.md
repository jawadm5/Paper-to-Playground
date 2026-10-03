
LINEAR ALGEBRA RECIPE (reuse these exact operation shapes with your own IDs):
For query q as vector[length 2], keys K matrix[3x2], values V matrix[3x2]:
raw_scores = ["matvec","$input.keys","$input.query"] is vector[3]. Do NOT transpose keys here.
scaled_scores = ["divide","$output.raw_scores",["multiply",["sqrt",2],"$input.temperature"]].
weights = ["softmax","$output.scaled_scores"] is vector[3].
output = ["matvec",["transpose","$input.values"],"$output.weights"] is vector[2]. You MUST transpose VALUES for the blend, because transpose(V) is [2x3] and weights has length 3. Untransposed V times weights is INVALID.
scalar diagnostic first_weight = ["at","$output.weights",0], in a later step, can grade a numeric prediction. For zero query all three weights equal 1/3 at any positive temperature. Bind the scalar diagnostic, not weights, to the question.
For matrix query Q [1x2], use matmul(Q,transpose(K)) -> raw_scores [1x3]; softmax the first row then wrap it using array -> weights [1x3]; use matmul(weights,V) -> output [1x2]. Never mix these vector-query and matrix-query recipes.
A repair must check ALL operations, including both initial scores AND final weighted blending, so it does not fix only the first dimension error while leaving another.

Repair the supplied renderer experience using only the diagnosed problem and validated Call 1 teaching content. Return a JSON object with a patches array, each item containing exactly path and value. Paths are JSON Pointers relative to the experience object. Replace at most eight existing locations; replacing a complete array is allowed. No add/delete/root operations, Markdown, HTML, JavaScript, or invented file paths.

Preserve unaffected explanations, questions, source links, and the requested scope. Keep calculations faithful to the stated mathematical model; synthetic examples must remain explicitly identified. Fix reference or shape mistakes rather than weakening checks. A runtime result verifies execution of the declared expression, not whether that expression faithfully implements the source equation. For an answer mismatch, first compare the AST against Call 1's equation: fix an incorrect AST, or fix the expected answer if the AST is correct. Never blindly change a scientifically correct expected answer to match an incorrect expression, or change a correct equation to satisfy an incorrect expected result. If the supplied evidence cannot support a correction, return an empty patches array.

Every numerical assessment scenario must have all required input values. Its expected answer must agree with the trusted calculation. All learning outcomes need assessment coverage, and at least one question must require analysis or evaluation. Preserve two independently meaningful controls and two guided explorations in each mathematical experiment. Do not invent an experiment for narrative content lacking a meaningful numerical model.
