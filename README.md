# Transmission Discord Bot
A python Discord bot for controlling an instance of [Transmission](https://transmissionbt.com), the torrent client, using the [transmissionrpc](https://pythonhosted.org/transmissionrpc/) python library.
This bot is built on [kkrypt0nn's bot template](https://github.com/kkrypt0nn/Python-Discord-Bot-Template) and adapted from [leighmacdonald's transmission scripts](https://github.com/leighmacdonald/transmission_scripts).

## Features
* Completely self-contained: Get the python dependencies, configure a single python file, and run
* Use of `Embeds` for pretty output
* Uses reactions in lieu of text input where appropriate
* User whitelist and blacklist to control access
* Channel list to limit access to specified channel(s)
* Complete management of transfers:
	* `t/add URL` Add new torrent transfers via **URL to torrent file** or **magnet link**
	* `t/list [OPTIONS]` List existing transfers with filtering, sorting, and searching transfer names with regular expressions
	* `t/modify [OPTIONS]` Modify (pause, resume, remove, or remove and delete) transfer(s) by transfer ID(s) or using `list` options
	* `t/summary` Print simple summary of all transfers
* In-channel documentation using `t/help [COMMAND]`

## Example images
* Transfer summary

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

## To-do
* Command to print detailed information for transfer(s)
	* Complete connection information
	* Lists of transfer files, peers, trackers
* Ability to specify which files to include in download (we'll see about that; sounds clunky but maybe using file ID specifiers *e.g.* `1,3-5,8`)
* Notifications
	* To the user that added the transfer
	* Let other users opt to receive notifications for transfers they *didn't* add
* Post-download file management (*never going to happen...*)
	* Compress files (encrypted) and make available for direct download from server

## Author(s)

* Tim Wilson

## Thanks to:

* kkrypt0nn
* leighmacdonald

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE.md](LICENSE.md) file for details
