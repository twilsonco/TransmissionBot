""""
Copyright © twilsonco 2020
Description:
This is a discord bot to manage torrent transfers through the Transmission transmissionrpc python library.

Version: 1.2
"""

import discord
import asyncio
import aiohttp
import json
from json import dumps, load
import subprocess
from discord.ext.commands import Bot
from discord.ext import commands
from platform import python_version
import os
import sys
from os.path import expanduser, join, exists, isdir, isfile
import re
import datetime
import pytz
import platform
import secrets
import transmissionrpc
import logging
import base64
import random
from enum import Enum

# BEGIN USER CONFIGURATION

CONFIG_DIR = os.path.dirname(os.path.realpath(__file__))

"""
Bot configuration:
1. set this to you liking
2. run the bot, which will make a config.json file containing this configuration info
3. comment or remove the configuration below, as the config.json will be used instead (this also makes updating to new versions easier)
"""
CONFIG = {
    "tsclient": { # information for transmission remote web gui
		'host': "192.168.0.2",
		'port': 9091,
		'user': "USERNAME",
		'password': "PASSWORD"
	},
    "whitelist_user_ids": [], # discord users allowed to use bot
    "blacklist_user_ids": [], # discord users disallowed to use bot
    "owner_user_ids": [], # discord users given full access
	 "delete_command_messages": False, # delete command messages from users
	"delete_command_message_private_torrent": True, # deletes command message if that message contains one or more torrent files that use a private tracker
	"private_transfers_protected": True, # prevent transfers on private trackers from being removed
	"private_transfer_protection_added_user_override": True, # if true, the user that added a private transfer can remove it regardless of 'private_transfers_protected'
	"whitelist_user_can_remove": True, # if true, whitelisted users can remove any transfer
	"whitelist_user_can_delete": True, # if true, whitelisted users can remove and delete any transfer
	"whitelist_added_user_remove_delete_override": True, # if true, override both 'whitelist_user_can_remove' and 'whitelist_user_can_delete' allowing whitelisted users to remove and delete transfers they added
    "bot_prefix": "t/", # bot command prefix
    "bot_token": "BOT_TOKEN", # bot token
    "dryrun": False, # if true, no changes are actually applied to transfers
    "listen_channel_ids": [], # channels in which to listen for commands
	"listen_all_channels": False, # if true, listen for commands in all text channels
	"listen_DMs": True, # listen for commands via DM to the bot
    "logo_url": "https://iyanovich.files.wordpress.com/2009/04/transmission-logo.png", # URL to logo that appears in some output
    "notification_channel_id": 'NOTIFICATION_CHANNEL_ID', # channel to which in-channel notificatations will be posted
    "notification_enabled": True, # if False, in-channel and DM notifications are disabled
	"notification_enabled_in_channel": True, # if False, in-channel notifications are disabled, but DM notifications will still work
    "notification_freq": 300, # number of seconds between checking transfers and posting notifications
	"notification_reaction_check_factor": 2, # determines how long DM notification subscription reactions will be monitored on in-channel and DM notifications; they're monitored for (notification_reaction_check_factor X notification_freq) seconds
	"notification_DM_opt_out_user_ids": [], # DON'T MODIFY (used by bot to record users that have opted out of receiving DM notifications)
	"notification_states":{ # determines the types of transfer state changes that are reported in notifications...
		"in_channel": # ...for in-channel notifications, (this is the full list of potential state changes)
		[
			"new",
			"removed",
			"error",
			"downloaded",
			"stalled",
			"unstalled",
			"finished",
			"stopped",
			"started"
		],
		"notified_users": # ...DM notifications for users that opted in to DM notifications for transfer(s)
		[
			"removed",
			"error",
			"downloaded",
			"stalled",
			"unstalled",
			"finished",
			"stopped",
			"started"
		],
		"added_user":# ...and DM notifications to users that added transfers
		[
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
    "repeat_cancel_verbose": True, # if true, print message when auto-update is canceled for a message
    "repeat_freq": 2, # number of seconds between updating an auto-update message
    "repeat_timeout": 3600, # number of seconds before an auto-update message times out
    "repeat_timeout_verbose": True, # if true, print message when auto-update message times out
    "summary_num_top_ratio": 5 # number of top seed-ratio transfers to show at the bottom of the summary output
}

TSCLIENT_CONFIG = None

# logging.basicConfig(format='%(asctime)s %(message)s',filename=join(expanduser("~"),'ts_scripts.log'))
logging.basicConfig(format='%(asctime)s %(message)s',filename=join(CONFIG_DIR,'transmissionbot.log'))
logger = logging.getLogger('transmission_bot')
logger.setLevel(logging.INFO) # set according to table below. values LESS than the set value will be ignored

"""
Level		Numeric value
__________________________
CRITICAL	50
ERROR		40
WARNING		30
INFO		20
DEBUG		10
NOTSET		0
"""

# END USER CONFIGURATION

# for storing config and transfer list

CONFIG_JSON = join(CONFIG_DIR, "config.json")
LOCK_FILE = join(CONFIG_DIR, "lock")




DEFAULT_REASON="TransmissionBot"

def lock(lockfile=LOCK_FILE):
	""" Wait for LOCK_FILE to not exist, then create it to lock """
	from time import sleep
	from random import random
	from pathlib import Path
	lock_file = Path(lockfile)
		
	logger.debug("Creating lock file '{}'".format(lockfile))
	
	while lock_file.is_file():
		logger.debug("Config file locked, waiting...")
		sleep(0.5)
		
	logger.debug("Lock file created '{}'".format(lockfile))
	lock_file.touch()
	
def unlock(lockfile=LOCK_FILE):
	""" Delete LOCK_FILE """
	from pathlib import Path
	lock_file = Path(lockfile)

	logger.debug("Removing lock file '{}'".format(lockfile))
	
	if lock_file.is_file():
		lock_file.unlink()
		logger.debug("Lock file removed '{}'".format(lockfile))
	else:
		logger.debug("Lock file didn't exist '{}'".format(lockfile))

def mkdir_p(path):
	"""mimics the standard mkdir -p functionality when creating directories

	:param path:
	:return:
	"""
	try:
		makedirs(path)
	except OSError as exc:  # Python >2.5
		if exc.errno == errno.EEXIST and isdir(path):
			pass
		else:
			raise

def generate_json(json_data=None, path=None, overwrite=False):
	"""Generate a new config file based on the value of the CONFIG global variable.

	This function will cause a fatal error if trying to overwrite an exiting file
	without setting overwrite to True.

	:param overwrite: Overwrite existing config file
	:type overwrite: bool
	:return: Create status
	:rtype: bool
	"""
	if not path or not json_data:
		return False
	if exists(path) and not overwrite:
		logger.fatal("JSON file exists already! (Set overwite option to overwrite)")
		return False
	if not exists(os.path.dirname(path)):
		mkdir_p(os.path.dirname(path))
	with open(path, 'w') as cf:
		lock()
		cf.write(dumps(json_data, sort_keys=True, indent=4, separators=(',', ': ')))
		unlock()
	return True


def load_json(path=None):
	"""Load a config file from disk using the default location if it exists. If path is defined
	it will be used instead of the default path.

	:param path: Optional path to config file
	:type path: str
	:return: Load status
	:rtype: bool
	"""
	if not path:
		return False
	if exists(path):
		jsonContents = load(open(path))
		logger.debug("Loaded JSON file: {}".format(path))
		return jsonContents
	return False


CONFIG = load_json(CONFIG_JSON) if exists(CONFIG_JSON) else None # will be read from CONFIG_JSON

class OutputMode(Enum):
	AUTO = 1
	DESKTOP = 2
	MOBILE = 3
	
OUTPUT_MODE = OutputMode.AUTO

COMPACT_OUTPUT = False

REPEAT_MSG_IS_PINNED = False
REPEAT_MSGS = {}
	# REPEAT_MSGS[msg_key] = {
	# 	'msgs':msg_list,
	# 	'command':command,
	# 	'context':context,
	# 	'content':content,
	# 	'pin_to_bottom':False,
	# 	'reprint': False,
	# 	'freq':CONFIG['repeat_freq'],
	# 	'timeout':CONFIG['repeat_timeout'],
	# 	'timeout_verbose':REPEAT_TIMEOUT,
	# 	'cancel_verbose':CONFIG['repeat_cancel_verbose'],
	# 	'start_time':datetime.datetime.now(),
	# 	'do_repeat':True
	# }

TORRENT_JSON = join(CONFIG_DIR, "transfers.json")

# list of transfer information to be stored in a separate file, used for
# checking for transfer state stanges for the notification system
# here's the structure, a dict with a dict for each transfer with select information.
# this will be a local var, since it's only needed in the function that checks for changes.
# TORRENT_LIST = {
# 	'hashString':{
# 		'name':t.name,
# 		'error':t.error,
#		'errorString':t.errorString,
# 		'status':t.status,
# 		'isStalled':t.isStalled,
#		'progress':t.progress
# 	}
# }

TORRENT_ADDED_USERS = {}
TORRENT_NOTIFIED_USERS = {}
TORRENT_OPTOUT_USERS = {}

async def determine_prefix(bot, message):
	return CONFIG['bot_prefix']

client = Bot(command_prefix=determine_prefix)
TSCLIENT = None
MAKE_CLIENT_FAILED = False


# Begin transmissionrpc functions, lovingly taken from https://github.com/leighmacdonald/transmission_scripts

filter_names = ( # these are the filters accepted by transmissionrpc
	"all",
	"active",
	"downloading",
	"seeding",
	"stopped",
	"finished"
)

filter_names_extra = ( # these are extra filters I've added
	"stalled",
	"private",
	"public",
	"error",
	'err_none', 
	'err_tracker_warn', 
	'err_tracker_error', 
	'err_local',
	'verifying', 
	'queued',
	"running" # running means a non-zero transfer rate, not to be confused with "active"
)

filter_names_full = filter_names + filter_names_extra

sort_names = (
	"id",
	"progress",
	"name",
	"size",
	"ratio",
	"speed",
	"speed_up",
	"speed_down",
	"status",
	"queue",
	"age",
	"activity"
)

class TSClient(transmissionrpc.Client):
	""" Basic subclass of the standard transmissionrpc client which provides some simple
	helper functionality.
	"""

	def get_torrents_by(self, sort_by=None, filter_by=None, reverse=False, filter_regex=None, id_list=None, num_results=None):
		"""This method will call get_torrents and then perform any sorting or filtering
		actions requested on the returned torrent set.

		:param sort_by: Sort key which must exist in `Sort.names` to be valid;
		:type sort_by: str
		:param filter_by:
		:type filter_by: str
		:param reverse:
		:return: Sorted and filter torrent list
		:rtype: transmissionrpc.Torrent[]
		"""
		if id_list:
			torrents = self.get_torrents(ids=id_list)
		else:
			torrents = self.get_torrents()
			if filter_regex:
				regex = re.compile(filter_regex, re.IGNORECASE)
				torrents = [tor for tor in torrents if regex.search(tor.name)]
			if filter_by:
				for f in filter_by.split():
					if f == "active":
						torrents = [t for t in torrents if not t.isStalled and t.rateDownload + t.rateUpload == 0]
					elif f in filter_names:
						torrents = filter_torrents_by(torrents, key=getattr(Filter, filter_by))
					elif f == "verifying":
						torrents = [t for t in torrents if "check" in t.status]
					elif f == "queued":
						torrents = [t for t in torrents if "load pending" in t.status]
					elif f == "stalled":
						torrents = [t for t in torrents if t.isStalled]
					elif f == "private":
						torrents = [t for t in torrents if t.isPrivate]
					elif f == "public":
						torrents = [t for t in torrents if not t.isPrivate]
					elif f == "error":
						torrents = [t for t in torrents if t.error != 0]
					elif f == "err_none":
						torrents = [t for t in torrents if t.error == 0]
					elif f == "err_tracker_warn":
						torrents = [t for t in torrents if t.error == 1]
					elif f == "err_tracker_error":
						torrents = [t for t in torrents if t.error == 2]
					elif f == "err_local":
						torrents = [t for t in torrents if t.error == 3]
					elif f == "running":
						torrents = [t for t in torrents if t.rateDownload + t.rateUpload > 0]
					else:
						continue
				if sort_by is None:
					if "downloading" in filter_by or "seeding" in filter_by or "running" in filter_by:
						sort_by = "speed"
					elif "stopped" in filter_by or "finished" in filter_by:
						sort_by = "ratio"
			if sort_by:
				torrents = sort_torrents_by(torrents, key=getattr(Sort, sort_by), reverse=reverse)
			if num_results and num_results < len(torrents):
				torrents = torrents[-num_results:]
		return torrents
		
def make_client():
	""" Create a new transmission RPC client

	If you want to parse more than the standard CLI arguments, like when creating a new customized
	script, you can append your options to the argument parser.

	:param args: Optional CLI args passed in.
	:return:
	"""
	global MAKE_CLIENT_FAILED
	tsclient = None
	lock()
	try:
		tsclient = TSClient(
			TSCLIENT_CONFIG['host'],
			port=TSCLIENT_CONFIG['port'],
			user=TSCLIENT_CONFIG['user'],
			password=TSCLIENT_CONFIG['password']
		)
		MAKE_CLIENT_FAILED = False
	except Exception as e:
		logger.error("Failed to make TS client: {}".format(e))
		MAKE_CLIENT_FAILED = True
	finally:
		unlock()
		return tsclient

		
def reload_client():
	global TSCLIENT
	TSCLIENT = make_client()


class Filter(object):
	"""A set of filtering operations that can be used against a list of torrent objects"""

	# names = (
	# 	"all",
	# 	"active",
	# 	"downloading",
	# 	"seeding",
	# 	"stopped",
	# 	"finished"
	# )
	names = filter_names

	@staticmethod
	def all(t):
		return t

	@staticmethod
	def active(t):
		return t.rateUpload > 0 or t.rateDownload > 0

	@staticmethod
	def downloading(t):
		return t.status == 'downloading'

	@staticmethod
	def seeding(t):
		return t.status == 'seeding'

	@staticmethod
	def stopped(t):
		return t.status == 'stopped'

	@staticmethod
	def finished(t):
		return t.status == 'finished'

	@staticmethod
	def lifetime(t):
		return t.date_added


def filter_torrents_by(torrents, key=Filter.all):
	"""

	:param key:
	:param torrents:
	:return: []transmissionrpc.Torrent
	"""
	filtered_torrents = []
	for torrent in torrents:
		if key(torrent):
			filtered_torrents.append(torrent)
	return filtered_torrents
	
class Sort(object):
	""" Defines methods for sorting torrent sequences """

	# names = (
	# 	"id",
	# 	"progress",
	# 	"name",
	# 	"size",
	# 	"ratio",
	# 	"speed",
	# 	"speed_up",
	# 	"speed_down",
	# 	"status",
	# 	"queue",
	# 	"age",
	# 	"activity"
	# )
	names = sort_names

	@staticmethod
	def activity(t):
		return t.date_active

	@staticmethod
	def age(t):
		return t.date_added

	@staticmethod
	def queue(t):
		return t.queue_position

	@staticmethod
	def status(t):
		return t.status

	@staticmethod
	def progress(t):
		return t.progress

	@staticmethod
	def name(t):
		return t.name.lower()

	@staticmethod
	def size(t):
		return -t.totalSize

	@staticmethod
	def id(t):
		return t.id

	@staticmethod
	def ratio(t):
		return t.ratio

	@staticmethod
	def speed(t):
		return t.rateUpload + t.rateDownload

	@staticmethod
	def speed_up(t):
		return t.rateUpload

	@staticmethod
	def speed_down(t):
		return t.rateDownload


def sort_torrents_by(torrents, key=Sort.name, reverse=False):
	return sorted(torrents, key=key, reverse=reverse)
	
# def print_torrent_line(torrent, colourize=True):
#	 name = torrent.name
#	 progress = torrent.progress / 100.0
#	 print("[{}] [{}] {} {}[{}/{}]{} ra: {} up: {} dn: {} [{}]".format(
#		 white_on_blk(torrent.id),
#		 find_tracker(torrent),
#		 print_pct(torrent) if colourize else name.decode("latin-1"),
#		 white_on_blk(""),
#		 red_on_blk("{:.0%}".format(progress)) if progress < 1 else green_on_blk("{:.0%}".format(progress)),
#		 magenta_on_blk(natural_size(torrent.totalSize)),
#		 white_on_blk(""),
#		 red_on_blk(torrent.ratio) if torrent.ratio < 1.0 else green_on_blk(torrent.ratio),
#		 green_on_blk(natural_size(float(torrent.rateUpload)) + "/s") if torrent.rateUpload else "0.0 kB/s",
#		 green_on_blk(natural_size(float(torrent.rateDownload)) + "/s") if torrent.rateDownload else "0.0 kB/s",
#		 yellow_on_blk(torrent.status)
#	 ))

def remove_torrent(torrent, reason=DEFAULT_REASON, delete_files=False):
	""" Remove a torrent from the client stopping it first if its in a started state.

	:param client: Transmission RPC Client
	:type client: transmissionrpc.Client
	:param torrent: Torrent instance to remove
	:type torrent: transmissionrpc.Torrent
	:param reason: Reason for removal
	:type reason: str
	:param dry_run: Do a dry run without actually running any commands
	:type dry_run: bool
	:return:
	"""
	if torrent.status != "stopped":
		if not CONFIG['dryrun']:
			TSCLIENT.stop_torrent(torrent.hashString)
	if not CONFIG['dryrun']:
		TSCLIENT.remove_torrent(torrent.hashString, delete_data=delete_files)
	logger.info("Removed: {} {}\n\tReason: {}\n\tDry run: {}, Delete files: {}".format(torrent.name, torrent.hashString, reason, CONFIG['dryrun'],delete_files))

def remove_torrents(torrents, reason=DEFAULT_REASON, delete_files=False):
	""" Remove a torrent from the client stopping it first if its in a started state.

	:param client: Transmission RPC Client
	:type client: transmissionrpc.Client
	:param torrent: Torrent instance to remove
	:type torrent: transmissionrpc.Torrent
	:param reason: Reason for removal
	:type reason: str
	:param dry_run: Do a dry run without actually running any commands
	:type dry_run: bool
	:return:
	"""
	for torrent in torrents:
		remove_torrent(torrent, reason=reason, delete_files=delete_files)
	
def stop_torrents(torrents=[], reason=DEFAULT_REASON):
	""" Stop (pause) a list of torrents from the client.

	:param client: Transmission RPC Client
	:type client: transmissionrpc.Client
	:param torrent: Torrent instance to remove
	:type torrent: transmissionrpc.Torrent
	:param reason: Reason for removal
	:type reason: str
	:param dry_run: Do a dry run without actually running any commands
	:type dry_run: bool
	:return:
	"""
	for torrent in (torrents if len(torrents) > 0 else TSCLIENT.get_torrents()):
		if torrent.status not in ["stopped","finished"]:
			if not CONFIG['dryrun']:
				TSCLIENT.stop_torrent(torrent.hashString)
			logger.info("Paused: {} {}\n\tReason: {}\n\tDry run: {}".format(torrent.name, torrent.hashString, reason, CONFIG['dryrun']))

def resume_torrents(torrents=[], reason=DEFAULT_REASON, start_all=False):
	""" Stop (pause) a list of torrents from the client.

	:param client: Transmission RPC Client
	:type client: transmissionrpc.Client
	:param torrent: Torrent instance to remove
	:type torrent: transmissionrpc.Torrent
	:param reason: Reason for removal
	:type reason: str
	:param dry_run: Do a dry run without actually running any commands
	:type dry_run: bool
	:return:
	"""
	if start_all:
		if not CONFIG['dryrun']:
			TSCLIENT.start_all()
		logger.info("Resumed: all transfers\n\tReason: {}\n\tDry run: {}".format(torrent.name, torrent.hashString, reason, CONFIG['dryrun']))
	else:
		for torrent in (torrents if len(torrents) > 0 else TSCLIENT.get_torrents()):
			if torrent.status == "stopped":
				if not CONFIG['dryrun']:
					TSCLIENT.start_torrent(torrent.hashString)
				logger.info("Resumed: {} {}\n\tReason: {}\n\tDry run: {}".format(torrent.name, torrent.hashString, reason, CONFIG['dryrun']))

def verify_torrents(torrents=[]):
	""" Verify a list of torrents from the client.

	:param client: Transmission RPC Client
	:type client: transmissionrpc.Client
	:param torrent: Torrent instance to remove
	:type torrent: transmissionrpc.Torrent
	:type reason: str
	:param dry_run: Do a dry run without actually running any commands
	:type dry_run: bool
	:return:
	"""
	for torrent in (torrents if len(torrents) > 0 else TSCLIENT.get_torrents()):
		if not CONFIG['dryrun']:
			TSCLIENT.verify_torrent(torrent.hashString)
		logger.info("Verified: {} {}\n\tDry run: {}".format(torrent.name, torrent.hashString, CONFIG['dryrun']))

def add_torrent(torStr):
	torrent = None
	if not CONFIG['dryrun']:
		if torStr != "":
			torrent = TSCLIENT.add_torrent(torStr)
			logger.info("Added: {} {}\n\tDry run: {}".format(torrent.name, torrent.hashString, CONFIG['dryrun']))
	else:
		logger.info("Added: {} \n\tDry run: {}".format(torStr if len(torStr) < 300 else torStr[:200], CONFIG['dryrun']))
	return torrent


# Begin discord bot functions, adapted from https://github.com/kkrypt0nn/Python-Discord-Bot-Template

# async def status_task():
# 	while True:
# 		await client.change_presence(activity=discord.Game("{}help".format(CONFIG['bot_prefix'])))
# 		await asyncio.sleep(86400)


# check current transfers against those in TORRENT_JSON and print notifications to channel for certain changes
def check_for_transfer_changes():
	global TORRENT_NOTIFIED_USERS, TORRENT_ADDED_USERS, TORRENT_OPTOUT_USERS
	# get current transfer information
	reload_client()
	torrents = TSCLIENT.get_torrents()
	# TORRENT_LIST = {
		# 'hashString':{
		# 	'name':t.name,
		# 	'error':t.error,
		#	'errorString':t.errorString,
		# 	'status':t.status,
		# 	'isStalled':t.isStalled,
		# 	'progress':t.progress
		# }
	# }
	lock()
	curTorrents = {t.hashString:{
			'name':t.name,
			'error':t.error,
			'errorString':t.errorString,
			'status':t.status,
			'isStalled':t.isStalled,
			'progress':t.progress,
			'added_user':None if t.hashString not in TORRENT_ADDED_USERS else TORRENT_ADDED_USERS[t.hashString],
			'notified_users':[] if t.hashString not in TORRENT_NOTIFIED_USERS else TORRENT_NOTIFIED_USERS[t.hashString],
			'optout_users':[] if t.hashString not in TORRENT_OPTOUT_USERS else TORRENT_OPTOUT_USERS[t.hashString]
		} for t in torrents}
	if exists(TORRENT_JSON):
		oldTorrents = load_json(path=TORRENT_JSON)
		if len(curTorrents) > 0 and len(oldTorrents) > 0 and len(next(iter(curTorrents.values()))) != len(next(iter(oldTorrents.values()))):
			logger.info("old transfer json {} is using an old format, replacing with current transfers and not checking for changes.".format(TORRENT_JSON))
			generate_json(json_data=curTorrents, path=TORRENT_JSON, overwrite=True)
			return None
		# get added_user and notified_users from oldTorrents and copy to newTorrents
		for h,t in oldTorrents.items():
			if h in curTorrents:
				if t['added_user']:
					# this would overwrite a torrent that somehow had two added_users, but that should never happen
					curTorrents[h]['added_user'] = t['added_user']
				if len(t['notified_users']) > 0:
					curTorrents[h]['notified_users'] += [u for u in t['notified_users'] if u not in curTorrents[h]['notified_users']]
				if len(t['optout_users']) > 0:
					curTorrents[h]['optout_users'] += [u for u in t['optout_users'] if u not in curTorrents[h]['optout_users'] and (h not in TORRENT_NOTIFIED_USERS or u not in TORRENT_NOTIFIED_USERS[h])]
					# logger.debug("'optout_users' for {} ({}): {}".format(t['name'], h, str(t['optout_users'])))
					# for u in t['optout_users']:
					# 	if h in TORRENT_NOTIFIED_USERS and u in TORRENT_NOTIFIED_USERS[h]:
					# 		user = client.get_user(u)
					# 		logger.debug("Removing {} ({}) from 'optout_users' for {} ({})".format(user.name, u, t['name'], h))
					# 		curTorrents[h]['optout_users'].remove(u)
					# logger.debug("new 'optout_users' for {} ({}): {}".format(t['name'], h, str(curTorrents[h]['optout_users'])))
					
		TORRENT_NOTIFIED_USERS = {}
		TORRENT_ADDED_USERS = {}
		TORRENT_OPTOUT_USERS = {}
		unlock()
		generate_json(json_data=curTorrents, path=TORRENT_JSON, overwrite=True)
	else:
		TORRENT_NOTIFIED_USERS = {}
		TORRENT_ADDED_USERS = {}
		TORRENT_OPTOUT_USERS = {}
		unlock()
		generate_json(json_data=curTorrents, path=TORRENT_JSON, overwrite=True)
		return None
	

	# print("before checking")
	# get lists of different transfer changes
	removedTransfers = {h:t for h,t in oldTorrents.items() if h not in curTorrents}
	errorTransfers = {h:t for h,t in curTorrents.items() if t['error'] != 0 and ((h in oldTorrents  and oldTorrents[h]['error'] == 0) or h not in oldTorrents)}
	downloadedTransfers = {h:t for h,t in curTorrents.items() if t['progress'] == 100.0 and ((h in oldTorrents and oldTorrents[h]['progress'] < 100.0) or h not in oldTorrents)}
	stalledTransfers = {h:t for h,t in curTorrents.items() if t['isStalled'] and ((h in oldTorrents and not oldTorrents[h]['isStalled']) or h not in oldTorrents)}
	unstalledTransfers = {h:t for h,t in curTorrents.items() if not t['isStalled'] and h in oldTorrents and oldTorrents[h]['isStalled']}
	finishedTransfers = {h:t for h,t in curTorrents.items() if t['status'] == 'finished' and ((h in oldTorrents and oldTorrents[h]['status'] != 'finished') or h not in oldTorrents)}
	stoppedTransfers = {h:t for h,t in curTorrents.items() if t['status'] == 'stopped' and ((h in oldTorrents and oldTorrents[h]['status'] != 'stopped') or h not in oldTorrents)}
	startedTransfers = {h:t for h,t in curTorrents.items() if t['status'] in ['downloading','seeding'] and h in oldTorrents and oldTorrents[h]['status'] not in ['downloading','seeding']}

	# only report transfers as "new" if they haven't already been put in one of the dicts above
	checkTransfers = {**errorTransfers, **downloadedTransfers, **stalledTransfers, **unstalledTransfers, **finishedTransfers, **stoppedTransfers, **startedTransfers, **oldTorrents}
	newTransfers = {h:t for h,t in curTorrents.items() if h not in checkTransfers}


	# print("done checking for changes")
	
	# DEBUG grab a few random transfers for each type, vary the number to see if multiple embeds works
	# print(str(oldTorrents))
	# numTransfers = 3
	# removedTransfers = {h:t for h,t in random.sample(oldTorrents.items(),numTransfers)}
	# errorTransfers = {h:t for h,t in random.sample(curTorrents.items(),numTransfers)}
	# downloadedTransfers = {h:t for h,t in random.sample(curTorrents.items(),numTransfers)}
	# stalledTransfers = {h:t for h,t in random.sample(curTorrents.items(),numTransfers)}
	# unstalledTransfers = {h:t for h,t in random.sample(curTorrents.items(),numTransfers)}
	# finishedTransfers = {h:t for h,t in random.sample(curTorrents.items(),numTransfers)}
	# newTransfers = {h:t for h,t in random.sample(curTorrents.items(),numTransfers)}
	# print(str(errorTransfers))
	# print("done applying debug changes")
	
	return {
		'new':{'name':"🟢 {0} new transfer{1}", 'data':newTransfers},
		'removed':{'name':"❌ {0} removed transfer{1}", 'data':removedTransfers},
		'error':{'name':"‼️ {0} transfer{1} with error{1}", 'data':errorTransfers},
		'downloaded':{'name':"⬇️ {0} transfer{1} finished downloading", 'data':downloadedTransfers},
		'stalled':{'name':"🐢 {0} transfer{1} stalled", 'data':stalledTransfers},
		'unstalled':{'name':"🐇 {0} previously stalled transfer{1} now active", 'data':unstalledTransfers},
		'finished':{'name':"🏁 {0} transfer{1} finished downloading and seeding", 'data':finishedTransfers},
		'stopped':{'name':"⏹ {0} transfer{1} paused", 'data':stoppedTransfers},
		'started':{'name':"▶️ {0} transfer{1} resumed", 'data':startedTransfers}
	}

def prepare_notifications(changedTransfers, states=CONFIG['notification_states']['in_channel']):
	nTotal = sum([len(d['data']) for s,d in changedTransfers.items() if s in states]) if changedTransfers is not None else 0
	torrents = {}
	if nTotal > 0:
		embeds = [discord.Embed(title="")]
		ts = datetime.datetime.now(tz=pytz.timezone('America/Denver'))
		embeds[-1].timestamp = ts
		for s,d in changedTransfers.items():
			if s in states:
				n = len(d['data'])
				if n > 0:
					for h,t in d['data'].items():
						torrents[h] = t
					
					nameStr = d['name'].format(n, '' if n == 1 else 's')
					vals = ["{}{}".format("**{}.**".format(i+1) if n > 1 else '', t['name'], "\n (error: *{}*)".format(t['errorString']) if t['errorString'] != "" else "") for i,t in enumerate(d['data'].values())]
					valStr = ',\n'.join(vals)
					
					if len(embeds[-1]) + len(nameStr) + len(valStr) >= 6000:
						embeds.append(discord.Embed(title=""))
						embeds[-1].timestamp = ts
					if len(nameStr) + len(valStr) > 1000:
						valStr = ""
						for i,v in enumerate(vals):
							if len(embeds[-1]) + len(nameStr) + len(valStr) + len(v) >= 6000:
								embeds.append(discord.Embed(title=""))
								embeds[-1].timestamp = ts
							if len(nameStr) + len(valStr) + len(v) > 1000:
								embeds[-1].add_field(name=nameStr, value=valStr, inline=False)
								nameStr = ""
								valStr = ""
							else:
								valStr += v
								if i < len(vals) - 1:
									valStr += ",\n"
						pass
				
					embeds[-1].add_field(name=nameStr, value=valStr, inline=False)
		return embeds, nTotal, torrents
	return None, nTotal, torrents

async def check_notification_reactions(message, is_text_channel, torrents, starttime=datetime.datetime.now()):
	if (datetime.datetime.now() - starttime).total_seconds() >= CONFIG['notification_freq'] * CONFIG['notification_reaction_check_factor']:
		if is_text_channel:
			await message.clear_reactions()
		return
	
	def check(reaction, user):
		return user.id in CONFIG['whitelist_user_ids'] and reaction.message.id == message.id and (str(reaction.emoji) == '🔕' or (str(reaction.emoji) == '🔔' and is_text_channel))
	
	try:
		reaction, user = await client.wait_for('reaction_add', timeout=CONFIG['notification_freq'], check=check)
	except asyncio.TimeoutError:
		return await check_notification_reactions(message, is_text_channel, torrents, starttime=starttime)
	else:
		if str(reaction.emoji) == '🔔':
			if len(torrents) > 0:
				for h,t in torrents.items():
					if h in TORRENT_NOTIFIED_USERS:
						TORRENT_NOTIFIED_USERS[h].append(user.id)
					else:
						TORRENT_NOTIFIED_USERS[h] = [user.id]
				embed = discord.Embed(title="🔔 Notifications enabled for:", description=",\n".join(["{}{}".format("" if len(torrents) == 1 else "**{}.**".format(i+1),j) for i,j in enumerate([t['name'] for t in torrents.values()])]))
				await user.send(embed=embed)
		if str(reaction.emoji) == '🔕':
			if len(torrents) > 0:
				for h,t in torrents.items():
					if h in TORRENT_OPTOUT_USERS:
						TORRENT_OPTOUT_USERS[h].append(user.id)
					else:
						TORRENT_OPTOUT_USERS[h] = [user.id]
				embed = discord.Embed(title="🔕 Notifications disabled for:", description=",\n".join(["{}{}".format("" if len(torrents) == 1 else "**{}.**".format(i+1),j) for i,j in enumerate([t['name'] for t in torrents.values()])]))
				await user.send(embed=embed)
	return await check_notification_reactions(message, is_text_channel, torrents, starttime=starttime)

async def run_notifications():
	if CONFIG['notification_enabled']:
		# get all changes
		logger.debug("Running notification check")
		changedTransfers = check_for_transfer_changes()
		nTotal = sum([len(d['data']) for d in changedTransfers.values()]) if changedTransfers is not None else 0
		if nTotal > 0:
		
			# first in_channel notifications
			if CONFIG['notification_enabled_in_channel']:
				embeds, n, torrents = prepare_notifications(changedTransfers, CONFIG['notification_states']['in_channel'])
				logger.debug("in_channel notifications: {}".format(n))
					# now post notifications
				if n > 0:
					ch = client.get_channel(CONFIG['notification_channel_id'])
					msgs = [await ch.send(embed=e) for e in embeds]
					[await msgs[-1].add_reaction(s) for s in ['🔔','🔕']]
					asyncio.create_task(check_notification_reactions(msgs[-1], True, torrents, datetime.datetime.now()))
					
			
			# Now notify the users
			# First get only the changedTransfers that require user notification.
			# These will be stored separate because users *should* be reminded whether a notification
			# is for a torrent they added versus one they elected to receive notifications for.
			logger.debug("preparing list of transfers for user DM notifications")
		
			addedUserChangedTransfers = {}
			notifiedUserChangedTransfers = {}
			for s,d in changedTransfers.items():
				logger.debug("state: {} ({} transfers)".format(s, len(d['data'])))
				if s in CONFIG['notification_states']['added_user']:
					for h,t in d['data'].items():
						logger.debug("Checking transfer: {} ({})".format(str(t), h))
						if t['added_user'] is not None and t['added_user'] not in t['optout_users']:
							u = t['added_user']
							if u in addedUserChangedTransfers:
								if s in addedUserChangedTransfers[u]:
									addedUserChangedTransfers[u][s]['data'][h] = t
								else:
									addedUserChangedTransfers[u][s] = {'name':d['name'],'data':{h:t}}
							else:
								addedUserChangedTransfers[u] = {s:{'name':d['name'],'data':{h:t}}}
				if s in CONFIG['notification_states']['notified_users']:
					for h,t in d['data'].items():
						logger.debug("Checking transfer: {} ({})".format(str(t), h))
						for u in t['notified_users']:
							if u not in t['optout_users'] and (u not in addedUserChangedTransfers or s not in addedUserChangedTransfers[u] or h not in addedUserChangedTransfers[u][s]['data']):
								if u in notifiedUserChangedTransfers:
									if s in notifiedUserChangedTransfers[u]:
										notifiedUserChangedTransfers[u][s]['data'][h] = t
									else:
										notifiedUserChangedTransfers[u][s] = {'name':d['name'],'data':{h:t}}
								else:
									notifiedUserChangedTransfers[u] = {s:{'name':d['name'],'data':{h:t}}}
								
			logger.debug("DM notifications for notified_users: {}".format(str(notifiedUserChangedTransfers)))
			logger.debug("DM notifications for added_user: {}".format(str(addedUserChangedTransfers)))
			logger.debug("done preparing list of user DM notifications, now send notifications")
		
			# now send notifications as DMs
			for u,transfers in addedUserChangedTransfers.items():
				logger.debug("Sending added_user notificaions for user {}".format(u))
				embeds, n, torrents = prepare_notifications(transfers, CONFIG['notification_states']['added_user'])
				if n > 0:
					embeds[-1].set_author(name="Activity for transfer{} you added".format('' if n == 1 else 's'))
					user = client.get_user(u)
					msgs = [await user.send(embed=e) for e in embeds]
					await msgs[-1].add_reaction('🔕')
					asyncio.create_task(check_notification_reactions(msgs[-1], False, torrents, datetime.datetime.now()))
			for u,transfers in notifiedUserChangedTransfers.items():
				logger.debug("Sending notified_user notificaions for user {}".format(u))
				embeds, n, torrents = prepare_notifications(transfers, CONFIG['notification_states']['notified_users'])
				if n > 0:
					user = client.get_user(u)
					msgs = [await user.send(embed=e) for e in embeds]
					await msgs[-1].add_reaction('🔕')
					asyncio.create_task(check_notification_reactions(msgs[-1], False, torrents, datetime.datetime.now()))
		else:
			logger.debug("No changed transfers...")
		
	return
	
async def loop_notifications():
	while CONFIG['notification_enabled']:
		# print("looping notifications")
		try:
			await run_notifications()
		except Exception as e:
			logger.error("Exception thrown in run_notifications: {}".format(e))
		await asyncio.sleep(CONFIG['notification_freq'])
	return
	

@client.event
async def on_ready():
	global TSCLIENT_CONFIG, CONFIG
	unlock()
	TSCLIENT_CONFIG = CONFIG['tsclient']
	if not CONFIG: # load from config file
		CONFIG = load_json(path=CONFIG_JSON)
		if not CONFIG:
			logger.critical("Failed to load config from {}".format(CONFIG_JSON))
			await client.change_presence(activity=discord.Game("config load error!"))
			return
	else: # config specified in this file, so try to write config file
		if exists(CONFIG_JSON):
			if load_json(CONFIG_JSON) != CONFIG:
				# check current config against config file, throw error if different
				logger.critical("Conflict: Config file exists and config specified in bot.py!")
				await client.change_presence(activity=discord.Game("config load error!"))
				return
		elif not generate_json(json_data=CONFIG, path=CONFIG_JSON, overwrite=True):
			logger.critical("Failed to write config file on startup!")
			await client.change_presence(activity=discord.Game("config load error!"))
			return
			
	TSCLIENT_CONFIG = CONFIG['tsclient']
	reload_client()
	if TSCLIENT is None:
		logger.critical("Failed to create transmissionrpc client")
		await client.change_presence(activity=discord.Game("client load error!"))
	else:
		# client.loop.create_task(status_task())
		await client.change_presence(activity=discord.Game("Listening {}help".format(CONFIG['bot_prefix'])))
		print('Logged in as ' + client.user.name)
		print("Discord.py API version:", discord.__version__)
		print("Python version:", platform.python_version())
		print("Running on:", platform.system(), platform.release(), "(" + os.name + ")")
		print('-------------------')

	# ch = client.get_channel(CONFIG['notification_channel_id'])
	# await ch.send("test message")
	# user = client.get_user(CONFIG['owner_user_ids'][0])
	# await user.send("test message")
	if CONFIG['notification_enabled']:
		task = asyncio.create_task(loop_notifications())
		
def humanseconds(S):
	if S == -2:
		return '?' if COMPACT_OUTPUT else 'Unknown'
	elif S == -1:
		return 'N/A'
	elif S < 0:
		return 'N/A'
	
	M = 60
	H = M * 60
	D = H * 24
	W = D * 7
	
	w,s = divmod(S,W)
	d,s = divmod(s,D)
	h,s = divmod(s,H)
	m,s = divmod(s,M)
	
	if COMPACT_OUTPUT:
		d += w * 7
		out = '{}{:02d}:{:02d}:{:02d}'.format('' if d == 0 else '{}-'.format(d), h, m, s)
	else:
		out = '{}{}{:02d}:{:02d}:{:02d}'.format('' if w == 0 else '{} week{}, '.format(w,'' if w == 1 else 's'), '' if d == 0 else '{} day{}, '.format(d,'' if d == 1 else 's'), h, m, s)
		
	return out

def humanbytes(B,d = 2):
	'Return the given bytes as a human friendly KB, MB, GB, or TB string'
	B = float(B)
	KB = float(1024)
	MB = float(KB ** 2) # 1,048,576
	GB = float(KB ** 3) # 1,073,741,824
	TB = float(KB ** 4) # 1,099,511,627,776
	
	if d <= 0:
		if B < KB:
			return '{0}B'.format(int(B))
		elif KB <= B < MB:
			return '{0:d}kB'.format(int(B/KB))
		elif MB <= B < GB:
			return '{0:d}MB'.format(int(B/MB))
		elif GB <= B < TB:
			return '{0:d}GB'.format(int(B/GB))
		elif TB <= B:
			return '{0:d}TB'.format(int(B/TB))
	else:
		if B < KB:
			return '{0} B'.format(B)
		elif KB <= B < MB:
			return '{0:.{nd}f} kB'.format(B/KB, nd = d)
		elif MB <= B < GB:
			return '{0:.{nd}f} MB'.format(B/MB, nd = d)
		elif GB <= B < TB:
			return '{0:.{nd}f} GB'.format(B/GB, nd = d)
		elif TB <= B:
			return '{0:.{nd}f} TB'.format(B/TB, nd = d)
	  
def tobytes(B):
	'Return the number of bytes given by a string (a float followed by a space and the unit of prefix-bytes eg. "21.34 GB")'
	numstr = B.lower().split(' ')
	KB = (('kilo','kb','kb/s'),float(1024))
	MB = (('mega','mb','mb/s'),float(KB[1] ** 2)) # 1,048,576
	GB = (('giga','gb','gb/s'),float(KB[1] ** 3)) # 1,073,741,824
	TB = (('tera','tb','tb/s'),float(KB[1] ** 4)) # 1,099,511,627,776
	
	for prefix in (KB,MB,GB,TB):
		if numstr[1] in prefix[0]:
			return float(float(numstr[0]) * prefix[1])
	
async def IsCompactOutput(message):
	if OUTPUT_MODE == OutputMode.AUTO:
		if message.author.dm_channel is not None and message.channel.id == message.author.dm_channel.id:
			return OutputMode.DESKTOP
			#user = client.get_user(message.author.id)
		else:
			user = message.author
		if user.is_on_mobile():
			return OutputMode.MOBILE
		else:
			return OutputMode.DESKTOP
	else:
		return OUTPUT_MODE
		
# check that message author is allowed and message was sent in allowed channel
async def CommandPrecheck(message, whitelist=CONFIG['whitelist_user_ids']):
	# first set output mode
	global COMPACT_OUTPUT
	COMPACT_OUTPUT = await IsCompactOutput(message) == OutputMode.MOBILE
	if (message.author.dm_channel is None or message.channel.id != message.author.dm_channel.id) and not CONFIG['listen_all_channels'] and message.channel.id not in CONFIG['listen_channel_ids']:
		await message.channel.send("I don't respond to commands in this channel...")
		await asyncio.sleep(2)
		await message.delete()
		return False
	if message.author.dm_channel is not None and message.channel.id == message.author.dm_channel.id and not CONFIG['listen_DMs']:
		await message.channel.send("I don't respond to DMs...")
		await asyncio.sleep(2)
		await message.delete()
		return False
	if message.author.id in CONFIG['blacklist_user_ids'] or (len(whitelist) > 0 and message.author.id not in whitelist):
		await message.channel.send("You're not allowed to use this...")
		await asyncio.sleep(2)
		await message.delete()
		return False
	return True

async def message_clear_reactions(message, parent_message, reactions=[]):
	if parent_message.author.dm_channel is None or parent_message.channel.id != parent_message.author.dm_channel.id:
		if reactions == []:
			await message.clear_reactions()
		else:
			for s in reactions:
				await message.clear_reaction(s)
	
def message_has_torrent_file(message):
	for f in message.attachments:
		if len(f.filename) > 8 and f.filename[-8:].lower() == ".torrent":
			return True
	return False

def commaListToParagraphForm(l):
	outStr = ''
	if len(l) > 0:
		outStr += ('' if len(l <= 2) else ', ').join(l[:-1])
		outStr += ('{} and '.format('' if len(l) <= 2 else ',') if len(l) > 1 else '') + str(l[-1])
		
	return outStr

async def add(message, content = ""):
	if await CommandPrecheck(message):
		async with message.channel.typing():
			torFileList = []
			for f in message.attachments:
				if len(f.filename) > 8 and f.filename[-8:].lower() == ".torrent":
					encodedBytes = base64.b64encode(await f.read())
					encodedStr = str(encodedBytes, "utf-8")
					torFileList.append({"name":f.filename,"content":encodedStr})
				continue
			if content == "" and len(torFileList) == 0:
				await message.channel.send("🚫 Invalid string")
		
			if CONFIG['delete_command_messages']:
				try:
					await message.delete()
				except:
					pass
		
			torStr = []
			torIDs = []
			for i,t in enumerate(torFileList):
				# await message.channel.send('Adding torrent from file: {}\n Please wait...'.format(t["name"]))
				try:
					tor = add_torrent(t["content"])
					if tor:
						lock()
						TORRENT_ADDED_USERS[tor.hashString] = message.author.id
						unlock()
						logger.info("User {} ({}) added torrent from file {}: {} ({})".format(message.author.name, message.author.id, t["name"], tor.name, tor.hashString))
						# if tor.isPrivate:
						# 	privateTransfers.append(len(privateTransfers))
						logger.debug("Added to TORRENT_ADDED_USERS")
						torStr.append("💽 {}".format(tor.name))
						torIDs.append(tor.id)
					elif CONFIG['dryrun']:
						torStr.append("💽 added file dryrun: {}".format(t["name"]))
				except Exception as e:
					logger.warning("Exception when adding torrent from file: {}".format(e))
			
			for t in content.strip().split(" "):
				if len(t) > 5:
					# await message.channel.send('Adding torrent from link: {}\n Please wait...'.format(t))
					try:
						tor = add_torrent(t)
						if tor:
							lock()
							TORRENT_ADDED_USERS[tor.hashString] = message.author.id
							unlock()
							logger.info("User {} ({}) added torrent from URL: {} ({})".format(message.author.name, message.author.id, tor.name, tor.hashString))
							# if tor.isPrivate:
							# 	privateTransfers.append(len(privateTransfers))
							logger.debug("Added to TORRENT_ADDED_USERS")
							torStr.append("🧲 {}".format(tor.name))
							torIDs.append(tor.id)
					except Exception as e:
						logger.warning("Exception when adding torrent from URL: {}".format(e))
				
			if len(torStr) > 0:
				embeds = []
				if len('\n'.join(torStr)) > 2000:
					embeds.append(discord.Embed(title='🟢 Added torrents'))
					descStr = torStr[0]
					for t in torStr[1:]:
						if len(descStr) + len(t) < 2000:
							descStr += '\n{}'.format(t)
						else:
							embeds[-1].description = descStr
							embeds.append(discord.Embed(title='🟢 Added torrents'))
							descStr = t
				else:
					embeds = [discord.Embed(title='🟢 Added torrent{}'.format("s" if len(torStr) > 1 else ""), description='\n'.join(torStr), color=0xb51a00)]
				privateTransfers = []
				if not CONFIG['dryrun']:
					logger.debug("Checking for private transfers amidst the {} new torrents".format(len(torStr)))
					privateCheckSuccess = False
					for i in range(5):
						try:
							newTorrents = TSCLIENT.get_torrents_by(id_list=torIDs)
							logger.debug("Fetched {} transfers from transmission corresponding to the {} transfer IDs recorded".format(len(newTorrents),len(torIDs)))
							for tor in newTorrents:
								logger.debug("Checking private status of added transfer {}: {}".format(i+1, tor.name))
								if tor.isPrivate:
									privateTransfers.append(torIDs.index(tor.id))
									logger.debug("Transfer is private")
							privateCheckSuccess = True
							logger.debug("Successfully checked for private tranfers: {} found".format(len(privateTransfers)))
							break
						except AttributeError as e:
							logger.debug("Attribute error when checking for private status of added torrent(s): {}".format(e))
						except Exception as e:
							logger.warning("Exception when checking for private status of added torrent(s): {}".format(e))
						asyncio.sleep(0.2)
				if len(privateTransfers) > 0 or CONFIG['dryrun']:
					if len(privateTransfers) > 0 and CONFIG['delete_command_message_private_torrent']:
						try:
							await message.delete()
						except Exception as e:
							logger.warning("Exception when removing command message used to add private torrent(s): {}".format(e))
					embeds[-1].set_footer(text="\n🔐  One or more added torrents are using a private tracker, which may prohibit running the same transfer from multiple locations. Ensure that you're not breaking any private tracker rules.{}".format('' if CONFIG['dryrun'] else "\n(I erased the command message to prevent any unintentional sharing of torrent files)"))
				for e in embeds:
					await message.channel.send(embed=e)
			else:
				await message.channel.send('🚫 No torrents added!')
		

@client.command(name='add', aliases=['a'], pass_context=True)
async def add_cmd(context, *, content = ""):
	try:
		await add(context.message, content=content)
	except Exception as e:
		logger.warning("Exception when adding torrent(s): {}".format(e))
	
# def torInfo(t):
# 	states = ('downloading', 'seeding', 'stopped', 'finished','all')
# 	stateEmoji = {i:j for i,j in zip(states,['🔻','🌱','⏸','🏁','↕️'])}
#
# 	downStr = humanbytes(t.progress * 0.01 * t.totalSize)
# 	upStr = "{} (Ratio: {:.2f})".format(humanbytes(t.uploadedEver), t.uploadRatio)
# 	runTime =
#
# 	if t.progress < 100.0:
# 		have = "{} of {} ({:.1f}){}{}".format(downStr,humanbytes(t.totalSize), t.progress, '' if t.haveUnchecked == 0 else ', {} Unverified'.format(humanbytes(t.haveUnchecked)), '' if t.corruptEver == 0 else ', {} Corrupt'.format(humanbytes(t.corruptEver)))
# 		avail = "{:.1f}%".format(t.desiredAvailable/t.leftUntilDone)
# 	else:
# 		have = "{} ({:d}){}{}".format(humanbytes(t.totalSize), t.progress, '' if t.haveUnchecked == 0 else ', {} Unverified'.format(humanbytes(t.haveUnchecked)), '' if t.corruptEver == 0 else ', {} Corrupt'.format(humanbytes(t.corruptEver)))
# 		avail = "100%"
#
# 	embed=discord.Embed(title=t.name,color=0xb51a00)
#
# 	return embed

torStates = ('downloading', 'seeding', 'stopped', 'verifying', 'queued', 'finished', #0-5
	'stalled', 'active', 'running', #6-8
	'private', 'public', #9-10
	'error', 'err_none', 'err_tracker_warn', 'err_tracker_error', 'err_local', # 11-
)
torStateEmoji = ('🔻','🌱','⏸','🔬','🚧','🏁',
	'🐢','🐇','🚀',
	'🔐','🔓',
	'‼️','✅','⚠️','🌐','🖥'
)
torStateFilters = {i:"--filter {}".format(j) for i,j in zip(torStateEmoji,torStates)}
torStateFilters['↕️']=''

def numTorInState(torrents, state):
	rpc_states = ('downloading', 'seeding', 'stopped', 'finished')
	if state in rpc_states:
		return len([True for t in torrents if t.status == state])
	elif state =='verifying': # these are also rpc statuses, but I want to combine them.
		return len([True for t in torrents if 'check' in t.status])
	elif state == 'queued':
		return len([True for t in torrents if 'load pending' in t.status])
	elif state == 'stalled':
		return len([True for t in torrents if t.isStalled])
	elif state == 'active':
		return len([True for t in torrents if not t.isStalled]) - len([True for t in torrents if t.rateDownload + t.rateUpload > 0])
	elif state == 'running':
		return len([True for t in torrents if t.rateDownload + t.rateUpload > 0])
	elif state == 'private':
		return len([True for t in torrents if t.isPrivate])
	elif state == 'public':
		return len([True for t in torrents if not t.isPrivate])
	elif state == 'error':
		return len([True for t in torrents if t.error != 0])
	elif state == 'err_none':
		return len([True for t in torrents if t.error == 0])
	elif state == 'err_twarn':
		return len([True for t in torrents if t.error == 1])
	elif state == 'err_terr':
		return len([True for t in torrents if t.error == 2])
	elif state == 'err_local':
		return len([True for t in torrents if t.error == 3])
	else:
		return 0

def torSummary(torrents, repeat_msg_key=None, show_repeat=True):
	numInState = [numTorInState(torrents,s) for s in torStates]
	numTot = len(torrents)
	
	sumTot = sum([t.totalSize for t in torrents])
	totSize = humanbytes(sumTot)
	totUpRate = humanbytes(sum([t.rateUpload for t in torrents]))
	totDownRate = humanbytes(sum([t.rateDownload for t in torrents]))
	
	downList = [t.progress*0.01*t.totalSize for t in torrents]
	upList = [t.ratio * j for t,j in zip(torrents,downList)]
	
	sumDown = sum(downList)
	sumUp = sum(upList)
	
	totDown = humanbytes(sumDown)
	totUp = humanbytes(sumUp)
	
	totRatio = '{:.2f}'.format(sumUp / sumDown)
	
	totDownRatio = '{:.2f}'.format(sumDown / sumTot * 100.0)
	
	numTopRatios = min([len(torrents),CONFIG['summary_num_top_ratio']])
	topRatios = "• Top {} ratio{}:".format(numTopRatios,"s" if numTopRatios != 1 else "")
	sortByRatio = sorted(torrents,key=lambda t:float(t.ratio),reverse=True)
	for i in range(numTopRatios):
		topRatios += "\n {:.1f} {:.35}{}".format(float(sortByRatio[i].ratio),sortByRatio[i].name,"..." if len(sortByRatio[i].name) > 35 else "")
	
	embed=discord.Embed(description="*React to see list of corresponding transfers*", color=0xb51a00)
	embed.set_author(name="Torrent Summary 🌊", icon_url=CONFIG['logo_url'])
	embed.add_field(name="⬇️ {}/s".format(totDownRate), value="⬆️ {}/s".format(totUpRate), inline=False)
	embed.add_field(name="⏬ {} of {}".format(totDown,totSize), value="⏫ {}  ⚖️ {}".format(totUp,totRatio), inline=False)
	embed.add_field(name="↕️ {} transfer{}".format(numTot, 's' if numTot != 1 else ''), value=' '.join(['{} {}'.format(i,j) for i,j in zip(torStateEmoji[:6], numInState[:6])]), inline=False)
	if COMPACT_OUTPUT:
		embed.add_field(name=' '.join(['{} {}'.format(i,j) for i,j in zip(torStateEmoji[11:], numInState[11:])]), value=' '.join(['{} {}'.format(i,j) for i,j in zip(torStateEmoji[6:9], numInState[6:9])]) + "—" + ' '.join(['{} {}'.format(i,j) for i,j in zip(torStateEmoji[9:11], numInState[9:11])]), inline=False)
	else:
		embed.add_field(name="{} Error{}".format(numInState[11], 's' if numInState[9] != 1 else ''), value='\n'.join(['{} {}'.format(i,"**{}**".format(j) if i != '✅' and j > 0 else j) for i,j in zip(torStateEmoji[12:], numInState[12:])]), inline=not COMPACT_OUTPUT)
		embed.add_field(name="Activity", value='\n'.join(['{} {}'.format(i,j) for i,j in zip(torStateEmoji[6:9], numInState[6:9])]), inline=not COMPACT_OUTPUT)
		embed.add_field(name="Tracker", value='\n'.join(['{} {}'.format(i,j) for i,j in zip(torStateEmoji[9:11], numInState[9:11])]), inline=not COMPACT_OUTPUT)
		
	freq = REPEAT_MSGS[repeat_msg_key]['freq'] if repeat_msg_key else None
	if show_repeat:
		embed.set_footer(text="{}📜 Symbol legend{}".format((topRatios + '\n') if numTopRatios > 0 else '', '\nUpdating every {} second{}—❎ to stop'.format(freq,'s' if freq != 1 else '') if repeat_msg_key else ', 🔄 to auto-update'))
	else:
		embed.set_footer(text="{}📜 Symbol legend".format((topRatios + '\n') if numTopRatios > 0 else ''))
	return embed,numInState


async def summary(message, content="", repeat_msg_key=None):
	global REPEAT_MSGS
	if await CommandPrecheck(message):
		async with message.channel.typing():
			if not repeat_msg_key:
				if len(REPEAT_MSGS) == 0:
					reload_client()
				if CONFIG['delete_command_messages']:
					try:
						await message.delete()
					except:
						pass
		
			if TSCLIENT is None:
				reload_client()
		
			stateEmojiFilterStartNum = 3 # the first emoji in stateEmoji that corresponds to a list filter
			ignoreEmoji = ('✅')
		
			summaryData=torSummary(TSCLIENT.get_torrents(), repeat_msg_key=repeat_msg_key, show_repeat=message.author.dm_channel is None or message.channel.id != message.author.dm_channel.id)
		
			if repeat_msg_key:
				msg = REPEAT_MSGS[repeat_msg_key]['msgs'][0]
				if REPEAT_MSGS[repeat_msg_key]['reprint'] or (REPEAT_MSGS[repeat_msg_key]['pin_to_bottom'] and message.channel.last_message_id != msg.id):
					await msg.delete()
					msg = await message.channel.send(embed=summaryData[0])
					REPEAT_MSGS[repeat_msg_key]['msgs'] = [msg]
					REPEAT_MSGS[repeat_msg_key]['reprint'] = False
				else:
					await msg.edit(embed=summaryData[0])
			
				if message.channel.last_message_id != msg.id and (message.author.dm_channel is None or message.channel.id != message.author.dm_channel.id):
					stateEmoji = ('📜','🖨','❎','↕️') + torStateEmoji
					stateEmojiFilterStartNum += 1
				else:
					stateEmoji = ('📜','↕️') + torStateEmoji
					stateEmojiFilterStartNum -= 1
			else:
				if message.author.dm_channel is not None and message.channel.id == message.author.dm_channel.id:
					stateEmoji = ('📜','↕️') + torStateEmoji
					stateEmojiFilterStartNum -= 1
				else:
					stateEmoji = ('📜','🔄','↕️') + torStateEmoji
				msg = await message.channel.send(embed=summaryData[0])
		
			# to get actual list of reactions, need to re-fetch the message from the server
			cache_msg = await message.channel.fetch_message(msg.id)
			msgRxns = [str(r.emoji) for r in cache_msg.reactions]
		
			for i in stateEmoji[:stateEmojiFilterStartNum]:
				if i not in msgRxns:
					await msg.add_reaction(i)
			for i in range(len(summaryData[1])):
				if summaryData[1][i] > 0 and stateEmoji[i+stateEmojiFilterStartNum] not in ignoreEmoji and stateEmoji[i+stateEmojiFilterStartNum] not in msgRxns:
					await msg.add_reaction(stateEmoji[i+stateEmojiFilterStartNum])
				elif summaryData[1][i] == 0 and stateEmoji[i+stateEmojiFilterStartNum] in msgRxns:
					await message_clear_reactions(msg, message, reactions=[stateEmoji[i+stateEmojiFilterStartNum]])
				# if not repeat_msg_key:
				# 	cache_msg = await message.channel.fetch_message(msg.id)
				# 	for r in cache_msg.reactions:
				# 		if r.count > 1:
				# 			async for user in r.users():
				# 				if user.id in CONFIG['whitelist_user_ids']:
				# 					if str(r.emoji) == '📜':
				# 						await message_clear_reactions(msg, message)
				# 						await legend(context)
				# 						return
				# 					elif str(r.emoji) == '🔄':
				# 						await message_clear_reactions(msg, message, reactions=['🔄'])
				# 						await repeat_command(summary, message=message, content=content, msg_list=[msg])
				# 						return
				# 					elif str(r.emoji) in stateEmoji[stateEmojiFilterStartNum-1:] and user.id == message.author.id:
				# 						await message_clear_reactions(msg, message)
				# 						await list_transfers(message, content=torStateFilters[str(r.emoji)])
				# 						return
		
			cache_msg = await message.channel.fetch_message(msg.id)
			for r in cache_msg.reactions:
				if r.count > 1:
					async for user in r.users():
						if user.id in CONFIG['whitelist_user_ids']:
							if str(r.emoji) == '📜':
								if repeat_msg_key:
									await message_clear_reactions(msg, message, reactions=['📜'])
								else:
									await message_clear_reactions(msg, message)
								await legend(message)
								return
							elif str(r.emoji) == '❎':
								await message_clear_reactions(msg, message)
								REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
								return
							elif str(r.emoji) == '🔄':
								await message_clear_reactions(msg, message, reactions=['🔄'])
								await repeat_command(summary, message=message, content=content, msg_list=[msg])
								return
							elif str(r.emoji) in stateEmoji[stateEmojiFilterStartNum-1:] and user.id == message.author.id:
								if repeat_msg_key:
									await message_clear_reactions(msg, message, reactions=[str(r.emoji)])
									asyncio.create_task(list_transfers(message, content=torStateFilters[str(r.emoji)]))
								else:
									await message_clear_reactions(msg, message)
									await list_transfers(message, content=torStateFilters[str(r.emoji)])
								return
		
			def check(reaction, user):
				return user == message.author and reaction.message.id == msg.id and str(reaction.emoji) in stateEmoji
		
		try:
			reaction, user = await client.wait_for('reaction_add', timeout=60.0 if not repeat_msg_key else REPEAT_MSGS[repeat_msg_key]['freq'], check=check)
		except asyncio.TimeoutError:
			if not repeat_msg_key:
				await message_clear_reactions(msg, message)
				return
			pass
		else:
			if str(reaction.emoji) in stateEmoji[stateEmojiFilterStartNum-1:] and str(reaction.emoji) not in ignoreEmoji:
				if repeat_msg_key:
					await message_clear_reactions(msg, message, reactions=[str(reaction.emoji)])
					asyncio.create_task(list_transfers(message, content=torStateFilters[str(reaction.emoji)]))
				else:
					await message_clear_reactions(msg, message)
					await list_transfers(message, content=torStateFilters[str(reaction.emoji)])
				return
			elif str(reaction.emoji) == '📜':
				if repeat_msg_key:
					await message_clear_reactions(msg, message, reactions=['📜'])
				else:
					await message_clear_reactions(msg, message)
				await legend(message)
				return
			elif str(reaction.emoji) == '❎':
				await message_clear_reactions(msg, message)
				REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
				return
			elif str(reaction.emoji) == '🔄':
				await message_clear_reactions(msg, message, reactions=['🔄'])
				await repeat_command(summary, message=message, content=content, msg_list=[msg])
				return
			elif str(reaction.emoji) == '🖨':
				await message_clear_reactions(msg, message, reactions=['🖨'])
				REPEAT_MSGS[repeat_msg_key]['reprint'] = True
				return
		if repeat_msg_key: # a final check to see if the user has cancelled the repeat by checking the count of the cancel reaction
			cache_msg = await message.channel.fetch_message(msg.id)
			for r in cache_msg.reactions:
				if r.count > 1:
					async for user in r.users():
						if user.id in CONFIG['whitelist_user_ids']:
							if str(reaction.emoji) == '📜':
								await message_clear_reactions(msg, message, reactions=['📜'])
								await legend(message)
								return
							elif str(r.emoji) == '❎':
								REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
								await message_clear_reactions(msg, message)
								return
							elif str(r.emoji) == '🖨':
								await message_clear_reactions(msg, message, reactions=['🖨'])
								REPEAT_MSGS[repeat_msg_key]['reprint'] = True
								return
							elif str(r.emoji) in stateEmoji[stateEmojiFilterStartNum-1:]:
								await message_clear_reactions(msg, message, reactions=[str(r.emoji)])
								await list_transfers(message, content=torStateFilters[str(r.emoji)])
								return
				
@client.command(name='summary',aliases=['s'], pass_context=True)
async def summary_cmd(context, *, content="", repeat_msg_key=None):
	try:
		await summary(context.message, content, repeat_msg_key=repeat_msg_key)
	except Exception as e:
		logger.warning("Exception in t/summary: {}".format(e))

def strListToList(strList):
	if not re.match('^[0-9\,\-]+$', strList):
		return False
	outList = []
	for seg in strList.strip().split(","):
		subseg = seg.split("-")
		if len(subseg) == 1 and int(subseg[0]) not in outList:
			outList.append(int(subseg[0]))
		elif len(subseg) == 2:
			subseg = sorted([int(i) for i in subseg])
			outList += range(subseg[0],subseg[1]+1)
	if len(outList) == 0:
		return False
	
	return outList


def torList(torrents, author_name="Torrent Transfers",title=None,description=None):
	states = ('downloading', 'seeding', 'stopped', 'finished','checking','check pending','download pending','upload pending')
	stateEmoji = {i:j for i,j in zip(states,['🔻','🌱','⏸','🏁','🔬','🔬','🚧','🚧'])}
	errorStrs = ['✅','⚠️','🌐','🖥']

	def torListLine(t):
		try:
			eta = int(t.eta.total_seconds())
		except:
			try:
				eta = int(t.eta)
			except:
				eta = 0
		if COMPACT_OUTPUT:
			down = humanbytes(t.progress * 0.01 * t.totalSize, d=0)
			out = "{}{} ".format(stateEmoji[t.status],errorStrs[t.error] if t.error != 0 else '')
			if t.status == 'downloading':
				out += "{}% {} {}{}/s{}".format(int(t.progress), down, '' if eta <= 0 else '{}@'.format(humanseconds(eta)), humanbytes(t.rateDownload, d=0), ' *{}/s* {:.1f}'.format(humanbytes(t.rateUpload, d=0), t.uploadRatio) if t.isStalled else '')
			elif t.status == 'seeding':
				out += "{} *{}/s*:{:.1f}".format(down, humanbytes(t.rateUpload, d=0), t.uploadRatio)
			elif t.status == 'stopped':
				out += "{}%{} {:.1f}".format(int(t.progress), down, t.uploadRatio)
			elif t.status == 'finished':
				out += "{} {:.1f}".format(down, t.uploadRatio)
			elif t.status == "checking":
				out += "{:.1f}%".format(t.recheckProgress*100.0)
		else:
			down = humanbytes(t.progress * 0.01 * t.totalSize)
			out = "{} {} {} {} ".format(stateEmoji[t.status],errorStrs[t.error],'🚀' if t.rateDownload + t.rateUpload > 0 else '🐢' if t.isStalled else '🐇', '🔐' if t.isPrivate else '🔓')
			if t.status == 'downloading':
				out += "{:.1f}% of {} ⏬ {} {}/s ⬇️ *{}/s* ⬆️ *{:.2f}* ⚖️".format(t.progress, humanbytes(t.totalSize, d=1), '' if eta <= 0 else '\n⏳ {} @ '.format(humanseconds(eta)), humanbytes(t.rateDownload), humanbytes(t.rateUpload), t.uploadRatio)
			elif t.status == 'seeding':
				out += "{} ⏬ *{}/s* ⬆️ *{:.2f}* ⚖️".format(humanbytes(t.totalSize, d=1), humanbytes(t.rateUpload), t.uploadRatio)
			elif t.status == 'stopped':
				out += "{:.1f}% of {} ⏬ *{:.2f}* ⚖️".format(t.progress, humanbytes(t.totalSize, d=1), t.uploadRatio)
			elif t.status == 'finished':
				out += "{} ⏬ {:.2f} ⚖️".format(humanbytes(t.totalSize, d=1), t.uploadRatio)
			elif t.status == "checking":
				out += "{:.2f}%".format(t.recheckProgress*100.0)
		
			if t.error != 0:
				out += "\n***Error:*** *{}*".format(t.errorString)
		return out
	
	if COMPACT_OUTPUT:
		nameList = ["{}){:.26}{}".format(t.id,t.name,"..." if len(t.name) > 26 else "") for t in torrents]
	else:
		nameList = ["{}) {:.245}{}".format(t.id,t.name,"..." if len(t.name) > 245 else "") for t in torrents]
	valList = [torListLine(t) for t in torrents]
	
	n = 0
	i = 0
	eNum = 1
	eNumTotal = 1 + len(torrents) // 25
	embeds = []
	if len(torrents) > 0:
		while i < len(torrents):
			embed=discord.Embed(title=title + ('' if eNumTotal == 1 else ' ({} of {})'.format(eNum, eNumTotal)),description=description,color=0xb51a00)
			for j in range(25):
				embed.add_field(name=nameList[i],value=valList[i],inline=False)
				i += 1
				n += 1
				if n >= 25:
					n = 0
					eNum += 1
					break
				if i >= len(torrents):
					break
			embeds.append(embed)
	else:
		embeds.append(discord.Embed(title=title, description="No matching transfers found!", color=0xb51a00))

	embeds[-1].set_author(name=author_name, icon_url=CONFIG['logo_url'])
	embeds[-1].set_footer(text="📜 Symbol legend")
	
	return embeds

def torGetListOpsFromStr(listOpStr):
	filter_by = None
	sort_by = None
	num_results = None
	splitcontent = listOpStr.split(" ")
	
	if "--filter" in splitcontent:
		ind = splitcontent.index("--filter")
		if len(splitcontent) > ind + 1:
			filter_by = splitcontent[ind+1]
			del splitcontent[ind+1]
		del splitcontent[ind]
	elif "-f" in splitcontent:
		ind = splitcontent.index("-f")
		if len(splitcontent) > ind + 1:
			filter_by = splitcontent[ind+1]
			del splitcontent[ind+1]
		del splitcontent[ind]
	
	if "--sort" in splitcontent:
		ind = splitcontent.index("--sort")
		if len(splitcontent) > ind + 1:
			sort_by = splitcontent[ind+1]
			del splitcontent[ind+1]
		del splitcontent[ind]
	elif "-s" in splitcontent:
		ind = splitcontent.index("-s")
		if len(splitcontent) > ind + 1:
			sort_by = splitcontent[ind+1]
			del splitcontent[ind+1]
		del splitcontent[ind]
		
	if "-N" in splitcontent:
		ind = splitcontent.index("-N")
		if len(splitcontent) > ind + 1:
			try:
				num_results = int(splitcontent[ind+1])
			except:
				num_results = -1
			del splitcontent[ind+1]
		del splitcontent[ind]
	
	filter_regex = " ".join(splitcontent).strip()
	if filter_regex == "":
		filter_regex = None
	
	if filter_by is not None and filter_by not in filter_names_full:
		return -1, None, None, None
	if sort_by is not None and sort_by not in sort_names:
		return None, -1, None, None
	if num_results is not None and num_results <= 0:
		return None, None, None, -1
		
	return filter_by, sort_by, filter_regex, num_results

async def repeat_command(command, message, content="", msg_list=[]):
	global REPEAT_MSGS
	msg_key = secrets.token_hex()
	REPEAT_MSGS[msg_key] = {
		'msgs':msg_list,
		'command':command,
		'message':message,
		'content':content,
		'pin_to_bottom':False,
		'reprint': False,
		'freq':CONFIG['repeat_freq'],
		'timeout':CONFIG['repeat_timeout'],
		'timeout_verbose':CONFIG['repeat_timeout_verbose'],
		'cancel_verbose':CONFIG['repeat_cancel_verbose'],
		'start_time':datetime.datetime.now(),
		'do_repeat':True
	}
	
	while msg_key in REPEAT_MSGS:
		msg = REPEAT_MSGS[msg_key]
		if msg['do_repeat']:
			delta = datetime.datetime.now() - msg['start_time']
			if delta.seconds >= msg['timeout']:
				if msg['timeout_verbose']:
					await message.channel.send("❎ Auto-update timed out...")
				break
			else:
				try:
					await msg['command'](message=msg['message'], content=msg['content'], repeat_msg_key=msg_key)
				except Exception as e:
					logger.warning("Failed to execute repeat command {}(content={}): {}".format(msg['command'], msg['content'], e))
					await asyncio.sleep(CONFIG['repeat_freq'])
		else:
			if msg['cancel_verbose']:
				await message.channel.send("❎ Auto-update canceled...")
			break
			
	del REPEAT_MSGS[msg_key]
	return

async def list_transfers(message, content="", repeat_msg_key=None):
	global REPEAT_MSGS
	if await CommandPrecheck(message):
		async with message.channel.typing():
			id_list = strListToList(content)
			filter_by = None
			sort_by = None
			filter_regex = None
			num_results = None
			if not id_list:
				filter_by, sort_by, filter_regex, num_results = torGetListOpsFromStr(content)
				if filter_by is not None and filter_by == -1:
					await message.channel.send("Invalid filter specified. Choose one of {}".format(str(filter_names_full)))
					return
				if sort_by is not None and sort_by == -1:
					await message.channel.send("Invalid sort specified. Choose one of {}".format(str(sort_names)))
					return
				if num_results is not None and num_results <= 0:
					await message.channel.send("Must specify integer greater than 0 for `-N`!")
					return
		
			if not repeat_msg_key:
				if len(REPEAT_MSGS) == 0:
					reload_client()
				if CONFIG['delete_command_messages']:
					try:
						await message.delete()
					except:
						pass
		
			if TSCLIENT is None:
				reload_client()
		
			torrents = TSCLIENT.get_torrents_by(sort_by=sort_by, filter_by=filter_by, filter_regex=filter_regex, id_list=id_list, num_results=num_results)
		
			embeds = torList(torrents, title="{} transfer{} matching '`{}`'".format(len(torrents),'' if len(torrents)==1 else 's',content))
		
			if message.author.dm_channel is not None and message.channel.id == message.author.dm_channel.id:
				embeds[-1].set_footer(text="📜 Symbol legend")
			else:
				embeds[-1].set_footer(text="📜 Symbol legend{}".format('\nUpdating every {} second{}—❎ to stop'.format(REPEAT_MSGS[repeat_msg_key]['freq'],'s' if REPEAT_MSGS[repeat_msg_key]['freq'] != 1 else '') if repeat_msg_key else ', 🔄 to auto-update'))
			
			if repeat_msg_key:
				msgs = REPEAT_MSGS[repeat_msg_key]['msgs']
				if REPEAT_MSGS[repeat_msg_key]['reprint'] or (REPEAT_MSGS[repeat_msg_key]['pin_to_bottom'] and message.channel.last_message_id != msgs[-1].id):
					for m in msgs:
						await m.delete()
					msgs = []
					REPEAT_MSGS[repeat_msg_key]['reprint'] = False
				for i,e in enumerate(embeds):
					if i < len(msgs):
						await msgs[i].edit(embed=e)
						cache_msg = await message.channel.fetch_message(msgs[i].id)
						if i < len(embeds) - 1 and len(cache_msg.reactions) > 0:
							await message_clear_reactions(cache_msg, message)
					else:
						msgs.append(await message.channel.send(embed=e))
				if len(msgs) > len(embeds):
					for i in range(len(msgs) - len(embeds)):
						await msgs[-1].delete()
						del msgs[-1]
				REPEAT_MSGS[repeat_msg_key]['msgs'] = msgs
				if message.channel.last_message_id != msgs[-1].id:
					rxnEmoji = ['📜','🖨','❎','🔔','🔕']
				else:
					rxnEmoji = ['📜','❎','🔔','🔕']
			else:
				msgs = [await message.channel.send(embed=e) for e in embeds]
				if message.author.dm_channel is not None and message.channel.id == message.author.dm_channel.id:
					rxnEmoji = ['📜','🔔','🔕']
				else:
					rxnEmoji = ['📜','🔄','🔔','🔕']
		
			msg = msgs[-1]
		
			# to get actual list of reactions, need to re-fetch the message from the server
			cache_msg = await message.channel.fetch_message(msg.id)
			msgRxns = [str(r.emoji) for r in cache_msg.reactions]
		
			for e in msgRxns:
				if e not in rxnEmoji:
					await message_clear_reactions(msg, message, reactions=[e])
		
			for e in rxnEmoji:
				if e not in msgRxns:
					await msg.add_reaction(e)
		
			def check(reaction, user):
				return user.id in CONFIG['whitelist_user_ids'] and reaction.message.id == msg.id and str(reaction.emoji) in rxnEmoji
		
		try:
			reaction, user = await client.wait_for('reaction_add', timeout=60.0 if not repeat_msg_key else REPEAT_MSGS[repeat_msg_key]['freq'], check=check)
		except asyncio.TimeoutError:
			if not repeat_msg_key:
				await message_clear_reactions(msg, message)
				return
			pass
		else:
			if str(reaction.emoji) == '📜':
				if repeat_msg_key:
					await message_clear_reactions(msg, message, reactions=['📜'])
				else:
					await message_clear_reactions(msg, message)
				await legend(message)
				return
			elif str(reaction.emoji) == '🖨':
				await message_clear_reactions(msg, message, reactions=['🖨'])
				REPEAT_MSGS[repeat_msg_key]['reprint'] = True
				return
			elif str(reaction.emoji) == '❎':
				await message_clear_reactions(msg, message)
				REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
				return
			elif str(reaction.emoji) == '🔄':
				await message_clear_reactions(msg, message, reactions=['🔄'])
				await repeat_command(list_transfers, message=message, content=content, msg_list=msgs)
				return
			elif str(reaction.emoji) == '🔔':
				if len(torrents) > 0:
					for t in torrents:
						if t.hashString in TORRENT_NOTIFIED_USERS:
							TORRENT_NOTIFIED_USERS[t.hashString].append(message.author.id)
						else:
							TORRENT_NOTIFIED_USERS[t.hashString] = [message.author.id]
					embed = discord.Embed(title="🔔 Notifications enabled for:", description=",\n".join(["{}{}".format("" if len(torrents) == 1 else "**{}.**".format(i+1),j) for i,j in enumerate([t.name for t in torrents])]))
					await user.send(embed=embed)
			elif str(reaction.emoji) == '🔕':
				if len(torrents) > 0:
					for t in torrents:
						if t.hashString in TORRENT_OPTOUT_USERS:
							TORRENT_OPTOUT_USERS[t.hashString].append(message.author.id)
						else:
							TORRENT_OPTOUT_USERS[t.hashString] = [message.author.id]
					embed = discord.Embed(title="🔕 Notifications disabled for:", description=",\n".join(["{}{}".format("" if len(torrents) == 1 else "**{}.**".format(i+1),j) for i,j in enumerate([t.name for t in torrents])]))
					await user.send(embed=embed)
				
		if repeat_msg_key: # a final check to see if the user has cancelled the repeat by checking the count of the cancel reaction
			cache_msg = await message.channel.fetch_message(msg.id)
			for r in cache_msg.reactions:
				if r.count > 1:
					async for user in r.users():
						if user.id in CONFIG['whitelist_user_ids']:
							if str(r.emoji) == '🖨':
								REPEAT_MSGS[repeat_msg_key]['reprint'] = True
								await message_clear_reactions(msg, message, reactions=['🖨'])
							elif str(r.emoji) == '📜':
								await message_clear_reactions(msg, message, reactions=['📜'])
								await legend(message)
								return
							elif str(r.emoji) == '❎':
								await message_clear_reactions(msg, message)
								REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
								return
		else: # not a repeat message, so no need to keep the reactions
			await message_clear_reactions(msg, message)

@client.command(name='list', aliases=['l'], pass_context=True)
async def list_transfers_cmd(context, *, content="", repeat_msg_key=None):
	try:
		await list_transfers(context.message, content=content, repeat_msg_key=repeat_msg_key)
	except Exception as e:
		logger.warning("Exception in t/list: {}".format(e))

async def modify(message, content=""):
	if await CommandPrecheck(message):
		async with message.channel.typing():
			allOnly = content.strip() == ""
			torrents = []
			if not allOnly:
				id_list = strListToList(content)
				filter_by = None
				sort_by = None
				filter_regex = None
				num_results = None
				if not id_list:
					filter_by, sort_by, filter_regex, num_results = torGetListOpsFromStr(content)
					if filter_by is not None and filter_by == -1:
						await message.channel.send("Invalid filter specified. Choose one of {}".format(str(filter_names_full)))
						return
					if sort_by is not None and sort_by == -1:
						await message.channel.send("Invalid sort specified. Choose one of {}".format(str(sort_names)))
						return
					if num_results is not None and num_results <= 0:
						await message.channel.send("Must specify integer greater than 0 for `-N`!")
						return

				if CONFIG['delete_command_messages']:
					try:
						await message.delete()
					except:
						pass
			
				if TSCLIENT is None:
					reload_client()
			
				if len(REPEAT_MSGS) == 0:
					reload_client()
				torrents = TSCLIENT.get_torrents_by(filter_by=filter_by, sort_by=sort_by, filter_regex=filter_regex, id_list=id_list, num_results=num_results)

				if len(torrents) > 0:
					ops = ["pause","resume","remove","removedelete","verify"]
					opNames = ["pause","resume","remove","remove and delete","verify"]
					opEmoji = ['⏸','▶️','❌','🗑','🔬']
					opStr = "⏸pause ▶️resume ❌remove 🗑remove  and  delete 🔬verify"
					embeds = torList(torrents,author_name="Click a reaction to choose modification".format(len(torrents), '' if len(torrents)==1 else 's'),title="{} transfer{} matching '`{}`' will be modified".format(len(torrents), '' if len(torrents)==1 else 's', content))
				else:
					embed=discord.Embed(title="Modify transfers",color=0xb51a00)
					embed.set_author(name="No matching transfers found!", icon_url=CONFIG['logo_url'])
					embeds = [embed]
			else:
				try:
					await message.delete()
				except:
					pass
				ops = ["pauseall","resumeall"]
				opNames = ["pause all","resume all"]
				opEmoji = ['⏸','▶️']
				opStr = "⏸ pause or ▶️ resume all"
				embed=discord.Embed(title="React to choose modification",color=0xb51a00)
				embed.set_author(name="All transfers will be affected!", icon_url=CONFIG['logo_url'])
				embed.set_footer(text=opStr)
				embeds = [embed]
			msgs = [await message.channel.send(embed=e) for e in embeds]
		
			if not allOnly and len(torrents) == 0:
				return
		
			opEmoji.append('📜')
		
			msg = msgs[-1]
		
			for i in opEmoji:
				await msgs[-1].add_reaction(i)
			
			cache_msg = await message.channel.fetch_message(msg.id)
			for reaction in cache_msg.reactions:
				if reaction.count > 1:
					async for user in reaction.users():
						if user.id == message.author.id:
							if str(reaction.emoji) == opEmoji[-1]:
								await message_clear_reactions(msg, message)
								await legend(message)
							elif str(reaction.emoji) in opEmoji[:-1]:
								cmds = {i:j for i,j in zip(opEmoji,ops)}
								cmdNames = {i:j for i,j in zip(opEmoji,opNames)}
								cmd = cmds[str(reaction.emoji)]
								cmdName = cmdNames[str(reaction.emoji)]
		
								doContinue = True
								msg2 = None
								if "remove" in cmds[str(reaction.emoji)]:
									footerPrepend = ""
									if CONFIG['private_transfers_protected']:
										removeTorrents = [t for t in torrents if not t.isPrivate]
										if len(removeTorrents) != len(torrents):
											if CONFIG['private_transfer_protection_added_user_override']:
												oldTorrents = load_json(path=TORRENT_JSON)
												removeTorrents = [t for t in torrents if not t.isPrivate or ((t.hashString in oldTorrents and oldTorrents[t.hashString]['added_user'] == message.author.id) or (t.hashString in TORRENT_ADDED_USERS and TORRENT_ADDED_USERS[t.hashString] == message.author.id))]
												if len(removeTorrents) != len(torrents):
													torrents = removeTorrents
													footerPrepend = "(I'm not allowed to remove private transfers unless they were added by you, but those you added and the public ones)\n"
											else:
												torrents = removeTorrents
												footerPrepend = "(I'm not allowed to remove private transfers, but I'll do the public ones)\n"
									
									if "delete" in cmds[str(reaction.emoji)] and not CONFIG['whitelist_user_can_delete'] and message.author.id not in CONFIG['owner_user_ids']:
										# user may not be allowed to perform this operation. Check if they added any transfers, and whether the added_user_override is enabled.
										if CONFIG['whitelist_added_user_remove_delete_override']:
											# override is enabled, so reduce the list of torrents to be modified to those added by the user.
											# first get transfers from TORRENT_JSON
											oldTorrents = load_json(path=TORRENT_JSON)
											removeTorrents = [t for t in torrents if (t.hashString in oldTorrents and oldTorrents[t.hashString]['added_user'] == message.author.id) or (t.hashString in TORRENT_ADDED_USERS and TORRENT_ADDED_USERS[t.hashString] == message.author.id)]
											if len(removeTorrents) != len(torrents):
												if len(removeTorrents) > 0:
													torrents = removeTorrents
													footerPrepend = "(You can only remove and delete transfers added by you. Other transfers won't be affected.)\n"
												else:
													await message.channel.send("🚫 You can only remove and delete transfers added by you. If this isn't right, ask an admin to add you to the bot owner list.")
													await message_clear_reactions(msg, message)
													return
										else:
											# override not enabled, so user can't perform this operation
											await message.channel.send("🚫 You're not allowed to remove and delete transfers. If this isn't right, ask an admin to add you to the bot owner list or to enable the override for transfers added by you.")
											await message_clear_reactions(msg, message)
											return
									elif not CONFIG['whitelist_user_can_remove'] and message.author.id not in CONFIG['owner_user_ids']:
										# user may not be allowed to perform this operation. Check if they added any transfers, and whether the added_user_override is enabled.
										if CONFIG['whitelist_added_user_remove_delete_override']:
											# override is enabled, so reduce the list of torrents to be modified to those added by the user.
											# first get transfers from TORRENT_JSON
											oldTorrents = load_json(path=TORRENT_JSON)
											removeTorrents = [t for t in torrents if (t.hashString in oldTorrents and oldTorrents[t.hashString]['added_user'] == message.author.id) or (t.hashString in TORRENT_ADDED_USERS and TORRENT_ADDED_USERS[t.hashString] == message.author.id)]
											if len(removeTorrents) != len(torrents):
												if len(removeTorrents) > 0:
													torrents = removeTorrents
													footerPrepend = "(You can only remove transfers added by you. Other transfers won't be affected.)\n"
												else:
													await message.channel.send("🚫 You can only remove transfers added by you. If this isn't right, ask an admin to add you to the bot owner list.")
													await message_clear_reactions(msg, message)
													return
										else:
											# override not enabled, so user can't perform this operation
											await message.channel.send("🚫 You're not allowed to remove transfers. If this isn't right, ask an admin to add you to the bot owner list or to enable the override for transfers added by you.")
											await message_clear_reactions(msg, message)
											return
									embed=discord.Embed(title="Are you sure you wish to remove{} {} transfer{}?".format(' and DELETE' if 'delete' in cmds[str(reaction.emoji)] else '', len(torrents), '' if len(torrents)==1 else 's'),description="**This action is irreversible!**",color=0xb51a00)
									embed.set_footer(text=footerPrepend + "React ✅ to continue or ❌ to cancel")
									msg2 = await message.channel.send(embed=embed)

									for i in ['✅','❌']:
										await msg2.add_reaction(i)
				
									def check1(reaction, user):
										return user == message.author and reaction.message.id == msg2.id and str(reaction.emoji) in ['✅','❌']
									try:
										reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check1)
									except asyncio.TimeoutError:
										await message_clear_reactions(msg, message)
										await message_clear_reactions(msg2, message)
										doContinue = False
									else:
										doContinue = str(reaction.emoji) == '✅'
								if doContinue:
									async with message.channel.typing():
										await message.channel.send("{} Trying to {} transfer{}, please wait...".format(str(reaction.emoji), cmdName, 's' if allOnly or len(torrents) > 1 else ''))
										try:
											if "pause" in cmd:
												stop_torrents(torrents)
											elif "resume" in cmd:
												resume_torrents(torrents, start_all=("all" in cmd))
											elif "verify" in cmd:
												verify_torrents(torrents)
											else:
												remove_torrents(torrents,delete_files="delete" in cmd)
											
											ops = ["pause","resume","remove","removedelete","pauseall","resumeall","verify"]
											opNames = ["paused","resumed","removed","removed and deleted","paused","resumed","queued for verification"]
											opEmoji = ["⏸","▶️","❌","🗑","⏸","▶️","🔬"]
											ops = {i:j for i,j in zip(ops,opNames)}
											opEmoji = {i:j for i,j in zip(ops,opEmoji)}
											await message.channel.send("{} Transfer{} {}".format(str(reaction.emoji),'s' if allOnly or len(torrents) > 1 else '', ops[cmd]))
											await message_clear_reactions(msg, message)
											if msg2 is not None:
												await message_clear_reactions(msg2, message)
											return
										except Exception as e:
											await message.channel.send("⚠️ A problem occurred trying to modify transfer(s). You may need to try again... Sorry!".format(str(reaction.emoji), cmdName, 's' if allOnly or len(torrents) > 1 else ''))
											logger.warning("Exception in t/modify running command '{}': {}".format(cmd,e))
								else:
									await message.channel.send("❌ Cancelled!")
									await message_clear_reactions(msg, message)
									if msg2 is not None:
										await message_clear_reactions(msg2, message)
									return
	
			def check(reaction, user):
				return user == message.author and reaction.message.id == msg.id and str(reaction.emoji) in opEmoji
	
		try:
			reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check)
		except asyncio.TimeoutError:
			await message_clear_reactions(msg, message)
			return
		else:
			if str(reaction.emoji) == opEmoji[-1]:
				await message_clear_reactions(msg, message)
				await legend(message)
			elif str(reaction.emoji) in opEmoji[:-1]:
				cmds = {i:j for i,j in zip(opEmoji,ops)}
				cmdNames = {i:j for i,j in zip(opEmoji,opNames)}
				cmd = cmds[str(reaction.emoji)]
				cmdName = cmdNames[str(reaction.emoji)]
				
				msg2 = None
				doContinue = True
				if "remove" in cmds[str(reaction.emoji)]:
					footerPrepend = ""
					if CONFIG['private_transfers_protected']:
						removeTorrents = [t for t in torrents if not t.isPrivate]
						if CONFIG['private_transfers_protected']:
							removeTorrents = [t for t in torrents if not t.isPrivate]
							if len(removeTorrents) != len(torrents):
								if CONFIG['private_transfer_protection_added_user_override']:
									oldTorrents = load_json(path=TORRENT_JSON)
									removeTorrents = [t for t in torrents if not t.isPrivate or ((t.hashString in oldTorrents and oldTorrents[t.hashString]['added_user'] == message.author.id) or (t.hashString in TORRENT_ADDED_USERS and TORRENT_ADDED_USERS[t.hashString] == message.author.id))]
									if len(removeTorrents) != len(torrents):
										torrents = removeTorrents
										footerPrepend = "(I'm not allowed to remove private transfers unless they were added by you, but those you added and the public ones)\n"
								else:
									torrents = removeTorrents
									footerPrepend = "(I'm not allowed to remove private transfers, but I'll do the public ones)\n"
					if "delete" in cmds[str(reaction.emoji)] and not CONFIG['whitelist_user_can_delete'] and message.author.id not in CONFIG['owner_user_ids']:
						# user may not be allowed to perform this operation. Check if they added any transfers, and whether the added_user_override is enabled.
						if CONFIG['whitelist_added_user_remove_delete_override']:
							# override is enabled, so reduce the list of torrents to be modified to those added by the user.
							# first get transfers from TORRENT_JSON
							oldTorrents = load_json(path=TORRENT_JSON)
							removeTorrents = [t for t in torrents if (t.hashString in oldTorrents and oldTorrents[t.hashString]['added_user'] == message.author.id) or (t.hashString in TORRENT_ADDED_USERS and TORRENT_ADDED_USERS[t.hashString] == message.author.id)]
							if len(removeTorrents) != len(torrents):
								if len(removeTorrents) > 0:
									torrents = removeTorrents
									footerPrepend = "(You can only remove and delete transfers added by you. Other transfers won't be affected.)\n"
								else:
									await message.channel.send("🚫 You can only remove and delete transfers added by you. If this isn't right, ask an admin to add you to the bot owner list.")
									await message_clear_reactions(msg, message)
									return
						else:
							# override not enabled, so user can't perform this operation
							await message.channel.send("🚫 You're not allowed to remove and delete transfers. If this isn't right, ask an admin to add you to the bot owner list or to enable the override for transfers added by you.")
							await message_clear_reactions(msg, message)
							return
					elif not CONFIG['whitelist_user_can_remove'] and message.author.id not in CONFIG['owner_user_ids']:
						# user may not be allowed to perform this operation. Check if they added any transfers, and whether the added_user_override is enabled.
						if CONFIG['whitelist_added_user_remove_delete_override']:
							# override is enabled, so reduce the list of torrents to be modified to those added by the user.
							# first get transfers from TORRENT_JSON
							oldTorrents = load_json(path=TORRENT_JSON)
							removeTorrents = [t for t in torrents if (t.hashString in oldTorrents and oldTorrents[t.hashString]['added_user'] == message.author.id) or (t.hashString in TORRENT_ADDED_USERS and TORRENT_ADDED_USERS[t.hashString] == message.author.id)]
							if len(removeTorrents) != len(torrents):
								if len(removeTorrents) > 0:
									torrents = removeTorrents
									footerPrepend = "(You can only remove transfers added by you. Other transfers won't be affected.)\n"
								else:
									await message.channel.send("🚫 You can only remove transfers added by you. If this isn't right, ask an admin to add you to the bot owner list.")
									await message_clear_reactions(msg, message)
									return
						else:
							# override not enabled, so user can't perform this operation
							await message.channel.send("🚫 You're not allowed to remove transfers. If this isn't right, ask an admin to add you to the bot owner list or to enable the override for transfers added by you.")
							await message_clear_reactions(msg, message)
							return
					embed=discord.Embed(title="Are you sure you wish to remove{} {} transfer{}?".format(' and DELETE' if 'delete' in cmds[str(reaction.emoji)] else '', len(torrents), '' if len(torrents)==1 else 's'),description="**This action is irreversible!**",color=0xb51a00)
					embed.set_footer(text="react ✅ to continue or ❌ to cancel")
					msg2 = await message.channel.send(embed=embed)
	
					for i in ['✅','❌']:
						await msg2.add_reaction(i)
					
					def check1(reaction, user):
						return user == message.author and reaction.message.id == msg2.id and str(reaction.emoji) in ['✅','❌']
					try:
						reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check1)
					except asyncio.TimeoutError:
						await message_clear_reactions(msg, message)
						await message_clear_reactions(msg2, message)
						doContinue = False
					else:
						doContinue = str(reaction.emoji) == '✅'
				if doContinue:
					async with message.channel.typing():
						await message.channel.send("{} Trying to {} transfer{}, please wait...".format(str(reaction.emoji), cmdName, 's' if allOnly or len(torrents) > 1 else ''))
						try:
							if "pause" in cmd:
								stop_torrents(torrents)
							elif "resume" in cmd:
								resume_torrents(torrents, start_all=("all" in cmd))
							elif "verify" in cmd:
								verify_torrents(torrents)
							else:
								remove_torrents(torrents,delete_files="delete" in cmd)
							
							ops = ["pause","resume","remove","removedelete","pauseall","resumeall","verify"]
							opNames = ["paused","resumed","removed","removed and deleted","paused","resumed","queued for verification"]
							opEmoji = ["⏸","▶️","❌","🗑","⏸","▶️","🔬"]
							ops = {i:j for i,j in zip(ops,opNames)}
							opEmoji = {i:j for i,j in zip(ops,opEmoji)}
							await message.channel.send("{} Transfer{} {}".format(str(reaction.emoji),'s' if allOnly or len(torrents) > 1 else '', ops[cmd]))
							await message_clear_reactions(msg, message)
							if msg2 is not None:
								await message_clear_reactions(msg2, message)
							return
						except Exception as e:
							await message.channel.send("⚠️ A problem occurred trying to modify transfer(s). You may need to try again... Sorry!".format(str(reaction.emoji), cmdName, 's' if allOnly or len(torrents) > 1 else ''))
							logger.warning("Exception in t/modify running command '{}': {}".format(cmd,e))
				else:
					await message.channel.send("❌ Cancelled!")
					await message_clear_reactions(msg, message)
					if msg2 is not None:
						await message_clear_reactions(msg2, message)
					return
					
		await message_clear_reactions(msg, message)

