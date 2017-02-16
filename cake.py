from collections import Counter
import logging
import re

from emoji import emojize

import plugins
import utils


log = logging.getLogger(__name__)


def _get_users(bot, conv):
    users = bot.get_users_in_conversation(conv.id_)
    # Handle synced rooms.
    if bot.get_config_option("syncing_enabled"):
        for sync in bot.get_config_option("sync_rooms", []):
            if conv.id_ in sync:
                for room in sync:
                    users += bot.get_users_in_conversation(room)
    return dict((user.id_.chat_id, user) for user in users)

def _get_names(bot, users):
    names = {}
    for uid, user in users.items():
        names[uid] = []
        if not user.full_name == "Unknown":
            names[uid].append(user.full_name)
        try:
            names[uid].append(bot.memory.get_by_path(["user_data", user.id_.chat_id, "nickname"]))
        except KeyError:
            pass
    return names

def _format_name(name):
    return re.sub(r"[^0-9a-z]+", "", utils.remove_accents(name).lower())

def _match_name(search, names, angel):
    search = _format_name(search)
    exact = []
    substr = []
    for user, nicks in names.items():
        if user == angel:
            continue
        matches = [_format_name(name) for name in nicks]
        if search == user or search in matches:
            exact.append(user)
        elif any(search in match for match in matches):
            substr.append(user)
    if len(exact) == 1:
        return exact[0]
    elif exact:
        raise ValueError("Multiple people with that name!  Maybe try a nickname instead?")
    elif len(substr) == 1:
        return substr[0]
    elif substr:
        raise ValueError("Multiple possible matches for that name!  Try being more specific.")
    else:
        raise ValueError("No matches for that name...")

def _show_name(uid, names):
    try:
        return names[uid][0]
    except IndexError:
        return "<i>{0}</i>".format(uid)


def _initialise(bot):
    plugins.register_user_command(["cake"])


def cake(bot, event, *args):
    """Cake for all!  Be a cake angel -- reward someone with a slice using <b>cake give [name]</b>."""
    cakes = bot.conversation_memory_get(event.conv_id, "cake") or []
    users = _get_users(bot, event.conv)
    names = _get_names(bot, users)
    msg = None
    if not args:
        if cakes:
            angels = Counter()
            hoarders = Counter()
            for angel, hoarder in cakes:
                angels[angel] += 1
                hoarders[hoarder] += 1
            parts = ["<b>Top cake hoarders:</b>"]
            for hoarder, count in sorted(hoarders.items(), key=lambda t: t[1], reverse=True):
                parts.append("{0}: :cake:x{1}".format(_show_name(hoarder, names), count))
            parts.append("<b>Top cake angels:</b>")
            for angel, count in sorted(angels.items(), key=lambda t: t[1], reverse=True):
                parts.append("{0}: :cake:x{1}".format(_show_name(angel, names), count))
            msg = "\n".join(parts)
        else:
            msg = "No :cake: given out yet..."
    elif args[0] == "give" and len(args) > 1:
        who = " ".join(args[1:])
        try:
            user = _match_name(who, names, event.user)
        except ValueError as e:
            yield from bot.coro_send_message(event.conv_id, str(e))
            return
        angel, hoarder = event.user.id_.chat_id, user
        log.debug("{0} gave cake to {1}".format(angel, hoarder))
        cakes.append([angel, hoarder])
        bot.conversation_memory_set(event.conv_id, "cake", cakes)
        msg = ":heart_eyes: {0} gave a slice of :cake: to {1}!".format(_show_name(angel, names), _show_name(hoarder, names))
    if msg:
        yield from bot.coro_send_message(event.conv_id, emojize(msg, use_aliases=True))
