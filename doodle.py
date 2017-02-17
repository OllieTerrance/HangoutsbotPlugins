import re
import shlex

import requests

import plugins


def _parse_args(bot, event):
    args = shlex.split(event.text)
    try:
        aliases = bot.memory.get_by_path(["bot.command_aliases"])
    except KeyError:
        aliases = ["/bot"]
    if args[0] in aliases:
        args.pop(0)
    return args


def _initialise(bot):
    plugins.register_user_command(["doodle", "doodle_email"])


def doodle(bot, event, *args):
    ("""Create a new Doodle poll: <b>doodle [<i>key</i>=<i>"value"</i> ...] [+<i>flag</i> ...]</b>\n"""
     """Keys: <i>title, description, options</i>\n"""
     """Flags: <i>text, yesno, hidden</i>\n"""
     """For date <i>options</i>, give a comma-separated list of YYYYMMDD or YYYYMMDDHHMM choices.  """
     """Otherwise, include the <i>+text</i> flag for free text choices.\n"""
     """Example: <i>doodle title="My Event" description="A cool event." options="20160101,20160102" +hidden</i>\n"""
     """You'll need to give Doodle an email address first -- use the <b>doodle_email</b> command to set one.""")
    args = _parse_args(bot, event)
    kwargs = {"type": "DATE", "optionsMode": "date", "ifNeedBe": "true", "hidden": "false"}
    for arg in args[1:]:
        if arg[0] == "+":
            flag = arg[1:]
            if flag == "text":
                kwargs.update({"type": "TEXT",
                               "optionsMode": "text"})
            elif flag == "yesno":
                kwargs["ifNeedBe"] = "false"
            elif flag == "hidden":
                kwargs["hidden"] = "true"
            else:
                yield from bot.coro_send_message(event.conv_id, "<i>Didn't recognise flag <b>{0}</b>.</i>".format(flag))
                return
        elif "=" in arg:
            key, val = arg.split("=", 1)
            if key == "options":
                key = "options[]"
                val = val.split(",")
            elif key not in ("title", "description"):
                yield from bot.coro_send_message(event.conv_id, "<i>Didn't recognise key <ib{0}</b>.</i>".format(key))
                return
            kwargs[key] = val
        else:
            yield from bot.coro_send_message(event.conv_id, "<i>Couldn't decode arg <b>{0}</b>.</i>".format(arg))
            return
    if "title" not in kwargs or "options[]" not in kwargs:
        yield from bot.coro_send_message(event.conv_id, "<i>Needs a <b>title</b> and <b>options</b>.  "
                                                        "See <b>help doodle</b> for the syntax.</i>")
        return
    if kwargs["type"] == "DATE" and not all(re.match(r"\d{8}(\d{4})?", o) for o in kwargs["options[]"]):
        yield from bot.coro_send_message(event.conv_id, "<i>Expecting date options but wrong got format "
                                                        "(use <b>+text</b> if not dates).</i>")
        return
    try:
        email = bot.memory.get_by_path(["user_data", event.user.id_.chat_id, "doodle_email"])
    except KeyError:
        yield from bot.coro_send_message(event.conv_id, "<i>No Doodle email set (see <b>help doodle_email</b>).</i>")
        return
    kwargs.update({"initiatorEmail": email, "initiatorAlias": event.user.full_name})
    resp = requests.post("https://doodle.com/np/new-polls/", data=kwargs)
    if not resp.ok:
        yield from bot.coro_send_message(event.conv_id, "Got a {} response from Doodle...".format(resp.status_code))
        return
    json = resp.json()
    yield from bot.coro_send_message(event.conv_id, """Doodle created! <a href="https://doodle.com/poll/{0}">"""
                                                    "https://doodle.com/poll/{0}</a>".format(json["id"]))
    user_1to1 = yield from bot.get_1to1(event.user_id.chat_id)
    yield from bot.coro_send_message(user_1to1, "Here's the administration link for your Doodle poll: "
                                                """<a href="https://doodle.com/poll/{0}{1}/admin">"""
                                                "https://doodle.com/poll/{0}{1}/admin</a>"
                                                .format(json["id"], json["adminKey"]))


def doodle_email(bot, event, *args):
    """Set an email address to be used for Doodle poll administration: <b>doodle_email <i>email</i></b>"""
    if args:
        bot.memory.set_by_path(["user_data", event.user.id_.chat_id, "doodle_email"], args[0])
        bot.memory.save()
        yield from bot.coro_send_message(event.conv_id, "<i>Your Doodle email has been set.</i>")
    else:
        try:
            email = bot.memory.set_by_path(["user_data", event.user.id_.chat_id, "doodle_email"])
            yield from bot.coro_send_message(event.conv_id, "<i>Your Doodle email is set.  You can update it "
                                                            "with <b>doodle_email [new email]</b>.</i>")
        except KeyError:
            yield from bot.coro_send_message(event.conv_id, "<i>No Doodle email on record.  You can set one "
                                                            "with <b>doodle_email [new email]</b>.</i>")
