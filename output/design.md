# Campus Customs Desk: Dashboard Design

**Concept:** a 3D pinball cabinet floating over a city-planet at dusk. The look borrows from two places. The background is a Star Wars capital world: endless towers, layered air traffic, stars and moons. The UI sits on that background like the table from *3D Pinball for Windows – Space Cadet*: chrome rails, a black LED score panel, round bumpers, rollover lamps, a plunger and flippers. The pinball metaphor fits the job. A ticket is "launched" into the table, the agents bounce it between them, and the human works the flippers that decide whether money moves.

Built with React + Vite + TypeScript in `frontend/`. It talks to the FastAPI backend at `http://localhost:8000` (`frontend/.env` → `VITE_API_BASE`). Start it with `npm run dev`, which opens http://localhost:5173.

## Background: the capital city (`CityBackground.tsx`)

- **Sky:** a dusk gradient from deep space navy, through violet and magenta, to an orange horizon glow. On top of it are twinkling stars, an occasional shooting star, two moons, and a slow capital-ship silhouette crossing the upper sky.
- **Skyscrapers:** three parallax layers, generated once per window size.
  - *Far:* tall, pale-blue spires.
  - *Middle:* warm windows.
  - *Near:* near-black slabs with big lit windows and an orange rim light from the sunset.
  - Spires carry blinking red and blue beacons.
- **Air traffic:** 16 lanes of speeders with headlights and red light trails, flying both directions. Each lane is drawn between the building layers by depth, so far traffic weaves *behind* near towers and near traffic streaks past in front. Closer lanes are bigger, brighter and faster.
- **Why:** it's alive and atmospheric without competing with the data. All of it sits behind semi-transparent "glass" panels (62% opaque, light blur), so it reads as depth, not noise. It also slows down for users who prefer reduced motion.

## Layout (the pinball table)

