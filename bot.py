import os
import psutil
import logging
import traceback
from random import randint
import asyncio
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

import python_source as source
import socket

"""
Variables used
"""
bot = commands.Bot(command_prefix='?')
ip = None  # will be used to keep track of the IP
ready = False  # Used for on_ready to only run some things once
loop_task = None  # The task that will be used to check the IP

"""
Environmental variables (.env)
and other constant variables
"""
IP_FILE = "ip"
class EnvValues:
    def __init__(self):
        load_dotenv()
        self.TOKEN = os.getenv('TOKEN')
        self.WEBHOOK_URL = os.getenv('WEBHOOK')
        self.DEBUG_ID = [int(developer) for developer in os.getenv("DEBUG_ID").split(",")]
        self.CHECK_EVERY = int(os.getenv('CHECK_EVERY'))
        self.TRUSTED_ROLE = int(os.getenv('TRUSTED_ROLE'))

# setting the config up
config = EnvValues()
# adding bot.config, so cogs can use these values
bot.config = config

# setting up logging
logging.basicConfig(level=logging.INFO, filename='discord.log', filemode='a',
                    format='%(asctime)s.%(msecs)d, %(levelname)s, %(filename)s, %(name)s | %(message)s',
                    datefmt='%m-%d-%Y, %H:%M:%S')
logger = logging.getLogger(__name__)

"""
Bot extensions / cogs
"""
bot.load_extension('jishaku')  # loading jishaku, its used for debugging

"""
Local methods
"""


def grab_color():
    """
    This is used for all of the embeds sent. Basically grabs a random color
    This is also placed in bot class (bot.grab_color) so it can be used by cogs / extensions

    :return: discord.Color with random rgb values
    """
    return discord.Color.from_rgb(randint(0, 255), randint(0, 255), randint(0, 255))


# referencing grab_color to bot.grab_color
bot.grab_color = grab_color


async def grab_ip():
    """
    Grabs the IP from ipinfo.io

    :return: string IP
    """
    logger.info("Grabbing the ip (grab_ip)")
    async with aiohttp.ClientSession() as session:
        async with session.get('http://ipinfo.io/ip') as resp:
            new_ip = await resp.text()
            new_ip = new_ip.replace('\n', '')

    return new_ip


async def send_webhook(content=None, embed=None):
    """
    Sends a webhook message to the WEBHOOK_URL
    or WEBHOOK in the .env

    :param content: message's content
    :param embed:   message's embed
    :return:        None
    """
    me = bot.user
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(config.WEBHOOK_URL,
                                           adapter=discord.AsyncWebhookAdapter(session))
        await webhook.send(content, embed=embed, username=me.display_name, avatar_url=me.avatar_url_as())


async def check_ip():
    """
    This will check if the IP has changed.
    If it did, then it'll send a message out

    This also manages the ip file. If there isn't a file, it'll create one and put the new IP in
    Then let users know. If there is an IP file, it will grab the variable ip and check if it changed.
    If it did, then it will edit the file with the new IP and let users know.

    Doing this so we don't spam the channel with "Bot started, here is the ip" every time the server
    restarts
    """
    global ip

    if ip is not None:
        new_ip = await grab_ip()

        if ip != new_ip:
            logger.info("New IP detected")
            embed = discord.Embed(title='New IP', description=f'IP has changed. Please use || {new_ip} ||',
                                  color=grab_color())
            await send_webhook(embed=embed)

            ip = new_ip
            with open(IP_FILE, 'w') as f:
                f.write(new_ip)
    else:
        # if the global ip is None, that means the bot just started
        logger.info("Bot started")
        try:
            with open(IP_FILE, 'r') as f:
                ip = f.readline()
                await check_ip()

        except FileNotFoundError:
            new_ip = await grab_ip()
            with open(IP_FILE, 'w') as f:
                f.write(new_ip)

            embed = discord.Embed(title='Bot started',
                                  description="Old IP file not found. Just in case, here is the ip. "
                                              f"Please use || {new_ip} ||", color=grab_color())
            await send_webhook(embed=embed)

            ip = new_ip


async def check_loop(time_wait):
    """
    This is the loop for checking the IP. It'll be a asyncio.Task in on_ready

    :param time_wait: seconds to wait for each time to check the IP
    """
    while True:
        try:
            await check_ip()
        except aiohttp.ClientConnectionError:
            # lost connection to the internet (maybe, or some other thing)
            # retrying every 10 seconds to see if its back up
            logger.error('Connection Error. Retrying in 10 seconds')
            await asyncio.sleep(10)
        except Exception as e:
            # unknown error happened. Since this will be a task, it won't have the exception in the console
            # so we'll get the traceback and put it in logger
            tb = traceback.TracebackException.from_exception(e)
            tb_msg = ''.join(tb.format())
            logger.error(tb_msg)

            await asyncio.sleep(time_wait)
        else:
            # no error happened, we can continue to wait
            await asyncio.sleep(time_wait)


"""
discord.py methods
"""


