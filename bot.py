""""
Copyright © twilsonco 2020
Description:
This is a discord bot to manage torrent transfers through the Transmission transmissionrpc python library.

Version: 1.1
"""

import discord
import asyncio
import aiohttp
import json
import subprocess
from discord.ext.commands import Bot
from discord.ext import commands
from platform import python_version
import os
import sys
from os.path import expanduser, join
import re
import datetime
import pytz
import platform
import secrets
import transmissionrpc
import logging
import base64
from enum import Enum

# BEGIN USER CONFIGURATION

BOT_PREFIX = 't/'
TOKEN = 'SECRET_TOKEN'
OWNERS = [OWNER_USER_IDS]
BLACKLIST = [USER_IDS]
WHITELIST = [USER_IDS]
CHANNEL_IDS=[CHANNEL_IDS]
LOGO_URL="https://iyanovich.files.wordpress.com/2009/04/transmission-logo.png"

TSCLIENT_CONFIG={
	'host': "10.0.1.2",
	'port': 9091,
	'user': "USERNAME",
	'password': "PASSWORD"
}

DRYRUN = False
REPEAT_FREQ = 2 # time in seconds to wait between reprinting repeated commands (in addition to the time requred to delete old message(s) and add reactions)
REPEAT_TIMEOUT = 3600 # time in seconds before a repeated command automatically stops
REPEAT_TIMEOUT_VERBOSE = True # if true, print a message when a repeated message times out
REPEAT_CANCEL_VERBOSE = True # same but for when user cancels a repeated message

logging.basicConfig(format='%(asctime)s %(message)s',filename=join(expanduser("~"),'transmissionbot.log'))

# END USER CONFIGURATION

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
	# 	'freq':REPEAT_FREQ,
	# 	'timeout':REPEAT_TIMEOUT,
	# 	'timeout_verbose':REPEAT_TIMEOUT_VERBOSE,
	# 	'cancel_verbose':REPEAT_CANCEL_VERBOSE,
	# 	'start_time':datetime.datetime.now(),
	# 	'do_repeat':True
	# }


client = Bot(command_prefix=BOT_PREFIX)
TSCLIENT = None

logger = logging.getLogger('transmission_bot')
logger.setLevel(logging.INFO)
DEFAULT_REASON="TransmissionBot"

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

	def get_torrents_by(self, sort_by=None, filter_by=None, reverse=False, filter_regex=None, id_list=None):
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
		torrents = self.get_torrents()
		if filter_regex:
			regex = re.compile(filter_regex, re.IGNORECASE)
			torrents = [tor for tor in torrents if regex.search(tor.name)]
		if id_list:
			torrents = [tor for tor in torrents if tor.id in id_list]
		if filter_by:
			for f in filter_by.split():
				if f in filter_names:
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
		return torrents
		
def make_client():
	""" Create a new transmission RPC client

	If you want to parse more than the standard CLI arguments, like when creating a new customized
	script, you can append your options to the argument parser.

	:param args: Optional CLI args passed in.
	:return:
	"""
	try:
		return TSClient(
			TSCLIENT_CONFIG['host'],
			port=TSCLIENT_CONFIG['port'],
			user=TSCLIENT_CONFIG['user'],
			password=TSCLIENT_CONFIG['password']
		)
	except:
		return None

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
		if not DRYRUN:
			TSCLIENT.stop_torrent(torrent.hashString)
	if not DRYRUN:
		TSCLIENT.remove_torrent(torrent.hashString, delete_data=delete_files)
	logger.info("Removed: {} {}\n\tReason: {}\n\tDry run: {}, Delete files: {}".format(torrent.name, torrent.hashString, reason, DRYRUN,delete_files))

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
			if not DRYRUN:
				TSCLIENT.stop_torrent(torrent.hashString)
			logger.info("Paused: {} {}\n\tReason: {}\n\tDry run: {}".format(torrent.name, torrent.hashString, reason, DRYRUN))

def resume_torrents(torrents=[], reason=DEFAULT_REASON):
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
		if torrent.status == "stopped":
			if not DRYRUN:
				TSCLIENT.start_torrent(torrent.hashString)
			logger.info("Resumed: {} {}\n\tReason: {}\n\tDry run: {}".format(torrent.name, torrent.hashString, reason, DRYRUN))

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
		if not DRYRUN:
			TSCLIENT.verify_torrent(torrent.hashString)
		logger.info("Verified: {} {}\n\tDry run: {}".format(torrent.name, torrent.hashString, DRYRUN))

def add_torrent(torStr):
	tor = None
	if torStr != "":
		tor = TSCLIENT.add_torrent(torStr)
	return tor


# Begin discord bot functions, adapted from https://github.com/kkrypt0nn/Python-Discord-Bot-Template

# async def status_task():
# 	while True:
# 		await client.change_presence(activity=discord.Game("{}help".format(BOT_PREFIX)))
# 		await asyncio.sleep(86400)

