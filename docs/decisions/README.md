# Decision log (ADRs)

Each Architecture Decision Record captures one project decision: the context, the options considered, the choice and its consequences. Decisions are made by the project owner; implementation follows them.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-scope-and-purpose.md) | Educational heads-up call/fold analyser, not a gambling tool | Accepted |
| [0002](0002-own-engine-libraries-for-plumbing.md) | Write the poker/probability engine ourselves; libraries for plumbing | Accepted |
| [0003](0003-web-architecture.md) | FastAPI backend + custom frontend, one container on Hugging Face Spaces | Accepted |
| [0004](0004-multi-street-model.md) | Model turn/river play instead of assuming showdown | Accepted |
| [0005](0005-range-input.md) | Range input via presets, 13×13 grid and text notation, kept in sync | Accepted |
| [0006](0006-frontend-without-build-step.md) | Plain HTML/CSS/JS frontend, no build step | Accepted |
| [0007](0007-python-tooling-uv.md) | Python 3.12 managed with uv; ruff and pytest | Accepted |
| [0008](0008-units-in-chips.md) | Display amounts in chips | Accepted |
| [0009](0009-card-picker.md) | Clickable 52-card grid picker | Accepted |
| [0010](0010-card-representation.md) | Cards are integers 0–51 | Accepted |
| [0011](0011-evaluator-verification.md) | Verify the evaluator exhaustively and against `treys` | Accepted |
| [0012](0012-property-based-testing.md) | Property-based tests with `hypothesis` | Accepted |
