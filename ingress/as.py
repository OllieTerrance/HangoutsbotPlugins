import requests

import plugins


def _initialise(bot):
    plugins.register_user_command(["agentstats"])
    plugins.register_admin_command(["as_groups", "as_setgroup"])


def agentstats(bot, event, *args):
    """Show a leaderboard from Agent Stats: <b>agentstats <i>field time</i></b>"""
    key = bot.get_config_option("as.key")
    if not key:
        yield from bot.coro_send_message(event.conv_id, "<i>No API key configured (<b>as.key</b>).</i>")
        return
    try:
        group = bot.memory.get_by_path(["conv_data", event.conv.id_, "as"])
    except KeyError:
        group = None
    if not group:
        yield from bot.coro_send_message(event.conv_id, "<i>No Agent Stats group associated with this conversation.</i>")
        return
    try:
        field = args[0].lower()
    except IndexError:
        field = "ap"
    try:
        time = args[1].lower()
        if time not in ("now", "week", "month"):
            yield from bot.coro_send_message(event.conv_id, "<i>Time period should be one of <b>now, week, month</b>.</i>")
            return
    except IndexError:
        time = "now"
    resp = requests.get("https://api.agent-stats.com/groups/{0}/{1}".format(group, time), headers={"AS-Key": key})
    if not resp.ok:
        yield from bot.coro_send_message(event.conv_id, "Got a {} response from Agent Stats...".format(resp.status_code))
        return
    scores = {}
    try:
        for agent, progress in resp.json().items():
            if field == "guardian" and progress[field] == "-":
                continue
            scores[agent] = progress[field]
    except KeyError:
        yield from bot.coro_send_message(event.conv_id, "<i>Field <b>{0}</b> is not recognised.</i>".format(field))
        return
    parts = ["<b>Leaderboard for {0} ({1})</b>".format(field.upper(), time)]
    for agent, score in sorted(scores.items(), key=lambda s: s[1], reverse=True):
        if score == 0:
            break
        parts.append("{0}: {1}".format(agent, score))
    yield from bot.coro_send_message(event.conv_id, "\n".join(parts))


def as_setgroup(bot, event, *args):
    """Set an Agent Stats group for this conversation: <b>as_setgroup <i>group</i></b>"""
    group = args[0] if args else None
    bot.memory.set_by_path(["conv_data", event.conv.id_, "as"], group)
    yield from bot.coro_send_message(event.conv_id, "<i>Agent Stats group {0}.</i>".format("set" if group else "cleared"))

def as_groups(bot, event, *args):
    """Show available Agent Stats groups for the configured API key."""
    key = bot.get_config_option("as.key")
    if not key:
        yield from bot.coro_send_message(event.conv_id, "<i>No API key configured (<b>as.key</b>).</i>")
        return
    resp = requests.get("https://api.agent-stats.com/groups", headers={"AS-Key": key})
    if not resp.ok:
        yield from bot.coro_send_message(event.conv_id, "Got a {} response from Agent Stats...".format(resp.status_code))
        return
    parts = ["<b>Available groups</b>"]
    for group in resp.json():
        line = group["groupid"]
        if not group["groupid"] == group["groupname"]:
            line = "{0}: <i>{1}</i>".format(line, group["groupname"])
        parts.append(line)
    yield from bot.coro_send_message(event.conv_id, "\n".join(parts))
