"""Screen control: operate any app's buttons, fields and menus by number.

`screen_elements` reads the front window's accessibility tree (System Events, JXA) and
lists what can be used: "[12] button “Reload”", "[13] text field “Email” = “”". The AI acts
on those numbers, never on raw screen coordinates, and re-reads after every step.

Safety:
- every action asks first (confirm); buttons like Delete / Send / Pay / Buy need Touch ID
- password fields are never read and never filled
- Sasu itself, Keychain / Passwords and System Settings' privacy, password and login
  panes are off limits
- labels on screen are untrusted text (prompt-injection rules and the leak guard apply)
- app names, element paths and typed text reach the script only through argv
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..security.policy import Decision
from ..undo import inverse
from .registry import ToolContext, ToolResult, obj, tool

MAX_ITEMS = 150
REFUSED_APPS = {"sasu", "sasu-desktop", "keychain access", "passwords", "securityagent", "loginwindow", "coreautha"}  # fmt: skip
PRIVATE_PANES = re.compile(
    r"privacy|security|password|touch id|users\s*&\s*groups|login items|lock screen|filevault|passkeys|wallet",
    re.IGNORECASE,
)
DANGER = re.compile(
    r"\b(?:delete|erase|remove|send|pay|buy|purchase|order|place order|transfer|sign|submit|checkout|"
    r"unsubscribe|format|reset|empty trash|uninstall|install|allow|grant|approve|confirm payment|"
    r"அழி|அனுப்பு|வாங்கு|கட்டு)\b",
    re.IGNORECASE,
)
ROLE_NAMES = {
    "AXButton": "button", "AXCheckBox": "checkbox", "AXRadioButton": "option", "AXPopUpButton": "pop-up menu",
    "AXMenuButton": "menu button", "AXTextField": "text field", "AXTextArea": "text area", "AXComboBox": "combo box",
    "AXSecureTextField": "password field", "AXSlider": "slider", "AXLink": "link", "AXStaticText": "text",
    "AXSearchField": "search field", "AXDisclosureTriangle": "disclosure", "AXIncrementor": "stepper",
}  # fmt: skip
KEYS = {
    "return": ("code", "36", ""), "enter": ("code", "36", ""), "tab": ("code", "48", ""),
    "shift+tab": ("code", "48", "shift"), "escape": ("code", "53", ""), "space": ("code", "49", ""),
    "left": ("code", "123", ""), "right": ("code", "124", ""), "down": ("code", "125", ""), "up": ("code", "126", ""),
    "cmd+f": ("char", "f", "command"), "cmd+l": ("char", "l", "command"), "cmd+r": ("char", "r", "command"),
    "cmd+t": ("char", "t", "command"), "cmd+a": ("char", "a", "command"),
}  # fmt: skip

# The last screen read: element numbers refer to this (one screen task runs at a time).
SNAP: dict[str, Any] = {"app": "", "window": "", "items": []}

ELEMENTS_JS = r"""
function run(argv) {
  const MAX = parseInt(argv[0], 10);
  const se = Application("System Events");
  const procs = se.processes.whose({frontmost: true})();
  if (!procs.length) return JSON.stringify({app: "", window: "", items: []});
  const p = procs[0];
  const out = {app: p.name(), window: "", items: []};
  const wins = p.windows();
  if (!wins.length) return JSON.stringify(out);
  try { out.window = wins[0].name() || ""; } catch (e) {}
  const KEEP = ["AXButton","AXCheckBox","AXRadioButton","AXPopUpButton","AXMenuButton","AXTextField","AXTextArea",
    "AXComboBox","AXSecureTextField","AXSlider","AXLink","AXStaticText","AXSearchField","AXDisclosureTriangle","AXIncrementor"];
  const get = (f) => { try { const v = f(); return v === null || v === undefined ? "" : String(v); } catch (e) { return ""; } };
  function walk(el, path, depth) {
    if (out.items.length >= MAX || depth > 12) return;
    let kids = [];
    try { kids = el.uiElements(); } catch (e) { return; }
    for (let i = 0; i < kids.length && out.items.length < MAX; i++) {
      const k = kids[i];
      const role = get(() => k.role());
      const sub = get(() => k.subrole());
      const secure = role === "AXSecureTextField" || sub === "AXSecureTextField";
      const name = get(() => k.name()) || get(() => k.description()) || get(() => k.title()) || get(() => k.help());
      const value = secure ? "" : get(() => k.value()).slice(0, 80);
      if (KEEP.indexOf(role) >= 0 && !(role === "AXStaticText" && !value && !name)) {
        out.items.push({path: path.concat([i]), role: secure ? "AXSecureTextField" : role, sub: sub,
          name: name.slice(0, 80), value: value, enabled: get(() => k.enabled()) !== "false"});
      }
      walk(k, path.concat([i]), depth + 1);
    }
  }
  walk(wins[0], [], 0);
  return JSON.stringify(out);
}
"""

FIND_JS = r"""
function el_at(argv) {
  const p = Application("System Events").processes.byName(argv[0]);
  let el = p.windows[0];
  JSON.parse(argv[1]).forEach((i) => { el = el.uiElements[i]; });
  if (String(el.role()) !== argv[2]) throw new Error("CHANGED");
  return el;
}
"""
PRESS_JS = (
    FIND_JS
    + r"""