@client.event
async def on_ready():
	global TSCLIENT
	TSCLIENT = make_client()
	if TSCLIENT is None:
		print("Failed to create transmissionrpc client")
	else:
		# client.loop.create_task(status_task())
		await client.change_presence(activity=discord.Game("{}help".format(BOT_PREFIX)))
		print('Logged in as ' + client.user.name)
		print("Discord.py API version:", discord.__version__)
		print("Python version:", platform.python_version())
		print("Running on:", platform.system(), platform.release(), "(" + os.name + ")")
		print('-------------------')

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
	
async def IsCompactOutput(context):
	if OUTPUT_MODE == OutputMode.AUTO:
		if context.message.author.is_on_mobile():
			return OutputMode.MOBILE
		else:
			return OutputMode.DESKTOP
	else:
		return OUTPUT_MODE
		
# check that message author is allowed and message was sent in allowed channel
async def CommandPrecheck(context):
	# first set output mode
	global COMPACT_OUTPUT
	COMPACT_OUTPUT = await IsCompactOutput(context) == OutputMode.MOBILE
	
	if len(CHANNEL_IDS) > 0 and context.message.channel.id not in CHANNEL_IDS:
		await context.message.channel.send("I don't respond to commands in this channel...")
		return False
	elif context.message.author.id in BLACKLIST or (len(WHITELIST) > 0 and context.message.author.id not in WHITELIST):
		await context.message.channel.send("You're not allowed to use this...")
		return False
	return True
	
				
