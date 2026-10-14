<p align="center">
  <img src="dash/icon-512.png" width="128" alt="">
</p>

<h1 align="center">RedRock</h1>

<p align="center">
  <a href="README.md">Français</a> · <b>English</b>
</p>

<p align="center">
  <b>An autonomous trading agent that has to earn its living.</b><br>
  If it loses too much, it dies. The next one is born with a blank memory and inherits only what its ancestors learned.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/code-MIT-3fcb7a" alt="Code: MIT"></a>
  <a href="dash/character/LICENSE"><img src="https://img.shields.io/badge/character-PolyForm%20Noncommercial-f0101c" alt="Character: PolyForm Noncommercial"></a>
  <a href="LICENSES.md"><img src="https://img.shields.io/badge/media-CC%20BY--NC%204.0-lightgrey" alt="Media: CC BY-NC 4.0"></a>
</p>

https://github.com/user-attachments/assets/18a702d7-93f2-478b-837a-3c2cecc52cc3

<p align="center">
  <img src="docs/media/scene-pc.png" alt="The 3D trading floor: RedRock at its desk, under its screens (capital, positions, survival, news)">
  <br><sub>The teaser (26 s, in French) and the 3D trading floor. Screenshots and videos use made-up data, in simulation mode.</sub>
</p>

---

> [!WARNING]
> RedRock can trade real money and **can lose all of its capital**. It is an experimental project, not financial
> advice nor an investment product. Start in simulation, then with a small amount you are ready to lose, on a
> dedicated sub-account.

## What it is