@client.command(name='modify', aliases=['m'], pass_context=True)
async def modify_cmd(context, *, content=""):
	try:
		await modify(context.message, content=content)
	except Exception as e:
		logger.warning("Exception in t/modify: {}".format(e))
		

async def toggle_compact_out(message):
	global OUTPUT_MODE
	if OUTPUT_MODE == OutputMode.AUTO:
		if message.author.is_on_mobile():
			OUTPUT_MODE = OutputMode.DESKTOP
			await message.channel.send('🖥 Switched to desktop output')
		else:
			OUTPUT_MODE = OutputMode.MOBILE
			await message.channel.send('📱 Switched to mobile output')
	else:
		OUTPUT_MODE = OutputMode.AUTO
		await message.channel.send("🧠 Switched to smart selection of output (for you, {})".format('📱 mobile' if message.author.is_on_mobile() else '🖥 desktop'))
	return

@client.command(name='compact', aliases=['c'], pass_context=True)
async def toggle_compact_out_cmd(context):
	await toggle_compact_out(context.message)

async def LegendGetEmbed(embed_data=None):
	isCompact = False #COMPACT_OUTPUT
	joinChar = ',' if isCompact else '\n'
	if embed_data:
		embed = discord.Embed.from_dict(embed_data)
		embed.add_field(name='Symbol legend', value='', inline=False)	
	else:
		embed = discord.Embed(title='Symbol legend', color=0xb51a00)

	embed.add_field(name="Status 🔍", value=joinChar.join(["🔻—downloading","🌱—seeding","⏸—paused","🔬—verifying","🚧—queued","🏁—finished","↕️—any"]), inline=not isCompact)
	embed.add_field(name="Metrics 📊", value=joinChar.join(["⬇️—download  rate","⬆️—upload  rate","⏬—total  downloaded","⏫—total  uploaded","⚖️—seed  ratio","⏳—ETA"]), inline=not isCompact)
	embed.add_field(name="Modifications 🧰", value=joinChar.join(["⏸—pause","▶️—resume","❌—remove","🗑—remove  and  delete","🔬—verify"]), inline=not isCompact)
	embed.add_field(name="Error ‼️", value=joinChar.join(["✅—none","⚠️—tracker  warning","🌐—tracker  error","🖥—local  error"]), inline=not isCompact)
	embed.add_field(name="Activity 📈", value=joinChar.join(["🐢—stalled","🐇—active","🚀—running (rate>0)"]), inline=not isCompact)
	embed.add_field(name="Tracker 📡", value=joinChar.join(["🔐—private","🔓—public"]), inline=not isCompact)
	embed.add_field(name="Messages 💬", value=joinChar.join(["🔄—auto-update message","❎—cancel auto-update","🖨—reprint at bottom"]), inline=not isCompact)
	embed.add_field(name="Notifications 📣", value=joinChar.join(["🔔—enable","🔕—disable"]), inline=not isCompact)
	return embed

