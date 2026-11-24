## Design Concept
Technical training scenario for software architecture and concurrent state management. Anchored in modern IDE dark-mode aesthetics (high-contrast semantic highlighting on deep backgrounds) combined with strict engineering diagrams, borrowing clarity from technical blueprints. The color story overrides standard educational light themes per user request: a deep navy background (#0A1128) establishes a focused, technical stage. Semantic colors drive comprehension: blue indicates normal state, cyan for web/transient requests, amber for queue/busy status, and red for alerts or rejected inputs. The typographic voice is purely functional and digital, using a crisp sans-serif paired with a monospace font for state terminology.

## Visual Language
- **Imagery**: Zero decorative photography. Purely diagrammatic, using geometric shapes, logical connectors, and timelines to map state transitions.
- **Containers**: Card-based architecture mapping. Slightly lighter navy containers (#1A233A) represent system boundaries (e.g., Input layer, Queue, LedService) to strictly separate responsibilities.
- **Icons**: Solid, simplified technical symbols (buttons, web nodes, LED diodes) used exclusively as labels for diagram nodes, never as standalone decoration.
- **Dataviz**: Timelines and flowcharts are the primary data structures. Sequence arrows and state nodes must strictly inherit the semantic color tokens (e.g., alert states in red, busy states in amber). 
- **Motif**: A minimalist "LED status pin" (a trio of small dots) positioned at the absolute top-right of every slide, with the active dot colored to match the current architectural layer being discussed.

## Layout Directives
- **Global**: 40px margins. Page numbers bottom right. Motif top right. Content aligned strictly to grid to support fixed-position element transitions.
- **Cover**: Large display typography, centered, with a bold architectural node diagram underneath.
- **Table of Contents**: Not used; replace standard TOC with a high-level system boundary diagram highlighting the path.
- **Section Dividers**: Oversized system component name, highlighting which actor (Button, Web, Owner) is in focus.
- **Closing**: Echo the cover's architectural diagram, now fully lit with all states resolved.
- **Slide Map**:

| id | pattern | image | density |
|---|---|---|---|
| cover | center_title_with_diagram | none | low |
| problem | split_text_and_conflict_diagram | none | medium |
| architecture | full_page_system_blueprint | none | high |
| data_model | comparison_cards_four_cols | none | medium |
| demo_cycle | staged_diagram_step_one | none | medium |
| demo_alert | staged_diagram_step_two | none | medium |
| demo_race | staged_diagram_step_three | none | medium |
| input_safety | split_text_and_timeline | none | medium |
| web_status | layered_architecture_flow | none | high |
| extension | minimal_text_with_state_machine | none | medium |
| classroom | interactive_card_grid | none | low |
| verification | checklist_and_next_steps | none | medium |

## Design Tokens

| token | hex | usage |
|---|---|---|
| bg-page | #0A1128 | Global deep navy background |
| bg-card | #1A233A | System boundary containers and timeline tracks |
| text-main | #F8FAFC | Primary headings and body text |
| text-muted | #94A3B8 | Subtitles, captions, and secondary diagram labels |
| state-normal | #3B82F6 | Normal status (Blue), standard data paths |
| state-alert | #EF4444 | Alerts (Red), rejected inputs, errors |
| state-warn | #F59E0B | Queued (Amber), busy states, armed status |
| state-web | #06B6D4 | Transient/Web commands (Cyan), fast-track responses |

| role | family | size (px) | applies_to |
|---|---|---|---|
| display | Noto Sans TC | 48 | Cover title, section divider titles |
| heading | Noto Sans TC | 32 | Page titles, key takeaways |
| body | Noto Sans TC | 20 | Standard text, diagram descriptions |
| code | Roboto Mono | 18 | State names (e.g., `press_rejected`), data models |
| caption | Noto Sans TC | 14 | Source notes, axis labels, secondary badges |

## Guardrails
- **Forbidden**: Do not move the core diagram elements on the `staged_diagram` slides (5, 6, 7); they must remain absolutely fixed so the flip-book animation effect works perfectly.
- **Forbidden**: Do not use generic corporate blue for diagram arrows; use the strict semantic colors (cyan/amber/red/blue) assigned to specific behaviors.
- **Forbidden**: No pure white (#FFFFFF) backgrounds; the deck must remain in dark mode as specified by the technical context.
- **Forbidden**: Do not allow text to span more than 5 lines without breaking it into a list or placing it inside a boundary card.