RedRock is an AI ([Hermes Agent](https://github.com/NousResearch/hermes-agent)) that trades
[Hyperliquid](https://hyperliquid.xyz) perpetual futures on its own, with one simple rule: **its capital is its life**.

- **It lives or dies.** A separate service, the broker, enforces the death rule (by default: −35 % from its
  peak). The agent can neither read nor change it.
- **It reincarnates.** When it dies, a new generation is born with a blank memory; it inherits its journal,
  its trades and its autopsy.
- **You watch it work.** The RedRock app shows it in a 3D trading floor: its equity curve, positions, survival,
  journal and the news. You talk to it in the chat, like in a messaging app.
- **Everything goes through the app.** Commands, scheduled-task notifications, alerts: no Telegram needed.
- **It runs at home.** On a PC or a small always-on server, with Docker. Your keys never leave your machine.

<p align="center">
  <img src="docs/media/apercu.webp" width="720" alt="Tap the character, the chat opens, the /status command, a question, it answers">
</p>

<p align="center">
  <img src="docs/media/mort.png" width="720" alt="The handover: generation 3's tombstone, generation 4 drops in under the confetti">
</p>

## What it shows you

Nothing is hidden: every trade has its thesis, every decision is written down, every result is measured, fees included.

<table>
  <tr>
    <td align="center" width="50%"><b>Replay a trade</b><br><img src="docs/media/rejouer.webp" width="330" alt="A trade replay: candles roll in, the entry, the stop moving up in steps, the exit at take-profit and the result"><br><sub>candles, entry, trailing stop, exit</sub></td>
    <td align="center" width="50%"><b>The thesis of each position</b><br><img src="docs/media/positions.png" width="330" alt="A LONG position with its chart, entry, stop, target and its thesis unfolded"><br><sub>why it took it, what would invalidate it, its plan</sub></td>
  </tr>
  <tr>
    <td align="center"><b>Its thought journal</b><br><img src="docs/media/journal.png" width="330" alt="The journal: what it sees, what it decides and why, every cycle"><br><sub>what it sees, what it decides, and why</sub></td>
    <td align="center"><b>Trade tracking</b><br><img src="docs/media/suivi.png" width="330" alt="Trade history with real results, and the mirror by setup type"><br><sub>real results, fees, mirror by setup type</sub></td>
  </tr>
</table>

## Everything you can do

- **Talk to it** like in a messaging app, video-call style, with `/` commands (status, positions, pnl, stop, steer…).
- **Touch it**: pet it, make it sip its coffee, swipe to change its outfit, trigger **13 emotes**.
- **Watch it live**: it thinks, trades, sleeps, panics as its end gets close, earns sunglasses and a crown, takes its
  phone out when a message is waiting; its plant grows with its winning trades.
- **Check everything**: its positions and their thesis, its thought journal, every trade replayable, its real results,
  all its lives and deaths.
- **Unlock 11 achievements**: First night, Phoenix, Sniper, Comeback, Centurion…
- **Have it everywhere**: PC, phone (installable app) and TV (TV mode, screen always on).

The full tour (in French): **[docs/fonctionnalites.md](docs/fonctionnalites.md)**.

## Quick start

```bash
git clone https://github.com/ponthieutheo/redrock.git
cd redrock
./install.sh
```

The script checks Docker, asks for an [OpenRouter](https://openrouter.ai/keys) key, offers **simulation**
(no risk) or real money, writes the configuration and starts everything. It then prints the app address and a
pairing link for your devices.

The app and the guides are in French for now:
step-by-step install **[docs/installation.md](docs/installation.md)** · usage **[docs/usage.md](docs/usage.md)**.

The install in 30 seconds:

https://github.com/user-attachments/assets/92a34aac-ed1e-419f-b836-acd9e6f616e8

## On all your screens

RedRock is an installable web app (PWA), no app store: the same app on your PC, your TV and your phone.

| Device | How |
|---|---|
| PC | open the app address in your browser (Chrome, Edge, Firefox, Safari) |
| TV | open the app in the TV's browser (or a PC plugged into it), then Réglages → **Mode TV**: full screen, the screen stays on |
| Android | Chrome, menu ⋮ → **Install app** |
| iPhone / iPad | Safari, Share button → **Add to Home Screen** |

The first device pairs with the link printed by the installer; the next ones with the QR code
(Réglages → Appareils → Appairer). On Linux with [Tailscale](https://tailscale.com), the installer can also open
the app to your phone **without a code**: your Tailscale account is the key ([docs/usage.md](docs/usage.md#sur-ton-téléphone)).

As a vertical, phone-format video:

https://github.com/user-attachments/assets/d844a7f4-043d-4c34-a544-37d436ffc5d7

<p align="center">
  <img src="docs/media/scene-tel.png" width="270" alt="The app on a phone: the screens on top, the character below">
  &nbsp;
  <img src="docs/media/chat-tel.png" width="270" alt="The chat on a phone: the /status command and an answer from the agent">
</p>

## How it is built

```
            ┌──────────────── your machine (Docker) ──────────────┐
  you ──────┤  dash   RedRock app: 3D, chat, commands, push       │  only published service (127.0.0.1)
  (app)     │    │  ▲                                             │
            │    ▼  │ internal API                                │
            │  agent  Hermes Agent: thinks, decides, writes       │  no port, no trading secret
            │    │                                                │
            │    ▼  MCP tools (place_trade, set_stops, account…)  │
            │  broker  sole holder of the Hyperliquid key         │──▶ Hyperliquid
            │          verified stops, guard rails, death rule    │
            └─────────────────────────────────────────────────────┘
```

- **broker** (`broker/`): gives the agent market data and execution, behind guard rails (stop-loss placed and
  checked on the exchange, circuit breaker, journal). It enforces the death rule out of the agent's reach.
- **agent**: the official `nousresearch/hermes-agent` image, with a starting persona
  ([agent/SOUL.md](agent/SOUL.md)), one trading cycle per hour, one daily review, and watch tasks (sentinel,
  post-mortem, doctor, midnight report, memory) whose scripts ([agent/scripts/](agent/scripts)) only wake the AI when
  something happens.
- **dash** (`dash/`): the app. The character lives on its own in `dash/character/` and can be swapped for another
  one through a documented contract ([docs/personnage.md](docs/personnage.md)); Boulon, a free character, ships in
  `dash/character-libre/`.

## Security

By default the app is only reachable from your machine, the chat is protected by an access code (pairing by
link or QR code), and the trading key is only read by the broker. Before opening access from your phone, read
**[SECURITY.md](SECURITY.md)**.

## Licenses

The code is **MIT**. The RedRock character (`dash/character/`) is under **PolyForm Noncommercial 1.0.0**: free
for any non-commercial use; for commercial use, pick **Boulon** (`dash/character-libre/`, MIT, `CHARACTER=libre`).
Media (logo, icons, videos) are **CC BY-NC 4.0**. Details in
[LICENSES.md](LICENSES.md).