@client.command(name='add', aliases=['a'], pass_context=True)
async def add(context, *, content = ""):
	if await CommandPrecheck(context):
		torFileList = []
		for f in context.message.attachments:
			if len(f.filename) > 8 and f.filename[-8:].lower() == ".torrent":
				encodedBytes = base64.b64encode(await f.read())
				encodedStr = str(encodedBytes, "utf-8")
				torFileList.append({"name":f.filename,"content":encodedStr})
			continue
		if content == "" and len(torFileList) == 0:
			await context.message.channel.send("🚫 Invalid string")
		
		try:
			await context.message.delete()
		except:
			pass
		
		torStr = []
		for t in torFileList:
			# await context.message.channel.send('Adding torrent from file: {}\n Please wait...'.format(t["name"]))
			tor = add_torrent(t["content"])
			torStr.append("From file: {}".format(tor.name))
			
		for t in content.strip().split(" "):
			if len(t) > 5:
				# await context.message.channel.send('Adding torrent from link: {}\n Please wait...'.format(t))
				tor = add_torrent(t)
				torStr.append("From link: {}".format(tor.name))
				
		if len(torStr) > 0:
			await context.message.channel.send('✅ Added torrent{}:\n{}'.format("s" if len(torStr) > 1 else "", '\n'.join(torStr)))
		else:
			await context.message.channel.send('🚫 No torrents added!')
	
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
torStateEmoji = ('🔻','🌱','⏸','🩺','🚧','🏁',
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

def torSummary(torrents, repeat_msg_key=None):
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
	
	numTopRatios = min([len(torrents),5])
	topRatios = "• Top {} ratio{}:".format(numTopRatios,"s" if numTopRatios != 1 else "")
	sortByRatio = sorted(torrents,key=lambda t:float(t.ratio),reverse=True)
	for i in range(numTopRatios):
		topRatios += "\n {:.1f} {:.35}{}".format(float(sortByRatio[i].ratio),sortByRatio[i].name,"..." if len(sortByRatio[i].name) > 35 else "")
	
	embed=discord.Embed(description="*React to see list of corresponding transfers*", color=0xb51a00)
	embed.set_author(name="Torrent Summary 🌊", icon_url=LOGO_URL)
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
	embed.set_footer(text=topRatios+"\n📜 Symbol legend{}".format('\nUpdating every {} second{}—❎ to stop'.format(freq,'s' if freq != 1 else '') if repeat_msg_key else ', 🔄 to auto-update'))
	# await context.message.channel.send(embed=embed)
	return embed,numInState
				
@client.command(name='summary',aliases=['s'], pass_context=True)
async def summary(context, *, content="", repeat_msg_key=None):
	global REPEAT_MSGS
	if await CommandPrecheck(context):
		if not repeat_msg_key:
			try:
				await context.message.delete()
			except:
				pass
		
		stateEmojiFilterStartNum = 3 # the first emoji in stateEmoji that corresponds to a list filter
		ignoreEmoji = ('✅')
		
		summaryData=torSummary(TSCLIENT.get_torrents(), repeat_msg_key=repeat_msg_key)
		
		if repeat_msg_key:
			msg = REPEAT_MSGS[repeat_msg_key]['msgs'][0]
			if REPEAT_MSGS[repeat_msg_key]['reprint'] or (REPEAT_MSGS[repeat_msg_key]['pin_to_bottom'] and context.message.channel.last_message_id != msg.id):
				await msg.delete()
				msg = await context.message.channel.send(embed=summaryData[0])
				REPEAT_MSGS[repeat_msg_key]['msgs'] = [msg]
				REPEAT_MSGS[repeat_msg_key]['reprint'] = False
			else:
				await msg.edit(embed=summaryData[0])
			
			if context.message.channel.last_message_id != msg.id:
				stateEmoji = ('📜','🖨','❎','↕️') + torStateEmoji
				stateEmojiFilterStartNum += 1
			else:
				stateEmoji = ('📜','❎','↕️') + torStateEmoji
		else:
			stateEmoji = ('📜','🔄','↕️') + torStateEmoji
			msg = await context.message.channel.send(embed=summaryData[0])
		
		# to get actual list of reactions, need to re-fetch the message from the server
		cache_msg = await context.message.channel.fetch_message(msg.id)
		msgRxns = [str(r.emoji) for r in cache_msg.reactions]
		
		for i in stateEmoji[:stateEmojiFilterStartNum]:
			if i not in msgRxns:
				await msg.add_reaction(i)
		for i in range(len(summaryData[1])):
			if summaryData[1][i] > 0 and stateEmoji[i+stateEmojiFilterStartNum] not in ignoreEmoji and stateEmoji[i+stateEmojiFilterStartNum] not in msgRxns:
				await msg.add_reaction(stateEmoji[i+stateEmojiFilterStartNum])
			elif summaryData[1][i] == 0 and stateEmoji[i+stateEmojiFilterStartNum] in msgRxns:
				await msg.clear_reaction(stateEmoji[i+stateEmojiFilterStartNum])
			cache_msg = await context.message.channel.fetch_message(msg.id)
			for r in cache_msg.reactions:
				if r.count > 1:
					async for user in r.users():
						if user.id in WHITELIST:
							if str(r.emoji) == stateEmoji[0]:
								await legend(context)
								return
							elif str(r.emoji) == stateEmoji[1]:
								if repeat_msg_key:
									REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
									return
								else:
									await msg.clear_reaction('🔄')
									await repeat_command(summary, context=context, content=content, msg_list=[msg])
									return
							elif str(r.emoji) in stateEmoji[stateEmojiFilterStartNum-1:] and user.id == context.message.author.id:
								if repeat_msg_key:
									REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
								await list_transfers(context, content=torStateFilters[str(r.emoji)])
								return
		
		def check(reaction, user):
			return user == context.message.author and reaction.message.id == msg.id and str(reaction.emoji) in stateEmoji
		
		try:
			reaction, user = await client.wait_for('reaction_add', timeout=60.0 if not repeat_msg_key else REPEAT_MSGS[repeat_msg_key]['freq'], check=check)
		except asyncio.TimeoutError:
			pass
		else:
			if str(reaction.emoji) in stateEmoji[stateEmojiFilterStartNum-1:] and str(reaction.emoji) not in ignoreEmoji:
				if repeat_msg_key:
					REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
				await list_transfers(context, content=torStateFilters[str(reaction.emoji)])
				return
			elif str(reaction.emoji) == stateEmoji[0]:
				await legend(context)
				return
			elif str(reaction.emoji) == '❎':
				REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
				return
			elif str(reaction.emoji) == '🔄':
				await msg.clear_reaction('🔄')
				await repeat_command(summary, context=context, content=content, msg_list=[msg])
				return
			elif str(reaction.emoji) == '🖨':
				REPEAT_MSGS[repeat_msg_key]['reprint'] = True
				await msg.clear_reaction('🖨')
		if repeat_msg_key: # a final check to see if the user has cancelled the repeat by checking the count of the cancel reaction
			cache_msg = await context.message.channel.fetch_message(msg.id)
			for r in cache_msg.reactions:
				if r.count > 1:
					if str(r.emoji) == '❎':
						async for user in r.users():
							if user.id == context.message.author.id:
								REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
								return
					elif str(r.emoji) == '🖨':
						REPEAT_MSGS[repeat_msg_key]['reprint'] = True
						await msg.clear_reaction('🖨')
					elif str(r.emoji) in stateEmoji[stateEmojiFilterStartNum-1:]:
						async for user in r.users():
							if user.id == context.message.author.id:
								REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
								await list_transfers(context, content=torStateFilters[str(r.emoji)])
								return

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
	stateEmoji = {i:j for i,j in zip(states,['🔻','🌱','⏸','🏁','🩺','🩺','🚧','🚧'])}
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
				out += "{}%{} {}{}/s:*{}/s*:{:.1f}".format(int(t.progress), down, '' if eta <= 0 else '{}@'.format(humanseconds(eta)), humanbytes(t.rateDownload, d=0), humanbytes(t.rateUpload, d=0), t.uploadRatio)
			elif t.status == 'seeding':
				out += "{} *{}/s*:{:.1f}".format(down, humanbytes(t.rateUpload, d=0), t.uploadRatio)
			elif t.status == 'stopped':
				out += "{}%{} {:.1f}".format(int(t.progress), down, t.uploadRatio)
			elif t.status == 'finished':
				out += "{} {:.1f}".format(down, t.uploadRatio)
		else:
			down = humanbytes(t.progress * 0.01 * t.totalSize)
			out = "{} {} {} {} ".format(stateEmoji[t.status],errorStrs[t.error],'🚀' if t.rateDownload + t.rateUpload > 0 else '🐢' if t.isStalled else '🐇', '🔐' if t.isPrivate else '🔓')
			if t.status == 'downloading':
				out += "⏬ {}/{} ({:.1f}%) {}⬇️ {}/s ⬆️ *{}/s* ⚖️ *{:.2f}*".format(down,humanbytes(t.totalSize),t.progress, '' if eta <= 0 else '\n⏳ {} @ '.format(humanseconds(eta)), humanbytes(t.rateDownload),humanbytes(t.rateUpload),t.uploadRatio)
			elif t.status == 'seeding':
				out += "⏬ {} ⬆️ *{}/s* ⚖️ *{:.2f}*".format(humanbytes(t.totalSize),humanbytes(t.rateUpload),t.uploadRatio)
			elif t.status == 'stopped':
				out += "⏬ {}/{} ({:.1f}%) ⚖️ *{:.2f}*".format(down,humanbytes(t.totalSize),t.progress,t.uploadRatio)
			elif t.status == 'finished':
				out += "⏬ {} ⚖️ {:.2f}".format(humanbytes(t.totalSize),t.uploadRatio)
		
			if t.error != 0:
				out += "***Error:*** *{}*".format(t.errorString)
		return out
	
	if COMPACT_OUTPUT:
		nameList = ["{}){:.26}{}".format(t.id,t.name,"..." if len(t.name) > 26 else "") for t in torrents]
	else:
		nameList = ["{}) {:.245}{}".format(t.id,t.name,"..." if len(t.name) > 245 else "") for t in torrents]
	valList = [torListLine(t) for t in torrents]
	
	n = 0
	i = 0
	embeds = []
	if len(torrents) > 0:
		while i < len(torrents):
			embed=discord.Embed(title=title,description=description,color=0xb51a00)
			for j in range(25):
				embed.add_field(name=nameList[i],value=valList[i],inline=False)
				i += 1
				n += 1
				if n >= 25:
					n = 0
					break
				if i >= len(torrents):
					break
			embeds.append(embed)
	else:
		embeds.append(discord.Embed(title=title, description="No matching transfers found!", color=0xb51a00))

	embeds[-1].set_author(name=author_name, icon_url=LOGO_URL)
	embeds[-1].set_footer(text="📜 Symbol legend")
	
	return embeds

def torGetListOpsFromStr(listOpStr):
	filter_by = None
	sort_by = None
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
	
	filter_regex = " ".join(splitcontent).strip()
	if filter_regex == "":
		filter_regex = None
	
	if filter_by is not None and filter_by not in filter_names_full:
		return -1, None, None
	if sort_by is not None and sort_by not in sort_names:
		return None, -1, None
		
	return filter_by, sort_by, filter_regex

async def repeat_command(command, context, content="", msg_list=[]):
	global REPEAT_MSGS
	msg_key = secrets.token_hex()
	REPEAT_MSGS[msg_key] = {
		'msgs':msg_list,
		'command':command,
		'context':context,
		'content':content,
		'pin_to_bottom':False,
		'reprint': False,
		'freq':REPEAT_FREQ,
		'timeout':REPEAT_TIMEOUT,
		'timeout_verbose':REPEAT_TIMEOUT_VERBOSE,
		'cancel_verbose':REPEAT_CANCEL_VERBOSE,
		'start_time':datetime.datetime.now(),
		'do_repeat':True
	}
	
	while msg_key in REPEAT_MSGS:
		msg = REPEAT_MSGS[msg_key]
		if msg['do_repeat']:
			delta = datetime.datetime.now() - msg['start_time']
			if delta.seconds >= msg['timeout']:
				if msg['timeout_verbose']:
					await context.message.channel.send("❎ Auto-update timed out...")
				break
			else:
				try:
					await msg['command'](context=msg['context'], content=msg['content'], repeat_msg_key=msg_key)
				except:
					await asyncio.sleep(REPEAT_FREQ)
		else:
			if msg['cancel_verbose']:
				await context.message.channel.send("❎ Auto-update canceled...")
			break
			
	del REPEAT_MSGS[msg_key]
	return

@client.command(name='list', aliases=['l'], pass_context=True)
async def list_transfers(context, *, content="", repeat_msg_key=None):
	global REPEAT_MSGS
	if await CommandPrecheck(context):
		id_list = strListToList(content)
		filter_by = None
		sort_by = None
		filter_regex = None
		if not id_list:
			filter_by, sort_by, filter_regex = torGetListOpsFromStr(content)
			if filter_by == -1:
				await context.message.channel.send("Invalid filter specified. Choose one of {}".format(str(filter_names_full)))
				return
			if sort_by == -1:
				await context.message.channel.send("Invalid sort specified. Choose one of {}".format(str(sort_names)))
				return
		
		
		
		if not repeat_msg_key:
			try:
				await context.message.delete()
			except:
				pass
		
		torrents = TSCLIENT.get_torrents_by(sort_by=sort_by, filter_by=filter_by, filter_regex=filter_regex, id_list=id_list)
		
		embeds = torList(torrents, title="{} transfer{} matching '`{}`'".format(len(torrents),'' if len(torrents)==1 else 's',content))
		
		embeds[-1].set_footer(text="📜 Symbol legend{}".format('\nUpdating every {} second{}—❎ to stop'.format(REPEAT_MSGS[repeat_msg_key]['freq'],'s' if REPEAT_MSGS[repeat_msg_key]['freq'] != 1 else '') if repeat_msg_key else ', 🔄 to auto-update'))
		
		if repeat_msg_key:
			msgs = REPEAT_MSGS[repeat_msg_key]['msgs']
			if REPEAT_MSGS[repeat_msg_key]['reprint'] or (REPEAT_MSGS[repeat_msg_key]['pin_to_bottom'] and context.message.channel.last_message_id != msgs[-1].id):
				for m in msgs:
					await m.delete()
				msgs = []
				REPEAT_MSGS[repeat_msg_key]['reprint'] = False
			for i,e in enumerate(embeds):
				if i < len(msgs):
					await msgs[i].edit(embed=e)
					cache_msg = await context.message.channel.fetch_message(msgs[i].id)
					if i < len(embeds) - 1 and len(cache_msg.reactions) > 0:
						await cache_msg.clear_reactions()
				else:
					msgs.append(await context.message.channel.send(embed=e))
			if len(msgs) > len(embeds):
				for i in range(len(msgs) - len(embeds)):
					await msgs[-1].delete()
					del msgs[-1]
			REPEAT_MSGS[repeat_msg_key]['msgs'] = msgs
			if context.message.channel.last_message_id != msgs[-1].id:
				rxnEmoji = ['📜','🖨','❎']
			else:
				rxnEmoji = ['📜','❎']
		else:
			msgs = [await context.message.channel.send(embed=e) for e in embeds]
			rxnEmoji = ['📜','🔄']
		
		msg = msgs[-1]
		
		# to get actual list of reactions, need to re-fetch the message from the server
		cache_msg = await context.message.channel.fetch_message(msg.id)
		msgRxns = [str(r.emoji) for r in cache_msg.reactions]
		
		for e in msgRxns:
			if e not in rxnEmoji:
				await msg.clear_reaction(e)
		
		for e in rxnEmoji:
			if e not in msgRxns:
				await msg.add_reaction(e)
		
		def check(reaction, user):
			return user.id in WHITELIST and reaction.message.id == msg.id and str(reaction.emoji) in rxnEmoji
		
		try:
			reaction, user = await client.wait_for('reaction_add', timeout=60.0 if not repeat_msg_key else REPEAT_MSGS[repeat_msg_key]['freq'], check=check)
		except asyncio.TimeoutError:
			pass
		else:
			if str(reaction.emoji) == '📜':
				await legend(context)
			elif str(reaction.emoji) == '🖨':
				REPEAT_MSGS[repeat_msg_key]['reprint'] = True
				await msg.clear_reaction('🖨')
			elif str(reaction.emoji) == '❎':
				REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
				return
			elif str(reaction.emoji) == '🔄':
				await msg.clear_reaction('🔄')
				await repeat_command(list_transfers, context=context, content=content, msg_list=msgs)
				return
		if repeat_msg_key: # a final check to see if the user has cancelled the repeat by checking the count of the cancel reaction
			cache_msg = await context.message.channel.fetch_message(msg.id)
			for r in cache_msg.reactions:
				if r.count > 1:
					if str(r.emoji) == '🖨':
						REPEAT_MSGS[repeat_msg_key]['reprint'] = True
						await msg.clear_reaction('🖨')
					elif str(r.emoji) == '❎':
						async for user in r.users():
							if user.id in WHITELIST:
								REPEAT_MSGS[repeat_msg_key]['do_repeat'] = False
								return

@client.command(name='modify', aliases=['m'], pass_context=True)
async def modify(context, *, content=""):
	if await CommandPrecheck(context):
		allOnly = content.strip() == ""
		torrents = []
		if not allOnly:
			id_list = strListToList(content)
			filter_by = None
			sort_by = None
			filter_regex = None
			if not id_list:
				filter_by, sort_by, filter_regex = torGetListOpsFromStr(content)
				if filter_by == -1:
					await context.message.channel.send("Invalid filter specified. Choose one of {}".format(str(filter_names_full)))
					return
				if sort_by == -1:
					await context.message.channel.send("Invalid sort specified. Choose one of {}".format(str(sort_names)))
					return

			try:
				await context.message.delete()
			except:
				pass
			
			torrents = TSCLIENT.get_torrents_by(filter_by=filter_by, sort_by=sort_by, filter_regex=filter_regex, id_list=id_list)

			if len(torrents) > 0:
				ops = ["pause","resume","remove","removedelete","verify"]
				opNames = ["pause","resume","remove","remove and delete","verify"]
				opEmoji = ['⏸','▶️','❌','🗑','🩺']
				opStr = "⏸pause ▶️resume ❌remove 🗑remove  and  delete 🩺verify"
				embeds = torList(torrents,author_name="Click a reaction to choose modification".format(len(torrents), '' if len(torrents)==1 else 's'),title="{} transfer{} matching '`{}`' will be modified".format(len(torrents), '' if len(torrents)==1 else 's', content))
			else:
				embed=discord.Embed(title="Modify transfers",color=0xb51a00)
				embed.set_author(name="No matching transfers found!", icon_url=LOGO_URL)
				embeds = [embed]
		else:
			try:
				await context.message.delete()
			except:
				pass
			ops = ["pauseall","resumeall"]
			opNames = ["pause all","resume all"]
			opEmoji = ['⏸','▶️']
			opStr = "⏸ pause or ▶️ resume all"
			embed=discord.Embed(title="React to choose modification",color=0xb51a00)
			embed.set_author(name="All transfers will be affected!", icon_url=LOGO_URL)
			embed.set_footer(text=opStr)
			embeds = [embed]
		msgs = [await context.message.channel.send(embed=e) for e in embeds]
		
		if not allOnly and len(torrents) == 0:
			return
		
		opEmoji.append('📜')
		
		msg = msgs[-1]
		
		for i in opEmoji:
			await msgs[-1].add_reaction(i)
			cache_msg = await context.message.channel.fetch_message(msg.id)
			for reaction in cache_msg.reactions:
				if reaction.count > 1:
					async for user in reaction.users():
						if user.id == context.message.author.id:
							if str(reaction.emoji) == opEmoji[-1]:
								await legend(context)
							elif str(reaction.emoji) in opEmoji[:-1]:
								cmds = {i:j for i,j in zip(opEmoji,ops)}
								cmdNames = {i:j for i,j in zip(opEmoji,opNames)}
								cmd = cmds[str(reaction.emoji)]
								cmdName = cmdNames[str(reaction.emoji)]
			
								doContinue = True
								if "remove" in cmds[str(reaction.emoji)]:
									embed=discord.Embed(title="Are you sure you wish to remove{} {} transfer{}?".format(' and DELETE' if 'delete' in cmds[str(reaction.emoji)] else '', len(torrents), '' if len(torrents)==1 else 's'),description="**This action is irreversible!**",color=0xb51a00)
									embed.set_footer(text="react ✅ to continue or ❌ to cancel")
									msg = await context.message.channel.send(embed=embed)
	
									for i in ['✅','❌']:
										await msg.add_reaction(i)
					
									def check1(reaction, user):
										return user == context.message.author and str(reaction.emoji) in ['✅','❌']
									try:
										reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check1)
									except asyncio.TimeoutError:
										doContinue = False
									else:
										doContinue = str(reaction.emoji) == '✅'
								if doContinue:
									await context.message.channel.send("{} Trying to {} transfer{}, please wait...".format(str(reaction.emoji), cmdName, 's' if allOnly or len(torrents) > 1 else ''))
									if "pause" in cmd:
										stop_torrents(torrents)
									elif "resume" in cmd:
										resume_torrents(torrents)
									elif "verify" in cmd:
										verify_torrents(torrents)
									else:
										remove_torrents(torrents,delete_files="delete" in cmd)
					
									ops = ["pause","resume","remove","removedelete","pauseall","resumeall","verify"]
									opNames = ["paused","resumed","removed","removed and deleted","paused","resumed","queued for verification"]
									opEmoji = ["⏸","▶️","❌","🗑","⏸","▶️","🩺"]
									ops = {i:j for i,j in zip(ops,opNames)}
									opEmoji = {i:j for i,j in zip(ops,opEmoji)}
									await context.message.channel.send("{} Transfer{} {}".format(str(reaction.emoji),'s' if allOnly or len(torrents) > 1 else '', ops[cmd]))
									return
								else:
									await context.message.channel.send("❌ Cancelled!")
									return
	
		def check(reaction, user):
			return user == context.message.author and str(reaction.emoji) in opEmoji
	
		try:
			reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check)
		except asyncio.TimeoutError:
			return
		else:
			if str(reaction.emoji) == opEmoji[-1]:
				await legend(context)
			elif str(reaction.emoji) in opEmoji[:-1]:
				cmds = {i:j for i,j in zip(opEmoji,ops)}
				cmdNames = {i:j for i,j in zip(opEmoji,opNames)}
				cmd = cmds[str(reaction.emoji)]
				cmdName = cmdNames[str(reaction.emoji)]
			
				doContinue = True
				if "remove" in cmds[str(reaction.emoji)]:
					embed=discord.Embed(title="Are you sure you wish to remove{} {} transfer{}?".format(' and DELETE' if 'delete' in cmds[str(reaction.emoji)] else '', len(torrents), '' if len(torrents)==1 else 's'),description="**This action is irreversible!**",color=0xb51a00)
					embed.set_footer(text="react ✅ to continue or ❌ to cancel")
					msg = await context.message.channel.send(embed=embed)
	
					for i in ['✅','❌']:
						await msg.add_reaction(i)
					
					def check1(reaction, user):
						return user == context.message.author and str(reaction.emoji) in ['✅','❌']
					try:
						reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check1)
					except asyncio.TimeoutError:
						doContinue = False
					else:
						doContinue = str(reaction.emoji) == '✅'
				if doContinue:
					await context.message.channel.send("{} Trying to {} transfer{}, please wait...".format(str(reaction.emoji), cmdName, 's' if allOnly or len(torrents) > 1 else ''))
					if "pause" in cmd:
						stop_torrents(torrents)
					elif "resume" in cmd:
						resume_torrents(torrents)
					elif "verify" in cmd:
						verify_torrents(torrents)
					else:
						remove_torrents(torrents,delete_files="delete" in cmd)
					
					ops = ["pause","resume","remove","removedelete","pauseall","resumeall","verify"]
					opNames = ["paused","resumed","removed","removed and deleted","paused","resumed","queued for verification"]
					opEmoji = ["⏸","▶️","❌","🗑","⏸","▶️","🩺"]
					ops = {i:j for i,j in zip(ops,opNames)}
					opEmoji = {i:j for i,j in zip(ops,opEmoji)}
					await context.message.channel.send("{} Transfer{} {}".format(str(reaction.emoji),'s' if allOnly or len(torrents) > 1 else '', ops[cmd]))
					return
				else:
					await context.message.channel.send("❌ Cancelled!")
					return

