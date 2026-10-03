# Design references and attribution

These references informed teaching and interaction patterns. They are not runtime dependencies. Scientific explanations are grounded in the supplied paper, and original source figures retain attribution. The renderer, SVG diagrams, concept-layout algorithm, and browser calculation components are implemented in this project.

## Learning and interface references

| Reference | Pattern informing the project |
| --- | --- |
| [Learn Your Way](https://research.google/blog/learn-your-way-reimagining-textbooks-with-generative-ai/) | Multiple representations of the same learning material |
| [PhET](https://phet.colorado.edu/en/about) | Purposeful controls, immediate feedback, and guided exploration |
| [Red Blob Games](https://www.redblobgames.com/pathfinding/a-star/introduction.html) | Explanations connected to manipulable examples |
| [Seeing Theory](https://seeing-theory.brown.edu/basic-probability/index.html) | Probability experiments alongside explanations |
| [Transformer Explainer](https://poloclub.github.io/transformer-explainer/) | Connected views of attention computations |
| [TensorFlow Playground](https://playground.tensorflow.org/) | Visible relationships between inputs and results |
| [IHMC concept maps](https://cmap.ihmc.us/docs/theory-of-concept-maps) | Directed, labeled relationships between concepts |
| [NotebookLM mind maps](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-studying-help/) | Concept navigation linked to source material |
| [Distill: communicating with interactive articles](https://distill.pub/2020/communicating-with-interactive-articles/) | Combining exposition, prediction, and interactive exploration |
| [n8n workflow nodes](https://docs.n8n.io/build/understand-workflows/workflow-components/work-with-nodes/) | Organized branching connections and compact graph nodes |
| [Transmit](https://transmit.tailwindui.com/) | A restrained context rail and a dominant reading column |

## Technical references

- [OpenRouter chat completions](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion): provider request and usage-accounting interface.
- [DeepSeek V4.1 Flash on OpenRouter](https://openrouter.ai/deepseek/deepseek-v4.1-flash): the project's testing model identifier.
- [MiniRacer](https://pypi.org/project/mini-racer/): JavaScript execution used for local calculation validation.
- [pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html): PDF extraction behavior and limitations.
- [Playwright](https://playwright.dev/python/docs/browsers): development browser verification; not a generator installation requirement.

Pinned dependency versions are recorded in `requirements.txt`. Actual provider runs and local checks are documented in [PROGRESS.md](PROGRESS.md); references alone do not establish runtime compatibility, scientific correctness, or learning effectiveness.