async def legend(message):
	if await CommandPrecheck(message):
		await message.channel.send(embed=await LegendGetEmbed())
	return

@client.command(name='legend', pass_context=True)
async def legend_cmd(context):
	await legend(context.message)

# @client.command(name='test', pass_context=True)
# async def test(context):
# 	if context.message.author.is_on_mobile():
# 		await context.channel.send('on mobile')
# 	else:
# 		await context.channel.send('on desktop')
# 	return

async def purge(message):
	def is_pinned(m):
		return m.pinned
	deleted = await message.channel.purge(limit=100, check=not is_pinned)
	await message.channel.send('Deleted {} message(s)'.format(len(deleted)))
	return
	
@client.command(name='purge', aliases=['p'], pass_context=True)
async def purge_cmd(context):
	await purge(context.message)

async def toggle_notifications(message):
	global CONFIG
	if message.author.dm_channel is not None and message.channel.id == message.author.dm_channel.id and CommandPrecheck(message):
		if message.author.id in CONFIG['notification_DM_opt_out_user_ids']:
			CONFIG['notification_DM_opt_out_user_ids'].remove(message.author.id)
			message.channel.send('🔕 DM notifications disabled')
		else:
			CONFIG['notification_DM_opt_out_user_ids'].append(message.author.id)
			message.channel.send('🔔 DM notifications enabled')
		generate_json(json_data=CONFIG, path=CONFIG_JSON, overwrite=True)
	elif CommandPrecheck(message, whitelist=CONFIG['owner_user_ids']):
		if CONFIG['notification_enabled_in_channel']:
			CONFIG['notification_enabled_in_channel'] = False
			message.channel.send('🔕 In-channel notifications disabled')
		else:
			CONFIG['notification_enabled_in_channel'] = True
			message.channel.send('🔔 In-channel notifications enabled')
		
	return

