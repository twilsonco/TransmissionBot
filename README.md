# Transmission Discord Bot
A self-hosted python [Discord.py](https://github.com/Rapptz/discord.py) bot for controlling an instance of [Transmission](https://transmissionbt.com), the bittorrent client,  from a **private** Discord server.
Using the [transmissionrpc](https://pythonhosted.org/transmissionrpc/) python library, this bot is built on [kkrypt0nn's bot template](https://github.com/kkrypt0nn/Python-Discord-Bot-Template) and adapted from [leighmacdonald's transmission scripts](https://github.com/leighmacdonald/transmission_scripts).

## Features overview
* [Interact via text channels or DMs](#channelDM)
* [Add transfers](#add)
* [Modify existing transfers](#modify)
* [Check transfer status](#status) (with optional realtime updating of output)
* [Notification system for transfer state changes](#notifications)
* [Pretty output and highly configurable](#pretty)
* [Easy setup](#setup)
* [`t/help` for usage information](#help)

## Example images
* Various images of TransmissionBot interaction through DM (light mode images) and in-channel (dark mode images)
* Going left to right, top to bottom for light mode images
	* Adding new transfers from torrent file (can also add magnet links or a url to a torrent file)
	* Listing transfers (with filtering, sorting, regex searching by name and tracker, etc.)
	* Modifying transfers
		* All transfers for pause/resume
		* Or by transfer name (with filtering etc.) for pause/resume/remove/remove-delete/verify, with confirmation for removal
	* Notifications via DM (can opt-in to notificaitons for any transfers, and users get notifications for transfers they added)
	* Transfer summary, followed up by listing running tranfers via reaction click
* Dark mode images
	* Mostly the same stuff but with commands send in-channel
	* Note that reactions are removed when no longer necessary to keep the channel clean
	* In-channel notifications for a variety of (customizable) transfer state changes
	* Second dark mode image: list tranfers by name regex search, followed up by summary of listed transfers via reaction click
	

![summary](https://github.com/twilsonco/TransmissionBot/blob/master/example%20image%20collage.png?raw=true)


## Install
1. Get [Transmission](https://transmissionbt.com) and setup its [web interface](https://helpdeskgeek.com/how-to/using-the-transmission-web-interface/)
2. Install python 3, [transmissionrpc](https://pypi.org/project/transmissionrpc/), pytz, and [discord.py](https://pypi.org/project/discord.py/)
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
		* replace `<permissions>` with the minimum permissions `93248`(*for read/send/manage messages, embed links, read message history, and add rections*) or administrator permissions `9` to keep things simple
	2. Invite the bot to your server
2. Configure `config.json` file starting with `config-sample.json`
	* *All values with* `ids` *are referring to Discord IDs, which are 18-digit numbers you can find by following [these instructions](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-)*
	* Values that MUST be configured: `bot_token`, `listen_channel_ids` if you want to use in-channel, `notification_channel_id` if you wish to use in-channel notifications, `owner_user_ids` at least with your Discord user id, `tsclient` with information pointing to your Transmission remote gui, `whitelist_user_ids` at least with your Discord user id and any other Discord users you wish to be able to use the bot.
	* After first run, a `config.json` file will be created in the same directory as `bot.py`. This file should then be used to make any configuration changes, and the definition of `CONFIG` in `bot.py` should be commented out or removed.
2. Configure logging in `bot.py`
	* Pick a location for the logfile on line 124; default is the same directory where bot.py resides
	* Optionally disable logging by setting the log level to `logging.CRITICAL` which isn't used anywhere
3. Run with `python3 /path/to/TransmissionBot/bot.py` and enjoy!

## Detailed features

### <a name="channelDM">Interact via text channels or DMs</a>
* Use commands with `t/` prefix in text channel or via DM
* Via DM only, use commands without prefix (*e.g.* `summary` or `s` rather than `t/summary` or `t/s`)
* *Why use DMs vs in-channel?*
	* Use DMs for user privacy or to keep the in-channel usage clean
	* Use in-channel when privacy isn't an issue, or if you wish to take advantage of auto-updating output
	* *Note: you can configure the bot to only respond to DMs or in-channel commands, so it can be a fully DM-based method of controlling Transmission if you wish*

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

### <a name="notifications">Notification system for transfer state changes</a>
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
	* Control whether whitelisted users are able to remove and/or delete transfers (with optional override specifically for transfers added by the user)
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
	
###Configuration
```javascript
{
    "DM_compact_output_user_ids": [], # users that will get compact output via DM (changed by t/compact command)
    "blacklist_user_ids": [], # discord users disallowed to use bot
    "bot_prefix": "t/", # bot command prefix
    "bot_token": "BOT-TOKEN", # bot token
    "delete_command_message_private_torrent": true, # deletes command message if that message contains one or more torrent files that use a private tracker
    "delete_command_messages": false, # delete command messages from users
    "dryrun": false, # if true, no changes are actually applied to transfers
    "listen_DMs": true, # listen for commands via DM to the bot
    "listen_all_channels": false, # if true, listen for commands in all text channels
    "listen_channel_ids": [], # channels in which to listen for commands
    "logo_url": "https://iyanovich.files.wordpress.com/2009/04/transmission-logo.png", # URL to logo that appears in some output
    "notification_DM_opt_out_user_ids": [], # DON'T MODIFY (used by bot to record users that have opted out of receiving DM notifications)
    "notification_channel_id": 0, # id of channel to which in-channel notificatations will be posted
    "notification_enabled": true, # if False, in-channel and DM notifications are disabled
    "notification_enabled_in_channel": true, # if False, in-channel notifications are disabled, but DM notifications will still work
    "notification_freq": 300, # number of seconds between checking transfers and posting notifications
    "notification_states": { # determines the types of transfer state changes that are reported in notifications...
        "added_user": [ # ...and DM notifications to users that added transfers
            "removed",
            "error",
            "downloaded",
            "finished"
        ],
        "in_channel": [ # ...for in-channel notifications, (this is the full list of potential state changes)
            "new",
            "removed",
            "error",
            "downloaded",
            "finished"
        ],
        "notified_users": [ # ...DM notifications for users that opted in to DM notifications for transfer(s)
            "removed",
            "error",
            "downloaded",
            "stalled",
            "unstalled",
            "finished",
            "stopped",
            "started"
        ]
    },
    "owner_user_ids": [], # discord users given full access
    "private_transfer_protection_added_user_override": true, # if true, the user that added a private transfer can remove it regardless of 'private_transfers_protected'
    "private_transfer_protection_bot_owner_override": false, # similar to 'private_transfer_protection_added_user_override', but allows bot owners to delete private transfers
    "private_transfers_protected": true, # prevent transfers on private trackers from being removed
    "reaction_wait_timeout": 7200, # seconds the bot should wait for a reaction to be clicked by a user
    "repeat_cancel_verbose": true, # if true, print message when auto-update is canceled for a message
    "repeat_freq": 10, # number of seconds between updating an auto-update message
    "repeat_freq_DM_by_user_ids": {}, # use t/repeatfreq to set autoupdate frequency over DM on a per-user basis
    "repeat_timeout": 3600, # number of seconds before an auto-update message times out
    "repeat_timeout_DM_by_user_ids": {}, # same but for autoupdate timeout
    "repeat_timeout_verbose": true, # if true, print message when auto-update message times out and stops updating
    "summary_num_top_ratio": 0, # number of top seed-ratio transfers to show at the bottom of the summary output
    "tsclient": { # information for transmission remote web gui
        "host": "127.0.0.1",
        "password": "password",
        "port": 9091,
        "user": "admin"
    },
    "whitelist_added_user_remove_delete_override": true, # if true, override both 'whitelist_user_can_remove' and 'whitelist_user_can_delete' allowing whitelisted users to remove and delete transfers they added
    "whitelist_user_can_delete": false, # if true, whitelisted users can remove and delete any transfer
    "whitelist_user_can_remove": false, # if true, whitelisted users can remove any transfer
    "whitelist_user_ids": [] # discord users allowed to use bot
}
```

## To-do (~~implemented~~)
* Comment and clean up code so people can read/trust it
* Command to print detailed information for transfer(s)
	* Complete connection information
	* Lists of transfer files, peers, trackers
* ~~Add ability to verify transfer data~~
* When searching by name, update regex to include potential accented characters, eg `pokemon` would also match `pokémon`
* ~~Specify number of transfers to show when using `list` or `modify`~~
* Combine the `list` and `modify` commands in the code, with a simple parameter to specify whether or not modification is allowed
* Currently, searching by name is done with case-insensitive regex. Update to that if a user includes upper case characters, case-sensitive search is performed
* ~~Add recurring list option. Ie every five seconds replace `list` output with fresh output. This would be done by reacting to a "repeat" emoji to initiate repetition of the current search~~ (also did this for `summary`)
* ~~Add additional filtering options: stalled, error, non-zero up/down rate.~~
* Add shorthand for filtering options (downloading/seeding/stalled/paused become d/s/i/p etc., that's i for "idle" since s is for seeding)
* Add a `top` command that'sessentially a combination of the up/down rate filter and the repeating output features 
* Ability to refine `list` output with filter or sort using reactions; ie click a filter or sort reaction which triggers another message with additional reactions to click to apply the extra filters or sort
* Ability to specify which files to include in download (we'll see about that; sounds clunky but maybe using file ID specifiers *e.g.* `1,3-5,8`)
* ~~Notifications for when a transfer finishes/stalls/errors~~
	* ~~via DM to the user that added the transfer~~
	* ~~or by posting to the channel from which a transfer was added~~
	* ~~Let other users opt to receive notifications for transfers they *didn't* add~~
* Post-download file management (*never going to happen...*)
	* Compress files (encrypted) and make available for direct download from server via download link posted to channel or DM'd to user
* ~~Use JSON config file so that updating is non-destructive~~
* Add `set` command so owners can edit configuration through Discord
* ~~Add a toggle for minimalised output for better display on mobile devices. Toggle using `t/compact` as standalone command or by clicking a 📱 reaction. Store as global variable so all commands output can be affected.~~

## Author(s)

* Tim Wilson

## Thanks to:

* Rapptz
* kkrypt0nn
* leighmacdonald

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE.md](LICENSE.md) file for details