@client.command(name='compact', aliases=['c'], pass_context=True)
async def toggle_compact_out(context):
	global OUTPUT_MODE
	if OUTPUT_MODE == OutputMode.AUTO:
		if context.message.author.is_on_mobile():
			OUTPUT_MODE = OutputMode.DESKTOP
			await context.message.channel.send('🖥 Switched to desktop output')
		else:
			OUTPUT_MODE = OutputMode.MOBILE
			await context.message.channel.send('📱 Switched to mobile output')
	else:
		OUTPUT_MODE = OutputMode.AUTO
		await context.message.channel.send("🧠 Switched to smart selection of output (for you, {})".format('📱 mobile' if context.message.author.is_on_mobile() else '🖥 desktop'))
	return

async def LegendGetEmbed(embed_data=None):
	isCompact = False #COMPACT_OUTPUT
	joinChar = ',' if isCompact else '\n'
	if embed_data:
		embed = discord.Embed.from_dict(embed_data)
		embed.add_field(name='Symbol legend', value='', inline=False)	
	else:
		embed = discord.Embed(title='Symbol legend', color=0xb51a00)

	embed.add_field(name="Status", value=joinChar.join(["🔻—downloading","🌱—seeding","⏸—paused","🩺—verifying","🚧—queued","🏁—finished","↕️—any"]), inline=not isCompact)
	embed.add_field(name="Metrics", value=joinChar.join(["⬇️—download  rate","⬆️—upload  rate","⏬—total  downloaded","⏫—total  uploaded","⚖️—seed  ratio","⏳—ETA"]), inline=not isCompact)
	embed.add_field(name="Modifications", value=joinChar.join(["⏸—pause","▶️—resume","❌—remove","🗑—remove  and  delete","🩺—verify"]), inline=not isCompact)
	embed.add_field(name="Error", value=joinChar.join(["✅—none","⚠️—tracker  warning","🌐—tracker  error","🖥—local  error"]), inline=not isCompact)
	embed.add_field(name="Activity", value=joinChar.join(["🐢—stalled","🐇—active","🚀—running (rate>0)"]), inline=not isCompact)
	embed.add_field(name="Tracker", value=joinChar.join(["🔐—private","🔓—public"]), inline=not isCompact)
	embed.add_field(name="Messages", value=joinChar.join(["🔄—auto-update message","❎—cancel auto-update","🖨—reprint at bottom"]), inline=not isCompact)
	return embed

