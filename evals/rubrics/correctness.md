# Correctness rubric

Use deterministic graders for values whenever possible. An LLM judge may assess
whether the answer is complete and readable, but must not override a failed
numeric, exact, schema, tool-call, or abstention grade.