async def only_trusted(ctx):
    """
    removed -- This will run before all the commands (global check) -- removed

    This is a check for users with the trusted role. Only used by the IP command at the moment
    Basically, only users with trusted role and if its in a guild can run any command.

    Or if its a user in DEBUG_IDs, then we'll give them all the powers.
    Most likely its the developer / manager of the bot
    """
    if ctx.author.id in config.DEBUG_ID:
        return True

    if ctx.guild is not None:
        role = ctx.guild.get_role(config.TRUSTED_ROLE)
        return role in ctx.author.roles
    else:
        raise commands.NoPrivateMessage()


@bot.event
async def on_ready():
    """
    on_ready event. This will run whenever the discord bot is ready / connected.
    This can run multiple times, which is why there is a boolean ready variable, so we don't keep starting tasks.
    """
    global ready
    global loop_task

    if not ready:
        ready = True
        # creating the task
        loop = asyncio.get_event_loop()
        loop_task = loop.create_task(check_loop(config.CHECK_EVERY))

    print(f'Logged in as {bot.user.name}')


@bot.event
async def on_command_error(ctx, error):
    """
    This occurs when a command has an exception raised
    It will go through this event with the error variable
    """
    print(error)
    message = ''
    if isinstance(error, commands.NoPrivateMessage):
        message = f'{ctx.command.name} cannot be used in DMs'

    elif isinstance(error, commands.CommandNotFound):
        """
        We don't want to send a message. 
        Passing it so it doesn't reach else at the end
        """
        pass

    elif isinstance(error, commands.DisabledCommand):
        message = f'{ctx.command.name} has been disabled'

    elif isinstance(error, commands.MissingPermissions):
        message = f'You are Missing Permissions for {ctx.command.name}'

    elif isinstance(error, commands.BotMissingPermissions):
        message = f'I am Missing Permissions for {ctx.command.name}'

    elif isinstance(error, commands.CheckFailure):
        """
        passing it since its used for Checks 
        """
        pass

    elif isinstance(error, commands.CommandOnCooldown):
        message = f'This command is on a cooldown. Try again in {int(error.retry_after)} seconds'

    elif isinstance(error, commands.MissingRequiredArgument):
        message = str(error)
        await ctx.send_help(ctx.command)

    elif isinstance(error, commands.UserInputError):
        message = str(error)
        await ctx.send_help(ctx.command)

    else:
        # if I missed an exception, or its something else we'll just print it out or send the debug users the errors
        tb = ''.join(traceback.TracebackException.from_exception(error).format())
        message = f"Sorry, a unexpected error occurred."
        for user_id in config.DEBUG_ID:
            user = bot.get_user(user_id)
            try:
                await user.send(f'[Error Handler] [{ctx.author} used {ctx.command.name}]: {error}\n```py\n{tb}```')
            except discord.HTTPException:
                await user.send(f'[Error Handler] [{ctx.author} used {ctx.command.name}]:\
                {error}\n```Error too large, check server logs```')
        # logging it
        logging.warning(tb)

    if message != '':
        message = message.replace('@', '@\u200b')
        await ctx.send(embed=discord.Embed(description=message, color=discord.Color.red()))


@bot.command()
async def ping(ctx):
    """Pong!"""
    await ctx.send(f'Pong! {round(bot.latency * 1000)} ms')


@bot.command()
async def pong(ctx):
    """Ping!"""
    await ctx.send(f'Ping! {round(bot.latency * 1000)} ms')


@bot.command()
async def pancake(ctx):
    """Pancake"""
    await ctx.send('🥞')


@bot.command(name='ip')
@commands.check(only_trusted)
async def grab_the_ip(ctx):
    """Gets the IP"""
    try:
        await check_ip()
        embed = discord.Embed(title='IP', description=f'|| {ip} ||', color=grab_color())
    except aiohttp.ClientConnectionError:
        embed = discord.Embed(title="⚠️", description="Could not connect to ipinfo", color=grab_color())

    await ctx.send(embed=embed)


@bot.command()
async def status(ctx):
    """System's status. Note this will take 2.5 seconds or longer to run"""
    message = await ctx.send(embed=discord.Embed(color=grab_color(), description="Please wait..."))

    # grabbing the CPU / Memory status
    psutil.cpu_percent()

    # Querying the server. psutil needs time to calculate the cpu_percent (more info in the psutil documentation)
    query = source.Aquery("127.0.0.1", 27015, timeout=5.0)
    try:
        server = await query.info()
        server_info = f"**{server['name']}**\nPlayers: {server['players']} / {server['max_players']}"
    except socket.timeout:
        server_info = "Ark server is currently down"

    await asyncio.sleep(2.5)
    # after grabbing the server information, grab the cpu_percent. Should have enough time to calculate.
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()

    # Converting memory from bytes -> GB
    mem_total = round(memory.total / 1024 / 1024 / 1024, 2)
    mem_available = round(memory.available / 1024 / 1024 / 1024, 2)

    embed = discord.Embed(title='System Status', color=grab_color())
    embed.add_field(name="CPU Usage Percent", value=f'{cpu_percent}%', inline=False)
    embed.add_field(name="Memory Usage", value=f'Available: {mem_available} GB, Total: {mem_total} GB',
                    inline=False)
    embed.add_field(name="Server Info", value=server_info, inline=False)
    await message.edit(embed=embed)


bot.run(config.TOKEN)
