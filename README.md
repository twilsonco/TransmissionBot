# Transmission Discord Bot
A python Discord bot for controlling an instance of [Transmission](https://transmissionbt.com), the torrent client, using the [transmissionrpc](https://pythonhosted.org/transmissionrpc/) python library.
This bot is built on [kkrypt0nn's bot template](https://github.com/kkrypt0nn/Python-Discord-Bot-Template) and adapted from [leighmacdonald's transmission scripts](https://github.com/leighmacdonald/transmission_scripts).

## Features overview
* [Interact via text channels or DMs](#channelDM)
* [Add transfers](#add)
* [Modify existing transfers](#modify)
* [Check transfer status](#status) (with optional realtime updating of output)
* [Notifications for transfer state changes](#notifications)
* [Pretty output and highly configurable](#pretty)
* [Easy setup](#setup)
* [`t/help` for usage information](#help)

## Example images
* Transfer summary (and symbol legend)

![summary](https://github.com/twilsonco/TransmissionBot/blob/master/out-summary.png)

* Modifying existing transfers

![modify](https://github.com/twilsonco/TransmissionBot/blob/master/out-modify.png)


## Install
1. Get [Transmission](https://transmissionbt.com) and setup its [web interface](https://helpdeskgeek.com/how-to/using-the-transmission-web-interface/)
2. Install python 3, [transmissionrpc](https://pypi.org/project/transmissionrpc/), and [discord.py](https://pypi.org/project/discord.py/)
3. Clone this repository using `git clone https://github.com/twilsonco/TransmissionBot`

## Configure
1. Setup your new bot on Discord:
	1. Sign up for a Discord [developer account](https://discord.com/developers/docs)
	2. Go to the [developer portal](https://discordapp.com/developers/applications), click *New Application*, pick a name and click *Create*
		* *Note the `CLIENT ID`*
	3. Click on *Bot* under *SETTINGS* and then click *Add Bot*
	4. Fill out information for the bot and **uncheck the `PUBLIC BOT` toggle**
		* *Note the bot `TOKEN`*
2. Invite the bot to your server
	1. Go to `https://discordapp.com/api/oauth2/authorize?client_id=<client_id>&scope=bot&permissions=<permissions>`
		* replace `<client_id>` with the `CLIENT ID` from above
		* replace `<permissions>` with the minimum permissions `92224`(*for send messages, manage messages, embed links, read message history, and add rections*) or administrator permissions `9` to keep things simple
	2. Invite the bot to your server
2. Configure `bot.py`
	1. Set discord options
		* `TOKEN` to your bot secret token
		* Lists of `OWNERS`, `BLACKLIST` and/or `WHITELIST` users, and `CHANNEL_IDS` on which the bot should listen for commands
			* get these ids by [enabling developer mode in your Discord client](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-) and right-clicking on a user/channel
		* Pick a `BOT_PREFIX` (default is `t/`)
	2. Set Transmission client information
		* `TSCLIENT_CONFIG` points to the Transmission web interface you already setup
		* Set `DRYRUN` to `True` to enable the discord bot to *actually* make changes to existing transfers
		* Pick a location for the logfile on line 45
		* Optionally disable logging by setting the log level to `logger.CRITICAL` which isn't used anywhere
3. Run with `python3 /path/to/TransmissionBot/bot.py` and enjoy!

## Detailed features

### <a name="channelDM">Interact via text channels or DMs</a>
* Use commands with `t/` prefix in text channel or via DM
* Via DM only, use full command name without prefix (*e.g.* `summary`)

### <a name="add">Add transfers</a>
* Simply drag a `.torrent` file into the channel on discord and it will be added and started
* Alternatively, enter a transfer magnet link or an address to a `.torrent` file using `t/add MAGNET_OR_URL`

### <a name="modify">Modify existing transfers</a>
* `t/modify` to pause, resume, verify, remove, or remove and delete one or more transfers
* Specify transfers using sequence of ids (*e.g.* 1,3,5-8), searching transfer names with regular expressions, or filtering by transfer properties (*e.g.* downloading, finished, etc.)
	* Limit number of matches using `-N` option
* Option to protext transfers using private trackers from removal
* `t/help modify` for more info

### <a name="status">Check transfer status</a>

#### List one or more transfers with pertinent information
* `t/list`
* Specify transfers using sequence of ids<sup>[1](#idseq)</sup>, searching transfer names with regular expressions, or filtering by transfer properties (e.g. downloading, finished, etc.)
* Click 🔄 reaction to update output in realtime (in-channel only, not through DM)
* `t/help list` for more info

#### Print transfer summary
* `t/summary`
* Includes overall transfer rates, amount of data transferred (based on current set of transfers), transfer counts for different states (*e.g.* downloading, finished, etc.), and list of highest seed-ratio transfers (configurable)
* Click 🔄 reaction to update output in realtime (in-channel only, not through DM)
* Use other reactions to print filtered lists of transfers
* Print symbol `t/legend`

### <a name="notifications">Notifications for transfer state changes</a>
* Print notifications regarding transfer state changes in a text channel and through DMs
* Users are notified through DM about transfers they added
* Can opt in to DM notifications for other transfers by reacting with 🔔 to `t/list` message or in-channel notifications
* Opt out of DM notifications 
	* Opt out of individual DM notifications by reacting with 🔕 to `t/list` message or either in-channel or DM notifications
	* Users opt out of all DM notifications using `t/notifications` through DM
	* Owners can disable in-channel notifications using `t/notifications` in a listened channel
* Customize what state changes are included in the configuration

### <a name="pretty">Pretty output and highly configurable</a>
* Output automatically formatted for display on desktop or mobile discord clients (in-channel only, not through DM)
* Use of Embeds and unicode symbols where appropriate.
* Remove reactions from messages when no longer necessary for prettier scroll-back (in-channel only, not through DM)
* Configure user access using whitelist, blacklist and owner list
* Protect transfers using private trackers from removal
* Set realtime update and notification frequency
* Set realtime update timeout
* Listen for commands on all or only specified text channels
* Toggle in-channel or DM interaction separately, or the notification system entirely
* Set which transfer state changes are reported in notifications with separate settings for in-channel notifications, notifications sent to users that added transfers, and users that opt into DM notifications
* Toggle dry-run to control whether transfer modifications are actually carried out

### <a name="help">`t/help` for usage information</a>
* Print help for some commands using `t/help COMMAND_NAME` (*e.g.* `t/help list`)

### <a name="setup">Easy setup</a>
0. Setup bot on Discord developer portal
1. Clone repository `git clone https://github.com/twilsonco/TransmissionBot`
2. Configure `CONFIG` in `bot.py` to your liking
3. Run bot `python3 /path/to/bot.py`
	* Bot will create `config.json`, after which you can remove or comment the definition of `CONFIG` in `bot.py` to make future updates easier

## To-do (~~implemented~~)
* Command to print detailed information for transfer(s)
	* Complete connection information
	* Lists of transfer files, peers, trackers
* ~~Add ability to verify transfer data~~
* When searching by name, update regex to include potential accented characters, eg `pokemon` would also match `pokémon`
* ~~Specify number of transfers to show when using `list` or `modify`~~
* Combine the `list` and `modify` commands in the code, with a simple parameter to specify whether or not modification is allowed
* Currently, searching by name is done with case-insensitive regex. Update to that if a user includes upper case characters, case-sensitive search is performed
* ~~Add recurring list option. Ie every five seconds replace `list` output with fresh output. This would be done by reacting to a "repeat" emoji to initiate repetition of the current search~~ (also did this for `summary`)
* ~~Add additional filtering options: stalled, error, non-zero up/down rate.
* Add shorthand for filtering options (downloading/seeding/stalled/paused become d/s/i/p etc., that's i for "idle" since s is for seeding)
* Add a `top` command that'sessentially a combination of the up/down rate filter and the repeating output features 
* Ability to refine `list` output with filter or sort using reactions; ie click a filter or sort reaction which triggers another message with additional reactions to click to apply the extra filters or sort
* Ability to specify which files to include in download (we'll see about that; sounds clunky but maybe using file ID specifiers *e.g.* `1,3-5,8`)
* ~~Notifications for when a transfer finishes/stalls/errors
	* ~~via DM to the user that added the transfer
	* ~~or by posting to the channel from which a transfer was added
	* ~~Let other users opt to receive notifications for transfers they *didn't* add
* Post-download file management (*never going to happen...*)
	* Compress files (encrypted) and make available for direct download from server via download link posted to channel or DM'd to user
* ~~Use JSON config file so that updating is non-destructive
* Add `set` command so owners can edit configuration through Discord
* ~~Add a toggle for minimalised output for better display on mobile devices. Toggle using `t/compact` as standalone command or by clicking a 📱 reaction. Store as global variable so all commands output can be affected.~~

## Author(s)

* Tim Wilson

## Thanks to:

* kkrypt0nn
* leighmacdonald

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE.md](LICENSE.md) file for details