@client.command(name='notifications', aliases=['n'], pass_context=True)
async def toggle_notifications_cmd(context):
	await toggle_notifications(context.message)
	
async def toggle_dryrun(message):
	global CONFIG
	CONFIG['dryrun'] = not CONFIG['dryrun']
	await message.channel.send("Toggled dryrun to {}".format(CONFIG['dryrun']))
		
	return

@client.command(name='dryrun', pass_context=True)
async def toggle_dryrun_cmd(context):
	if CommandPrecheck(context.message, whitelist=CONFIG['owner_user_ids']):
		await toggle_dryrun(context.message)

@client.event
async def on_message(message):
	if message.author.id == client.user.id:
		return
	if message_has_torrent_file(message):
		await add(message, content=message.content)
	if message.author.dm_channel is not None and message.channel.id == message.author.dm_channel.id: # dm only
		if len(message.content) >= len("summary") and "summary" == message.content[:len("summary")]:
			await summary(message)
		elif len(message.content) >= len("list") and "list" in message.content[:len("list")]:
			await list_transfers(message, content=message.content[len("list"):].strip())
		elif len(message.content) >= len("add") and "add" in message.content[:len("add")]:
			await add(message, content=message.content[len("add"):].strip())
		elif len(message.content) >= len("modify") and "modify" in message.content[:len("modify")]:
			await modify(message, content=message.content[len("modify"):].strip())
		elif len(message.content) >= len("legend") and "legend" in message.content[:len("legend")]:
			await legend(message)
		elif len(message.content) >= len("help") and "help" in message.content[:len("help")]:
			await help(message, content=message.content[len("help"):].strip())
		elif len(message.content) >= len("notifications") and "notifications" in message.content[:len("notifications")]:
			await toggle_notifications(message)
		elif len(message.content) >= len("compact") and "compact" in message.content[:len("compact")]:
			await toggle_compact_out(message)
		else:
			await client.process_commands(message)
	elif not message.guild: # group dm only
		# do stuff here #
		pass
	else: # server text channel
		await client.process_commands(message)
	

