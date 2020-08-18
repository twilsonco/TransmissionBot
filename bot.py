""""
Copyright © twilsonco 2020
Description:
This is a discord bot to manage torrent transfers through the Transmission transmissionrpc python library.

Version: 1.0
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
from os.path import expanduser, join
import re
import datetime
import pytz
import platform
import transmissionrpc
import logging

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

logging.basicConfig(format='%(asctime)s %(message)s',filename=join(expanduser("~"),'transmissionbot.log'))



client = Bot(command_prefix=BOT_PREFIX)
TSCLIENT = None



logger = logging.getLogger('transmission_bot')
logger.setLevel(logging.INFO)
DEFAULT_REASON="TransmissionBot"

# Begin transmissionrpc functions, lovingly taken from https://github.com/leighmacdonald/transmission_scripts

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
			torrents = filter_torrents_by(torrents, key=getattr(Filter, filter_by))
			if sort_by is None:
				if filter_by == "downloading":
					sort_by = "speed_down"
				elif filter_by == "seeding":
					sort_by = "speed_up"
				elif filter_by in ["stopped","finished"]:
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

filter_names = (
	"all",
	"active",
	"downloading",
	"seeding",
	"stopped",
	"finished"
)

class Filter(object):
	"""A set of filtering operations that can be used against a list of torrent objects"""

	names = (
		"all",
		"active",
		"downloading",
		"seeding",
		"stopped",
		"finished"
	)

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
	
class Sort(object):
	""" Defines methods for sorting torrent sequences """

	names = (
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

def humanbytes(B):
	'Return the given bytes as a human friendly KB, MB, GB, or TB string'
	B = float(B)
	KB = float(1024)
	MB = float(KB ** 2) # 1,048,576
	GB = float(KB ** 3) # 1,073,741,824
	TB = float(KB ** 4) # 1,099,511,627,776

	if B < KB:
		return '{0} {1}'.format(B,'B')
	elif KB <= B < MB:
		return '{0:.2f} kB'.format(B/KB)
	elif MB <= B < GB:
		return '{0:.2f} MB'.format(B/MB)
	elif GB <= B < TB:
		return '{0:.2f} GB'.format(B/GB)
	elif TB <= B:
		return '{0:.2f} TB'.format(B/TB)
	  
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

# check that message author is allowed and message was sent in allowed channel
async def CommandPrecheck(context):
	if len(CHANNEL_IDS) > 0 and context.message.channel.id not in CHANNEL_IDS:
		await context.message.channel.send("I don't respond to commands in this channel...")
		return False
	elif context.message.author.id in BLACKLIST or (len(WHITELIST) > 0 and context.message.author.id not in WHITELIST):
		await context.message.channel.send("You're not allowed to use this...")
		return False
	return True
				
@client.command(name='add', pass_context=True)
async def add(context, *, content):
	if await CommandPrecheck(context):
		if content == "":
			await context.message.channel.send("Invalid string")
		else:
			torStr = None
			for t in content.strip().split(" "):
				await context.message.channel.send('Adding torrent {}\n Please wait...'.format(t))
				tor = add_torrent(t)
				if torStr:
					torStr += "\n{}" % tor.name
				else:
					torStr = tor.name
			await context.message.channel.send('✅ Added torrent{}:\n{}'.format("s" if len(content.strip().split(" ")) > 1 else "", torStr))
@client.command(name='a', pass_context=True)
async def a(context, *, content=""):
	await add(context, content=content)
	
# def torInfo(t):
# 	states = ('downloading', 'seeding', 'stopped', 'finished','all')
# 	stateEmoji = {i:j for i,j in zip(states,['🔻','🌱','⏸','🏁','🔁'])}
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
#
#
# 	embed=discord.Embed(title=t.name,color=0xb51a00)
#
# 	return embed


def torList(torrents, author_name="Torrent Transfers",title=None,description=None):
	states = ('downloading', 'seeding', 'stopped', 'finished','all')
	stateEmoji = {i:j for i,j in zip(states,['🔻','🌱','⏸','🏁','🔁'])}
	errorStrs = ['✅','⚠️','🌐','🖥']

	def torListLine(t):
		down = humanbytes(t.progress * 0.01 * t.totalSize)
		out = "{} {} {} {} ".format(stateEmoji[t.status],errorStrs[t.error],'🐢' if t.isStalled else '🐇', '🔒' if t.isPrivate else '🔓')
		if t.status == 'downloading':
			out += "{}/{} ⬇️ {}/s ⬆️ {}/s ⚖️ {:.2f}".format(down,humanbytes(t.totalSize),humanbytes(t.rateDownload),humanbytes(t.rateUpload),t.uploadRatio)
		elif t.status == 'seeding':
			out += "{} ⬆️ {}/s ⚖️ {:.2f}".format(humanbytes(t.totalSize),humanbytes(t.rateUpload),t.uploadRatio)
		elif t.status == 'stopped':
			out += "{}/{} ⚖️ {:.2f}".format(down,humanbytes(t.totalSize),t.uploadRatio)
		elif t.status == 'finished':
			out += "{} ⚖️ {:.2f}".format(humanbytes(t.totalSize),t.uploadRatio)
		
		return out
	
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
	
	if filter_by is not None and filter_by not in filter_names:
		return -1, None, None
	if sort_by is not None and sort_by not in sort_names:
		return None, -1, None
		
	return filter_by, sort_by, filter_regex

@client.command(name='list', pass_context=True)
async def list(context, *, content=""):
	if await CommandPrecheck(context):
		filter_by, sort_by, filter_regex = torGetListOpsFromStr(content)
		if filter_by == -1:
			await context.message.channel.send("Invalid filter specified. Choose one of {}".format(str(filter_names)))
			return
		if sort_by == -1:
			await context.message.channel.send("Invalid sort specified. Choose one of {}".format(str(sort_names)))
			return
		
		torrents = TSCLIENT.get_torrents_by(sort_by=sort_by, filter_by=filter_by, filter_regex=filter_regex)
		
		embeds = torList(torrents, title="{} transfer{} matching '`{}`'".format(len(torrents),'' if len(torrents)==1 else 's',content))
		
		for e in embeds:
			msg = await context.message.channel.send(embed=e)
		
		await msg.add_reaction('📜')
		
		def check(reaction, user):
			return user == context.message.author and str(reaction.emoji) == '📜'
		
		try:
			reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check)
		except asyncio.TimeoutError:
			pass
		else:
			if str(reaction.emoji) == '📜':
				await legend(context)
@client.command(name='l', pass_context=True)
async def l(context, *, content=""):
	await list(context, content=content)

def torSummary(torrents):
	states = ('downloading', 'seeding', 'paused', 'finished')
	numInState = [len([True for t in torrents if t.status == s]) for s in states]
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
	topRatios = "• Top {} ratio{}:".format(numTopRatios,"s" if numTopRatios > 0 else "")
	sortByRatio = sorted(torrents,key=lambda t:float(t.ratio),reverse=True)
	for i in range(numTopRatios):
		topRatios += "\n {:.1f} {:.35}{}".format(float(sortByRatio[i].ratio),sortByRatio[i].name,"..." if len(sortByRatio[i].name) > 35 else "")
	
	embed=discord.Embed(title="🌊 Torrent Summary", description="*React to see list of corresponding transfers*", color=0xb51a00)
	embed.set_thumbnail(url=LOGO_URL)
	embed.add_field(name="⬇️ {}/s".format(totDownRate), value="⬆️ {}/s".format(totUpRate), inline=False)
	embed.add_field(name="⏬ {} of {}".format(totDown,totSize), value="⏫ {}  ⚖️ {}".format(totUp,totRatio), inline=False)
	embed.add_field(name="🔁 {} transfer{} total".format(numTot,"" if numTot == 0 else "s"), value="🔻 {} 🌱 {} 🏁 {} ⏸ {}".format(numInState[0],numInState[1],numInState[3],numInState[2]), inline=False)
	embed.set_footer(text=topRatios+"\n📜 Symbol legend")
	# await context.message.channel.send(embed=embed)
	return embed,numInState
				
@client.command(name='summary', pass_context=True)
async def summary(context, *, content=""):
	if await CommandPrecheck(context):
		states = ('downloading', 'seeding', 'paused', 'finished','all')
		stateEmoji = ['🔻','🌱','⏸','🏁','🔃','📜']
		
		summary=torSummary(TSCLIENT.get_torrents())
		msg = await context.message.channel.send(embed=summary[0])
		for i in range(len(summary[1])):
			if summary[1][i] > 0:
				await msg.add_reaction(stateEmoji[i])
		for i in stateEmoji[-2:]:
			await msg.add_reaction(i)
		
		def check(reaction, user):
			return user == context.message.author and str(reaction.emoji) in stateEmoji
		
		try:
			reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check)
		except asyncio.TimeoutError:
			pass
		else:
			if str(reaction.emoji) in stateEmoji[:-1]:
				cmds = {i:j for i,j in zip(stateEmoji,('--filter downloading', '--filter seeding', '--filter stopped', '--filter finished', ''))}
				await list(context, content=cmds[str(reaction.emoji)])
			elif str(reaction.emoji) == stateEmoji[-1]:
				await legend(context)
@client.command(name='s', pass_context=True)
async def s(context, *, content=""):
	await summary(context, content=content)

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

@client.command(name='modify', pass_context=True)
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
					await context.message.channel.send("Invalid filter specified. Choose one of {}".format(str(filter_names)))
					return
				if sort_by == -1:
					await context.message.channel.send("Invalid sort specified. Choose one of {}".format(str(sort_names)))
					return
			# await context.message.channel.send("{} {} {} {}".format())
			# return
			torrents = TSCLIENT.get_torrents_by(filter_by=filter_by, sort_by=sort_by, filter_regex=filter_regex, id_list=id_list)

			if len(torrents) > 0:
				ops = ["pause","resume","remove","removedelete"]
				opNames = ["pause","resume","remove","remove and delete"]
				opEmoji = ['⏸','▶️','❌','🗑']
				opStr = "⏸pause ▶️resume ❌remove 🗑remove  and  delete"
				embeds = torList(torrents,author_name="Click a reaction to choose modification".format(len(torrents), '' if len(torrents)==1 else 's'),title="{} transfer{} matching '`{}`' will be modified".format(len(torrents), '' if len(torrents)==1 else 's', content))
				# embeds[-1].set_footer(text=opStr)
			else:
				embed=discord.Embed(title="Modify transfers",color=0xb51a00)
				embed.set_author(name="No matching transfers found!", icon_url=LOGO_URL)
				embeds = [embed]
		else:
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
		
		for i in opEmoji:
			await msgs[-1].add_reaction(i)
	
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
				cmd = cmds[str(reaction.emoji)]
			
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
					if "pause" in cmd:
						stop_torrents(torrents)
					elif "resume" in cmd:
						resume_torrents(torrents)
					else:
						remove_torrents(torrents,delete_files="delete" in cmd)
					
					ops = ["pause","resume","remove","removedelete","pauseall","resumeall"]
					opNames = ["paused","resumed","removed","removed and deleted","paused","resumed"]
					opEmoji = ["⏸","▶️","❌","🗑","⏸","▶️"]
					ops = {i:j for i,j in zip(ops,opNames)}
					opEmoji = {i:j for i,j in zip(ops,opEmoji)}
					await context.message.channel.send("{} Transfer{} {}".format(str(reaction.emoji),'s' if allOnly or len(torrents) > 1 else '', ops[cmd]))
				else:
					await context.message.channel.send("❌ Cancelled!")
@client.command(name='m', pass_context=True)
async def m(context, *, content=""):
	await modify(context, content=content)
	
@client.command(name='legend', pass_context=True)
async def legend(context):
	embed = discord.Embed(title='Symbol legend', color=0xb51a00)
	embed.add_field(name="Status", value="🔻—downloading\n🌱—seeding\n🏁—finished\n⏸—paused\n🔁—any", inline=True)
	embed.add_field(name="Error", value="✅—none\n⚠️—tracker  warning\n🌐—tracker  error\n🖥—local  error", inline=True)
	embed.add_field(name="Metrics", value="⬇️—(total)  download  rate\n⬆️—(total)  upload  rate\n⏬—total  downloaded\n⏫—total  uploaded\n⚖️—seed  ratio", inline=True)
	embed.add_field(name="Timeout", value="🐢—stalled\n🐇—running", inline=True)
	embed.add_field(name="Tracker", value="🔒—private\n🔓—public", inline=True)
	embed.add_field(name="Modifications", value="⏸—pause\n▶️—resume\n❌—remove\n🗑—remove  and  delete", inline=True)
	await context.message.channel.send(embed=embed)
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
				embed.add_field(name="Filtering", value='`--filter FILTER` or `-f FILTER`\n`FILTER` is one of `{}`'.format(str(filter_names)), inline=False)
				embed.add_field(name="Sorting", value='`--sort SORT` or `-s SORT`\n`SORT` is one of `{}`'.format(str(sort_names)), inline=False)
				embed.add_field(name="Searching by name", value='`NAME` is a regular expression used to search transfer names (no enclosing quotes; may contain spaces)', inline=False)
				embed.add_field(name="Examples", value="*List all transfers:* `{0}list`\n*Search using phrase 'ubuntu':* `{0}l ubuntu`\n*List downloading transfers:* `{0}l -f downloading`\n*Sort transfers by age:* `{0}list --sort age`".format(BOT_PREFIX), inline=False)
				await context.message.channel.send(embed=embed)
			elif content in ["a","add"]:
				embed = discord.Embed(title='Add transfer', description="If multiple torrents are added, separate them by spaces", color=0xb51a00)
				embed.set_author(name="Add one or more specified torrents by magnet link or url to torrent file", icon_url=LOGO_URL)
				embed.add_field(name="Usage", value='`{0}add TORRENT_FILE_URL_OR_MAGNET_LINK ...`\n`{0}a TORRENT_FILE_URL_OR_MAGNET_LINK ...`'.format(BOT_PREFIX), inline=False)
				embed.add_field(name="Examples", value="*Add download of ubuntu OS:* `{0}add https://releases.ubuntu.com/20.04/ubuntu-20.04.1-desktop-amd64.iso.torrent`".format(BOT_PREFIX), inline=False)
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
			embed.add_field(name="Add new torrent transfers", value="*add one or more specified torrents by magnet link or url to torrent file*\n*ex.* `{0}add TORRENT ...` or `{0}a TORRENT ...`".format(BOT_PREFIX), inline=False)
			embed.add_field(name="Modify existing transfers", value="*pause, resume, remove, or remove and delete specified transfers*\n*ex.* `{0}modify [TORRENT]` or `{0}m [TORRENT]`".format(BOT_PREFIX), inline=False)
			embed.add_field(name='Show legend', value='*prints legend showing the meaning of symbols used in the output of other commands*\n*ex.* `{0}legend`'.format(BOT_PREFIX), inline=False)
			embed.add_field(name='Help - Gives this menu', value='*with optional details of specified command*\n*ex.* `{0}help` or `{0}help COMMAND`'.format(BOT_PREFIX), inline=False)
		
			await context.message.channel.send(embed=embed)

@client.event
async def on_command_error(context, error):
	if isinstance(error, commands.CommandOnCooldown):
		await context.message.delete()
		embed = discord.Embed(title="Error!", description='This command is on a {:.2f}s cooldown'.format(error.retry_after), color=0xb51a00)
		message = await context.message.channel.send(embed=embed)
		await asyncio.sleep(5)
		await message.delete()
	elif isinstance(error, commands.CommandNotFound):
		await context.message.delete()
		embed = discord.Embed(title="Error!", description="I don't know that command!", color=0xb51a00)
		message = await context.message.channel.send(embed=embed)
		await asyncio.sleep(2)
		await help(context)
	raise error

client.run(TOKEN)
