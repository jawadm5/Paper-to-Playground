# Design inspiration and technical references

Public sources were inspected on 2026-10-03. The technical notes below were written during initial planning; current authenticated runs and verification supersede their historical untested status and are recorded in PROGRESS.md. These references inform our design; they are not runtime dependencies or proof that the generator can reproduce their quality. Use the assigned paper, not a secondary explainer, as scientific authority for each case. Reused code or assets require their own license review and README credit.

## Learning experience references

| Reference | Pattern informing this project | Boundary |
| --- | --- | --- |
| [Learn Your Way](https://research.google/blog/learn-your-way-reimagining-textbooks-with-generative-ai/) | Multiple representations of common source material and navigation between them | Our executable experiments and offline assessment need their own implementation |
| [PhET](https://phet.colorado.edu/en/about) | Purposeful controls, immediate feedback, multiple representations, guided exploration | Borrow teaching principles rather than entire simulations |
| [Red Blob Games](https://www.redblobgames.com/pathfinding/a-star/introduction.html) | Stepwise mechanisms, manipulable examples, comparisons | Handcrafted article quality is a reference, not evidence of automatic generation |
| [Seeing Theory](https://seeing-theory.brown.edu/basic-probability/index.html) | Explanations beside probability experiments | The site is archived for reference |
| [Transformer Explainer](https://poloclub.github.io/transformer-explainer/) | Overview linked to internal computation | Our scope is the requested mechanism, not an entire language model |
| [TensorFlow Playground](https://playground.tensorflow.org/) | Connected input, intermediate, and output views | Do not import training or broad hyperparameter controls when unnecessary |
| [Tangle](https://worrydream.com/Tangle/) | Reactive numbers within prose | Pattern reference; library adoption is not decided |
| [Mathigon](https://mathigon.org/teachers) | Manipulatives and construction activities | Questions must remain locally verifiable |
| [IHMC CmapTools](https://cmap.ihmc.us/docs/theory-of-concept-maps) | Labeled relationships and cross-links | A concept map is more than a list of headings in bubbles |
| [LOOPY](https://ncase.me/loopy/) | Exploring propagation in systems diagrams | Use dynamics only where supported by the mechanism |
| [NotebookLM mind maps](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-studying-help/) | Source-based navigation through concepts | No learner-time model calls in our page |
| [NotebookLM study tools](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-student-features/) | Source-linked quiz explanations | Preserve our agreed final-submission feedback timing |
| [Brilliant](https://brilliant.org/) | Objective-oriented practice and progress feedback | Current public product descriptions are not an independent learning-efficacy evaluation |
| [Intuitive Papers](https://intuitivepapers.ai/flashattention-fast-and-memory-efficient-exact/) | Paper-focused explanatory sequence and comparisons | Secondary explanation is not a substitute for the original paper |
| [Distill on interactive articles](https://distill.pub/2020/communicating-with-interactive-articles/) | Details on demand, prediction, simulations, and multiple representations | Design synthesis; no automatic claim of learning gains for our application |

## Technical source notes

- [OpenRouter chat completions](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion) documents the request endpoint, completion limits, structured-response options, and token usage fields. The implementation must validate observed provider responses rather than infer usage from text length.
- [DeepSeek V4.1 Flash on OpenRouter](https://openrouter.ai/deepseek/deepseek-v4.1-flash) identifies `deepseek/deepseek-v4.1-flash` and documents structured outputs and image input. Use this exact model for the user-specified testing profile. No price or throughput guarantee is assumed; an authenticated capability and latency test remains outstanding.
- [DeepSeek release announcement](https://api-docs.deepseek.com/news/news260910/) confirms the model family. DeepSeek's direct endpoint aliases are not OpenRouter model identifiers.
- [MiniRacer package](https://pypi.org/project/mini-racer/) documents Python 3.11 compatibility within its supported range, packaged native-engine wheels, and execution timeout support. These support its candidacy for portable JavaScript checks; installation and resource-limit behavior still need local and target-platform tests.
- [Playwright browser installation](https://playwright.dev/python/docs/browsers) distinguishes the Python package from browser binaries and OS dependencies. The generator must not require an extra installation command in assessment.
- [pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) describes extraction limitations. Text extraction must not be treated as reliable recovery of every scanned page or equation.

The attempted unauthenticated model-catalog request from the local shell could not connect. The model identifier and advertised capabilities were instead verified through OpenRouter's public model page. No authenticated OpenRouter call has been made in this specification phase.