client.remove_command('help')

async def help(message, content=""):
	if await CommandPrecheck(message):
		if content != "":
			if content in ["l","list"]:
				embed = discord.Embed(title='List transfers', color=0xb51a00)
				embed.set_author(name="List current transfers with sorting, filtering, and search options", icon_url=CONFIG['logo_url'])
				embed.add_field(name="Usage", value='`{0}list [--filter FILTER] [--sort SORT] [-N NUM_RESULTS] [NAME]`'.format(CONFIG['bot_prefix']), inline=False)
				embed.add_field(name="Filtering", value='`--filter FILTER` or `-f FILTER`\n`FILTER` is one of `{}`'.format(str(filter_names_full)), inline=False)
				embed.add_field(name="Sorting", value='`--sort SORT` or `-s SORT`\n`SORT` is one of `{}`'.format(str(sort_names)), inline=False)
				embed.add_field(name="Specify number of results to show", value='`-N NUM_RESULTS`\n`NUM_RESULTS` is an integer greater than 0', inline=False)
				embed.add_field(name="Searching by name", value='`NAME` is a regular expression used to search transfer names (no enclosing quotes; may contain spaces)', inline=False)
				embed.add_field(name="Examples", value="*List all transfers:* `{0}list`\n*Search using phrase 'ubuntu':* `{0}l ubuntu`\n*List downloading transfers:* `{0}l -f downloading`\n*List 10 most recently added transfers (sort transfers by age and specify number):* `{0}list --sort age -N 10`".format(CONFIG['bot_prefix']), inline=False)
				await message.channel.send(embed=embed)
			elif content in ["a","add"]:
				embed = discord.Embed(title='Add transfer', description="If multiple torrents are added, separate them by spaces", color=0xb51a00)
				embed.set_author(name="Add one or more specified torrents by magnet link, url to torrent file, or by attaching a torrent file", icon_url=CONFIG['logo_url'])
				embed.add_field(name="Usage", value='`{0}add TORRENT_FILE_URL_OR_MAGNET_LINK ...`\n`{0}a TORRENT_FILE_URL_OR_MAGNET_LINK ...`'.format(CONFIG['bot_prefix']), inline=False)
				embed.add_field(name="Examples", value="*Add download of Linux Ubuntu using link to torrent file:* `{0}add https://releases.ubuntu.com/20.04/ubuntu-20.04.1-desktop-amd64.iso.torrent`\n*Add download of ubuntu using the actual `.torrent` file:* Select the `.torrent` file as an attachmend in Discord, then enter `t/a` as the caption".format(CONFIG['bot_prefix']), inline=False)
				await message.channel.send(embed=embed)
			elif content in ["m","modify"]:
				embed = discord.Embed(title='Modify existing transfer(s)', color=0xb51a00)
				embed.set_author(name="Pause, resume, remove, or remove and delete specified transfer(s)", icon_url=CONFIG['logo_url'])
				embed.add_field(name="Usage", value='`{0}modify [LIST_OPTIONS] [TORRENT_ID_SPECIFIER]`'.format(CONFIG['bot_prefix']), inline=False)
				embed.add_field(name="Pause or resume ALL transfers", value="Simply run `{0}modify` to pause or resume all existing transfers".format(CONFIG['bot_prefix']), inline=False)
				embed.add_field(name="By list options", value='`LIST_OPTIONS` is a valid set of options to the `{0}list` command (see `{0}help list` for details)'.format(CONFIG['bot_prefix']), inline=False)
				embed.add_field(name="By ID specifier", value='`TORRENT_ID_SPECIFIER` is a valid transfer ID specifier—*e.g.* `1,3-5,9` to specify transfers 1, 3, 4, 5, and 9\n*Transfer IDs are the left-most number in the list of transfers (use* `{0}list` *to print full list)*'.format(CONFIG['bot_prefix']), inline=False)
				embed.add_field(name="Examples", value="`{0}modify`\n`{0}m seinfeld`\n`{0}m 23,34,36-42`\n`{0}m --filter downloading seinfeld`".format(CONFIG['bot_prefix']), inline=False)
				await message.channel.send(embed=embed)
		else:
			embed = discord.Embed(title='List of commands:', color=0xb51a00)
			embed.set_author(name='Transmission Bot: Manage torrent file transfers', icon_url=CONFIG['logo_url'])
			embed.add_field(name="Print summary of transfers", value="*print summary from all transfers, with followup options to list transfers*\n*ex.* `{0}summary` or `{0}s`".format(CONFIG['bot_prefix']), inline=False)
			embed.add_field(name="List torrent transfers", value="*list current transfers with sorting, filtering, and search options*\n*ex.* `{0}list [OPTIONS]` or `{0}l [OPTIONS]`".format(CONFIG['bot_prefix']), inline=False)
			embed.add_field(name="Add new torrent transfers", value="*add one or more specified torrents by magnet link, url to torrent file, or by attaching a torrent file*\n*ex.* `{0}add TORRENT ...` or `{0}a TORRENT ...`".format(CONFIG['bot_prefix']), inline=False)
			embed.add_field(name="Modify existing transfers", value="*pause, resume, remove, or remove and delete specified transfers*\n*ex.* `{0}modify [TORRENT]` or `{0}m [TORRENT]`".format(CONFIG['bot_prefix']), inline=False)
			embed.add_field(name='Toggle output style', value='*toggle between desktop (default), mobile (narrow), or smart selection of output style*\n*ex.* `{0}compact` or {0}c'.format(CONFIG['bot_prefix']), inline=False)
			embed.add_field(name='Toggle notifications', value='*toggle notifications regarding transfer state changes to be checked every {1} seconds (can be changed in config file)*\n*ex.* `{0}notifications` or {0}n'.format(CONFIG['bot_prefix'], CONFIG['notification_freq']), inline=False)
			embed.add_field(name='Show legend', value='*prints legend showing the meaning of symbols used in the output of other commands*\n*ex.* `{0}legend`'.format(CONFIG['bot_prefix']), inline=False)
			embed.add_field(name='Help - Gives this menu', value='*with optional details of specified command*\n*ex.* `{0}help` or `{0}help COMMAND`'.format(CONFIG['bot_prefix']), inline=False)
			
			# if not COMPACT_OUTPUT:
			# 	legendEmbed=await LegendGetEmbed()
			# 	embed.add_field(name=legendEmbed.title, value='', inline=False)
			# 	for f in legendEmbed.fields:
			# 		embed.add_field(name=f.name, value=f.value, inline=f.inline)
			
			await message.channel.send(embed=embed)