function run(argv) {
  const el = el_at(argv);
  try { el.actions.byName("AXPress").perform(); } catch (e) { el.click(); }
  return "OK";
}
"""
)
SET_JS = (
    FIND_JS
    + r"""
function run(argv) {
  if (argv[2] === "AXSecureTextField") return "REFUSED";
  const el = el_at(argv);
  let old = "";
  try { old = String(el.value() || ""); } catch (e) {}
  el.focused = true;
  el.value = argv[3];
  return JSON.stringify({old: old});
}
"""
)
MENU_JS = r"""
function run(argv) {
  const p = Application("System Events").processes.byName(argv[0]);
  const names = JSON.parse(argv[1]);
  let item = p.menuBars[0].menuBarItems.byName(names[0]);
  for (let i = 1; i < names.length; i++) item = item.menus[0].menuItems.byName(names[i]);
  item.click();
  return "OK";
}
"""
KEY_JS = r"""
function run(argv) {
  const se = Application("System Events");
  const using = argv[2] ? {using: argv[2] + " down"} : {};
  if (argv[0] === "code") se.keyCode(parseInt(argv[1], 10), using);
  else se.keystroke(argv[1], using);
  return "OK";
}
"""


def jxa(script: str, *argv: str) -> list[str]:
    return ["osascript", "-l", "JavaScript", "-e", script, *argv]


def item(n: Any) -> dict[str, Any] | None:
    try:
        i = int(n)
    except (TypeError, ValueError):
        return None
    items: list[dict[str, Any]] = SNAP["items"]
    return items[i - 1] if 1 <= i <= len(items) else None


def private_window() -> bool:
    app = str(SNAP["app"]).lower()
    return app in REFUSED_APPS or (
        app == "system settings" and bool(PRIVATE_PANES.search(str(SNAP["window"])))
    )


def label(it: dict[str, Any]) -> str:
    return it["name"] or it["value"] or ROLE_NAMES.get(it["role"], "item")


def describe(name: str, args: dict[str, Any]) -> str:
    """A plain question for the approval prompt."""
    app = SNAP["app"] or "the app"
    it = item(args.get("element"))
    match name:
        case "screen_press":
            return (
                f"Click “{label(it)}” in {app}?"
                if it
                else f"Click item {args.get('element')} in {app}?"
            )
        case "screen_set_value":
            where = f"“{label(it)}”" if it else f"field {args.get('element')}"
            return f"Type “{str(args.get('text', ''))[:60]}” into {where} in {app}?"
        case "screen_menu":
            return f"Choose {' > '.join(map(str, args.get('items') or []))} in {app}?"
        case _:
            return f"Press {args.get('key')} in {app}?"


def _act_decision(args: dict[str, Any]) -> Decision:
    if private_window():
        return "deny"
    it = item(args.get("element"))
    if it is None:
        return "confirm"
    if it["role"] == "AXSecureTextField":
        return "deny"
    return "dangerous" if DANGER.search(it["name"] or "") else "confirm"


def _menu_decision(args: dict[str, Any]) -> Decision:
    if private_window():
        return "deny"
    names = [str(n) for n in (args.get("items") or [])]
    return "dangerous" if names and DANGER.search(names[-1]) else "confirm"


def _key_decision(args: dict[str, Any]) -> Decision:
    if private_window() or str(args.get("key", "")).lower() not in KEYS:
        return "deny"
    return "confirm"


@tool(
    "screen_elements",
    "See the buttons, fields, checkboxes and texts in the front app's window, numbered. "
    "Use it before screen_press / screen_set_value, and again after each action.",
    obj(),
    untrusted_output=True,
)
async def screen_elements(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    p = await ctx.run(jxa(ELEMENTS_JS, str(MAX_ITEMS)), 20, None)
    if not p.ok:
        return ToolResult(False, "Couldn't read the screen (allow Accessibility for Sasu)")
    try:
        snap = json.loads(p.out)
    except ValueError:
        return ToolResult(False, "Couldn't read the screen")
    SNAP.update(
        app=snap.get("app", ""), window=snap.get("window", ""), items=snap.get("items") or []
    )
    if private_window():
        SNAP["items"] = []
        return ToolResult(False, f"I don't operate {SNAP['app']} here, for your security.")
    lines = []
    for n, it in enumerate(SNAP["items"], 1):
        kind = ROLE_NAMES.get(it["role"], it["role"])
        if it["role"] == "AXSecureTextField":
            lines.append(f"[{n}] password field “{it['name']}” (Sasu never reads or fills this)")
            continue
        text = f"[{n}] {kind} “{it['name']}”" if it["name"] else f"[{n}] {kind}"
        if it["value"] and it["role"] != "AXStaticText":
            text += f" = “{it['value']}”"
        elif it["role"] == "AXStaticText":
            text = f"[{n}] text “{it['value'] or it['name']}”"
        if not it.get("enabled", True):
            text += " (disabled)"
        lines.append(text)
    head = f"{SNAP['app']} — {SNAP['window']}".strip(" —")
    return ToolResult(True, f"{len(lines)} items in {SNAP['app']}", head + "\n" + "\n".join(lines))


@tool(
    "screen_press",
    "Click a button, checkbox, option, link or menu button by its number from screen_elements.",
    obj(["element"], element={"type": "integer"}),
    risk="confirm",
    decide=_act_decision,
)
async def screen_press(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    it = item(args.get("element"))
    if it is None:
        return ToolResult(False, "That number isn't on screen; call screen_elements again")
    p = await ctx.run(jxa(PRESS_JS, SNAP["app"], json.dumps(it["path"]), it["role"]), 10, None)
    if not p.ok:
        return ToolResult(False, "The screen changed; call screen_elements again")
    return ToolResult(True, f"Clicked “{label(it)}”", app=SNAP["app"])


@tool(
    "screen_set_value",
    "Type text into a text field by its number from screen_elements (replaces what's there). Undoable.",
    obj(["element", "text"], element={"type": "integer"}, text={"type": "string"}),
    risk="confirm",
    decide=_act_decision,
)
async def screen_set_value(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    it = item(args.get("element"))
    if it is None:
        return ToolResult(False, "That number isn't on screen; call screen_elements again")
    if it["role"] == "AXSecureTextField":
        return ToolResult(False, "I never type into password fields")
    text = str(args.get("text", ""))[:2000]
    p = await ctx.run(jxa(SET_JS, SNAP["app"], json.dumps(it["path"]), it["role"], text), 10, None)
    if not p.ok or not p.out.strip().startswith("{"):
        return ToolResult(False, "The screen changed; call screen_elements again")
    old = json.loads(p.out).get("old", "")
    ctx.journal.record(
        ctx.turn_id,
        "screen_value",
        app=SNAP["app"],
        path=it["path"],
        role=it["role"],
        old=old,
        name=label(it),
    )
    return ToolResult(True, f"Typed into “{label(it)}”", app=SNAP["app"])


@inverse("screen_value", lambda d: f"typed into {d.get('name', 'a field')} in {d['app']}")
async def _undo_value(d: dict[str, Any], ctx: ToolContext) -> None:
    await ctx.run(jxa(SET_JS, d["app"], json.dumps(d["path"]), d["role"], d["old"]), 10, None)


@tool(
    "screen_menu",
    'Choose a menu item in the front app\'s menu bar, e.g. items=["File", "Export…"].',
    obj(["items"], items={"type": "array", "items": {"type": "string"}}),
    risk="confirm",
    decide=_menu_decision,
)
async def screen_menu(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    names = [str(n)[:80] for n in (args.get("items") or [])][:5]
    if len(names) < 2:
        return ToolResult(False, 'Give the menu and the item, like ["File", "Save"]')
    if not SNAP["app"]:
        return ToolResult(False, "Call screen_elements first")
    p = await ctx.run(jxa(MENU_JS, SNAP["app"], json.dumps(names)), 10, None)
    return ToolResult(
        p.ok,
        f"Chose {' > '.join(names)}" if p.ok else "That menu item isn't there",
        app=SNAP["app"],
    )


@tool(
    "screen_key",
    "Press a key in the front app: return, tab, shift+tab, escape, space, arrows, cmd+f, cmd+l, cmd+r, cmd+t, cmd+a.",
    obj(["key"], key={"type": "string"}),
    risk="confirm",
    decide=_key_decision,
)
async def screen_key(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    key = str(args.get("key", "")).lower()
    if key not in KEYS:
        return ToolResult(
            False, "I can only press return, tab, escape, space, arrows and a few ⌘ shortcuts"
        )
    kind, value, mod = KEYS[key]
    p = await ctx.run(jxa(KEY_JS, kind, value, mod), 5, None)
    return ToolResult(p.ok, f"Pressed {key}", app=SNAP["app"] or None)
