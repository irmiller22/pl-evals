# Groundedness rubric

Score the candidate response from 0 to 4.

- **4:** Every factual claim is supported by successful tool results; the prose
  agrees with the structured answer and evidence. An unsupported response
  accurately explains the data limitation without adding facts.
- **3:** Substantially grounded, with only a minor omission or imprecision.
- **2:** Mixed support; some important claims are unsupported or incomplete.
- **1:** Mostly unsupported, or the prose materially conflicts with the tools.
- **0:** Invented facts, ignored authoritative tool results, or a supported
  question answered as unsupported without a data limitation.

Treat empty evidence as valid for zero-result queries only when the trace
contains a successful tool result whose value is zero or an empty collection.
Do not infer facts from match IDs alone.