@client.command(name='help', description='Help HUD.', brief='HELPOOOO!!!', pass_context=True)
async def help_cmd(context, *, content=""):
	await help(context.message, content)

@client.event
async def on_command_error(context, error):
	# if command has local error handler, return
	if hasattr(context.command, 'on_error'):
		return
	
	# get the original exception
	error = getattr(error, 'original', error)
	if isinstance(error, commands.CommandNotFound):
		return
	if isinstance(error, commands.BotMissingPermissions):
		missing = [perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_perms]
		if len(missing) > 2:
			fmt = '{}, and {}'.format("**, **".join(missing[:-1]), missing[-1])
		else:
			fmt = ' and '.join(missing)
			_message = 'I need the **{}** permission(s) to run this command.'.format(fmt)
			await context.send(_message)
		return
	if isinstance(error, commands.DisabledCommand):
		await context.send('This command has been disabled.')
		return
	if isinstance(error, commands.CommandOnCooldown):
		await context.send("This command is on cooldown, please retry in {}s.".format(math.ceil(error.retry_after)))
		return
	if isinstance(error, commands.MissingPermissions):
		missing = [perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_perms]
		if len(missing) > 2:
			fmt = '{}, and {}'.format("**, **".join(missing[:-1]), missing[-1])
		else:
			await context.send(_message)
		return
	if isinstance(error, commands.UserInputError):
		await context.send("Invalid input.")
		await help(context)
		return
	if isinstance(error, commands.NoPrivateMessage):
		try:
			await context.author.send('This command cannot be used in direct messages.')
		except discord.Forbidden:
			pass
		return
	if isinstance(error, commands.CheckFailure):
		await context.send("You do not have permission to use this command.")
		return
	# ignore all other exception types, but print them to stderr
	print('Ignoring exception in command {}:'.format(context.command), file=sys.stderr)
	# traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
	
	if isinstance(error, commands.CommandOnCooldown):
		try:
			await context.message.delete()
		except:
			pass
		embed = discord.Embed(title="Error!", description='This command is on a {:.2f}s cooldown'.format(error.retry_after), color=0xb51a00)
		message = await context.message.channel.send(embed=embed)
		await asyncio.sleep(5)
		await message.delete()
	elif isinstance(error, commands.CommandNotFound):
		try:
			await context.message.delete()
		except:
			pass
		embed = discord.Embed(title="Error!", description="I don't know that command!", color=0xb51a00)
		message = await context.message.channel.send(embed=embed)
		await asyncio.sleep(2)
		await help_cmd(context)
	raise error

client.run(CONFIG['bot_token'])
