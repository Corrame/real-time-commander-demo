from game.models import Battlefield


def render_state(bf: Battlefield) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"[Tick {bf.tick}/{bf.max_tick}] Location: {bf.location} | Policy: {bf.commander_policy}")
    lines.append("-" * 72)
    lines.append("Friendly:")
    for u in bf.friendly_units:
        dead = " [DOWN]" if not u.is_alive() else ""
        lines.append(f"  - {u.short()}{dead}")

    lines.append("")
    lines.append("Enemy:")
    for e in bf.enemy_units:
        dead = " [DOWN]" if not e.is_alive() else ""
        lines.append(f"  - {e.short()}{dead}")

    lines.append("")
    lines.append("Situation:")
    for s in bf.global_status:
        lines.append(f"  - {s}")

    if bf.log:
        lines.append("")
        lines.append("Recent log:")
        for item in bf.log[-8:]:
            lines.append(f"  * {item}")

    lines.append("=" * 72)
    return "\n".join(lines)