| Area | Pinball part | Contents |
|---|---|---|
| Top | Backglass / marquee | Title, an LED **mission line** saying what needs attention, stardate (`desk.date_today`), resolved count, link status |
| Left | Rollover lanes + plunger | The three tickets, a **LAUNCH TEAM** plunger, and **NEW GAME · RESET DB** |
| Center | Playfield | Agent bumpers, delegation rails, one comm card per agent |
| Right | Score panel + flipper console | LED **checking balance**, pending total, balance if everything is approved, and the **Approval Console** |
| Bottom | Debrief + log | **Mission Debrief** (the Boss's summary) and the **Transmission Log** (every event) |

Every panel has a chrome bevel border (a light-to-dark-to-light metallic gradient) to echo Space Cadet's rails. Headings use Orbitron, telemetry uses Share Tech Mono, and LED readouts use a dot-matrix font with an orange glow and a dot mask.

## How each agent reads differently

Each agent has one colour, one glyph and one call sign, used everywhere: bumper, comm card, log line, debrief crew tag. You can tell who is talking without reading the name.

| Agent | Call sign | Colour | Glyph | Why |
|---|---|---|---|---|
| Boss | COMMAND | gold `#ffd23f` | crown | Gold signals authority and the final call; it sits at the top of the playfield, and its comm card spans the full row above the specialists |
| Inventory | CARGO | cyan `#38e1ff` | crate | Cool and factual: stock counts and shortfalls |
| Accounting | CREDITS | green `#53ff8a` | coin | Money is green, and it matches the approve flipper |
| Facilities | DOCKMASTER | orange `#ff8a3d` | building | Warm and physical: the shop space and the landlord |
| Customer Service | COMMS | magenta `#ff4fd8` | speech bubble | The one "voice" that talks to people outside the shop |
| Human | OPERATOR | red `#ff5a5a` | person | Red marks the only actor who can move money |

**On the playfield:**
- The **active** agent's bumper flashes, grows, and sends out a shockwave ring.
- When one agent asks another, the **rail between them lights up** in the callee's colour with moving dashes.
- When the run ends, rails that were used stay faintly lit, so you can see the routing afterwards.
- Agents the Boss **never dispatched** fade to grey. You can compare this against the plan in `desk_tickets.html` at a glance: for example, only Facilities lights up on ticket 102.

**Comm cards:**
- Each card shows what the agent last *said*: the request it sent, or the summary it reported back.
- While active, it also shows what it's *doing* (the MCP call in progress) in monospace.
- Below that are chips for every **MCP tool it used** on this ticket.
- A status pill reads ACTIVE, REPORTED, NOT DISPATCHED or STANDBY.

**Transmission log:** one line per event, showing time, call sign in the agent's colour, an icon, and the text.
- Delegations read as speech ("asks INVENTORY: …", "reports: …") in bright white.
- Tool calls and results are dimmer *telemetry* and can be hidden with a toggle.
- A human payment is highlighted red, and the Boss's final call is highlighted gold.

## How resolved tickets show up

Each ticket lane has a **rollover lamp**, like the lights on a pinball lane:

| Lamp | Meaning |
|---|---|
| Amber, slow blink | **Open**: the team hasn't worked it |
| Cyan, fast pulse, with a "TEAM ON IT" chip | **Running**: the playfield is live |
| Green, steady, with a "RESOLVED" chip | **Resolved**: the team's run finished and the Boss made the final call |

- **What "resolved" means:** the team finished its run. A second chip shows what the ticket is still waiting on (e.g. AWAITING APPROVAL, AWAITING CUSTOMER). That way "the agents are done" is never confused with "money already moved".
- **The debrief:** when a run finishes, the Mission Debrief shows a green **RESOLVED BY TEAM** stamp, the Boss's final status, the crew that worked it, the decision in one line, findings, actions, and a **NEXT ▸** step.
- **The marquee:** counts RESOLVED x/3 and says JACKPOT when all three are done. A toast also confirms that the run finished.
- **Why:** pinball players read lamps peripherally. Amber/cyan/green tells you the state of all three tickets without reading any text.

## How cash shows up

- **The score panel:** the checking balance is the **pinball score**, an orange dot-matrix LED in a black bezel at the top of the right column. It's the only number on screen styled that way, so it reads as the thing that matters most.
- **Under the score:**
  - **PENDING APPROVAL:** the total of all queued payment requests.
  - **IF ALL APPROVED:** the balance if every pending request is approved. It turns red if that would go negative, an early warning before anyone clicks.
- **When an approved payment lands:**
  - The LED **counts down** from the old balance to the new one.
  - It flashes red with a short "tilt" shake.
  - A red **−$840.00** drops off the display.
  - The log records the operator, the amount, and what changed (e.g. "Invoice 501 marked paid", or the lease's next due date moving forward).
- **Why:** cash only ever goes out in this scenario, and it only moves when the human approves. Making that moment loud and visual (a pinball "tilt") makes it obvious which action had real consequences.

## Approvals (the flippers)

- **The request cards:** agents only *queue* payments. Each request appears in the Approval Console as a card showing amount, payee, reason, which agent asked, and which ticket it's for. Requests for the selected ticket are outlined in white.
- **The flippers:** each card has two flipper-shaped buttons, a green **APPROVE & PAY** and a red **REJECT**. They tilt when pressed, like real flippers.
- **Operator name:** the flippers stay locked until the operator types a name. That name is recorded as `approved_by` in the `payments` table, and the server refuses agent names.
- **Purchase orders:** they appear as cyan cards with **APPROVE PO**. The card states that no cash moves.
- **Why:** the console sits directly under the cash score, so the cause (approve) and the effect (balance drops) are in the same eyeline.

## Sound (`frontend/src/sound.ts`)

- **Generated live:** pinball-cabinet sound effects are synthesized in the browser with the Web Audio API, so there are no audio files and no copied Space Cadet samples.
- **One pitch per agent:** each agent has its own pitch, so you can hear who is working without looking.

| Agent | Pitch |
|---|---|
| Boss | G3 (deepest) |
| Facilities | C4 |
| Inventory | E4 |
| Accounting | G4 |
| Customer Service | C5 (highest) |

| Moment | Sound |
|---|---|
| LAUNCH pressed | Plunger: a filtered noise whoosh, a rising sweep and a ding |
| An agent asks a teammate | **Laser zap**, a falling sawtooth sweep pitched to the agent being called |
| An agent calls an MCP tool | **Bumper pop**: a short square-wave hit in that agent's pitch, plus a click |
| An agent reports back | Two-note rising chime in that agent's pitch |
| Run finished (Boss signs off) | Jackpot arpeggio |
| Human approves a payment | Coin pickup, then a descending "score drain" (cash leaving) |
| Rejected payment, refused delegation, error, failed launch | Low "tilt" buzzer |
| Selecting a ticket lane | Rollover blip |

- **Pacing:** each poll's new events play as a short, staggered sequence of at most 8 sounds, so a burst of tool calls sounds like a pinball rally, not noise.
- **No replay:** the backlog isn't replayed when the page first loads.
- **Volume:** a compressor keeps it from getting loud.
- **Toggle:** **♪ SOUND ON/OFF** in the marquee, remembered in the browser. Browsers only allow audio after a click, so the board unlocks audio on your first click anywhere.

## Refresh model

- **Polling:** the board polls `/tickets`, `/cash` and `/approvals`, and reads `/events?since=<last id>` incrementally.
- **Speed:** it polls every 1 s while a run is in flight and every 3 s when idle.
- **Backend offline:** the marquee flips to a blinking NO SIGNAL, and a banner shows the exact command to start the backend.
