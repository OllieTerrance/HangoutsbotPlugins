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
    ("""Create a new Doodle poll: <b>doodle "title" "option" ["option" ...] [+yesno] [+hidden]</b>\n"""
     """Use quotes to contain spaces.  For date options, use YYYYMMDD or YYYYMMDDHHMM format.\n"""
     """Example: <i>doodle "My Event" 20160101 20160102 201601013 +hidden</i>\n"""
     """You'll need to give Doodle an email address first -- use the <b>doodle_email</b> command to set one.""")
    args = _parse_args(bot, event)
    kwargs = {"type": "TEXT", "optionsMode": "text", "ifNeedBe": "true", "hidden": "false", "options[]": []}
    for arg in args[1:]:
        if arg[0] == "+":
            flag = arg[1:]
            if flag == "yesno":
                kwargs["ifNeedBe"] = "false"
            elif flag == "hidden":
                kwargs["hidden"] = "true"
            else:
                yield from bot.coro_send_message(event.conv_id, "<i>Didn't recognise flag <b>{0}</b>.</i>".format(flag))
                return
        elif "title" in kwargs:
            kwargs["options[]"].append(arg)
        else:
            kwargs["title"] = arg
    if "title" not in kwargs or not kwargs["options[]"]:
        yield from bot.coro_send_message(event.conv_id, "<i>Needs a title and at least one option.</i>")
        return
    if all(re.match(r"\d{8}(\d{4})?", o) for o in kwargs["options[]"]):
        kwargs.update({"type": "DATE", "optionsMode": "date"})
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
