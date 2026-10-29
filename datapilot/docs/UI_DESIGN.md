# Import workbench design

The interface is organized around a file manifest, per-file executions and source evidence. The workspace selector stays visible; folder paths and execution results provide the content rather than illustrative dashboards.

Design guidance: the official Anthropic [frontend-design skill](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design/SKILL.md), read at that pinned commit. It was consulted as developer guidance; no third-party agent tools or runtime analytics skills were installed.

Palette: harbor #183642 navigation, cloud #f4f6fa canvas, white #ffffff content, cobalt #3559d9 actions, seafoam #e0f2e8 success, amber #9a641e attention. Utility typography uses system Aptos/Segoe UI with no external font request. Tables remain readable and horizontally scrollable; mobile navigation and the import manifest adapt to narrow screens. Focus visibility, input labels, dialog keyboard handling and reduced motion are included.

The original textual screen contracts remain in the supplied architecture. Unimplemented cleaning, AI, business analytics and export paths describe their availability honestly instead of displaying mock results.