@client.command(name='legend', pass_context=True)
async def legend(context):
	if await CommandPrecheck(context):
		await context.message.channel.send(embed=await LegendGetEmbed())
	return

# @client.command(name='test', pass_context=True)
# async def test(context):
# 	if context.message.author.is_on_mobile():
# 		await context.channel.send('on mobile')
# 	else:
# 		await context.channel.send('on desktop')
# 	return

@client.command(name='purge', aliases=['p'], pass_context=True)
async def purge(context):
	def is_pinned(m):
		return m.pinned
	deleted = await context.channel.purge(limit=100, check=not is_pinned)
	await context.channel.send('Deleted {} message(s)'.format(len(deleted)))
	return

client.remove_command('help')

@client.command(name='help', description='Help HUD.', brief='HELPOOOO!!!', pass_context=True)
async def help(context, *, content=""):
	if await CommandPrecheck(context):
		if content != "":
			if content in ["l","list"]:
				embed = discord.Embed(title='List transfers', color=0xb51a00)
				embed.set_author(name="List current transfers with sorting, filtering, and search options", icon_url=LOGO_URL)
				embed.add_field(name="Usage", value='`{0}list [--filter FILTER] [--sort SORT] [NAME]`'.format(BOT_PREFIX), inline=False)
				embed.add_field(name="Filtering", value='`--filter FILTER` or `-f FILTER`\n`FILTER` is one of `{}`'.format(str(filter_names_full)), inline=False)
				embed.add_field(name="Sorting", value='`--sort SORT` or `-s SORT`\n`SORT` is one of `{}`'.format(str(sort_names)), inline=False)
				embed.add_field(name="Searching by name", value='`NAME` is a regular expression used to search transfer names (no enclosing quotes; may contain spaces)', inline=False)
				embed.add_field(name="Examples", value="*List all transfers:* `{0}list`\n*Search using phrase 'ubuntu':* `{0}l ubuntu`\n*List downloading transfers:* `{0}l -f downloading`\n*Sort transfers by age:* `{0}list --sort age`".format(BOT_PREFIX), inline=False)
				await context.message.channel.send(embed=embed)
			elif content in ["a","add"]:
				embed = discord.Embed(title='Add transfer', description="If multiple torrents are added, separate them by spaces", color=0xb51a00)
				embed.set_author(name="Add one or more specified torrents by magnet link, url to torrent file, or by attaching a torrent file", icon_url=LOGO_URL)
				embed.add_field(name="Usage", value='`{0}add TORRENT_FILE_URL_OR_MAGNET_LINK ...`\n`{0}a TORRENT_FILE_URL_OR_MAGNET_LINK ...`'.format(BOT_PREFIX), inline=False)
				embed.add_field(name="Examples", value="*Add download of Linux Ubuntu using link to torrent file:* `{0}add https://releases.ubuntu.com/20.04/ubuntu-20.04.1-desktop-amd64.iso.torrent`\n*Add download of ubuntu using the actual `.torrent` file:* Select the `.torrent` file as an attachmend in Discord, then enter `t/a` as the caption".format(BOT_PREFIX), inline=False)
				await context.message.channel.send(embed=embed)
			elif content in ["m","modify"]:
				embed = discord.Embed(title='Modify existing transfer(s)', color=0xb51a00)
				embed.set_author(name="Pause, resume, remove, or remove and delete specified transfer(s)", icon_url=LOGO_URL)
				embed.add_field(name="Usage", value='`{0}modify [LIST_OPTIONS] [TORRENT_ID_SPECIFIER]`'.format(BOT_PREFIX), inline=False)
				embed.add_field(name="Pause or resume ALL transfers", value="Simply run `{0}modify` to pause or resume all existing transfers".format(BOT_PREFIX), inline=False)
				embed.add_field(name="By list options", value='`LIST_OPTIONS` is a valid set of options to the `{0}list` command (see `{0}help list` for details)'.format(BOT_PREFIX), inline=False)
				embed.add_field(name="By ID specifier", value='`TORRENT_ID_SPECIFIER` is a valid transfer ID specifier—*e.g.* `1,3-5,9` to specify transfers 1, 3, 4, 5, and 9\n*Transfer IDs are the left-most number in the list of transfers (use* `{0}list` *to print full list)*'.format(BOT_PREFIX), inline=False)
				embed.add_field(name="Examples", value="`{0}modify`\n`{0}m seinfeld`\n`{0}m 23,34,36-42`\n`{0}m --filter downloading seinfeld`".format(BOT_PREFIX), inline=False)
				await context.message.channel.send(embed=embed)
		else:
			embed = discord.Embed(title='List of commands:', color=0xb51a00)
			embed.set_author(name='Transmission Bot: Manage torrent file transfers', icon_url=LOGO_URL)
			embed.add_field(name="Print summary of transfers", value="*print summary from all transfers, with followup options to list transfers*\n*ex.* `{0}summary` or `{0}s`".format(BOT_PREFIX), inline=False)
			embed.add_field(name="List torrent transfers", value="*list current transfers with sorting, filtering, and search options*\n*ex.* `{0}list [OPTIONS]` or `{0}l [OPTIONS]`".format(BOT_PREFIX), inline=False)
			embed.add_field(name="Add new torrent transfers", value="*add one or more specified torrents by magnet link, url to torrent file, or by attaching a torrent file*\n*ex.* `{0}add TORRENT ...` or `{0}a TORRENT ...`".format(BOT_PREFIX), inline=False)
			embed.add_field(name="Modify existing transfers", value="*pause, resume, remove, or remove and delete specified transfers*\n*ex.* `{0}modify [TORRENT]` or `{0}m [TORRENT]`".format(BOT_PREFIX), inline=False)
			embed.add_field(name='Toggle output style', value='*toggle between desktop (default), mobile (narrow), or smart selection of output style*\n*ex.* `{0}compact` or {0}c'.format(BOT_PREFIX), inline=False)
			embed.add_field(name='Show legend', value='*prints legend showing the meaning of symbols used in the output of other commands*\n*ex.* `{0}legend`'.format(BOT_PREFIX), inline=False)
			embed.add_field(name='Help - Gives this menu', value='*with optional details of specified command*\n*ex.* `{0}help` or `{0}help COMMAND`'.format(BOT_PREFIX), inline=False)
			
			# if not COMPACT_OUTPUT:
			# 	legendEmbed=await LegendGetEmbed()
			# 	embed.add_field(name=legendEmbed.title, value='', inline=False)
			# 	for f in legendEmbed.fields:
			# 		embed.add_field(name=f.name, value=f.value, inline=f.inline)
			
			await context.message.channel.send(embed=embed)

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
		await help(context)
	raise error

client.run(TOKEN)
