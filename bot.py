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

"""
Environmental variables (.env)
and other constant variables
"""
load_dotenv()
TOKEN = os.getenv('TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK')
DEBUG_ID = [109093669042151424]
CHECK_EVERY = 1800  # 30 minutes
TRUSTED_ROLE = 690223202420785260

"""
Variables used
"""
bot = commands.Bot(command_prefix='?')
ip = None  # will be used to keep track of the IP
ready = False  # Used for on_ready to only run some things once
loop_task = None  # The task that will be used to check the IP

# setting up logging
logging.basicConfig(level=logging.INFO, filename='discord.log', filemode='w',
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

    :return: discord.Color with random rgb values
    """
    return discord.Color.from_rgb(randint(0, 255), randint(0, 255), randint(0, 255))

async def grab_ip():
    """
    Grabs the IP from ipinfo.io

    :return: string IP
    """
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
        webhook = discord.Webhook.from_url(WEBHOOK_URL,
                                           adapter=discord.AsyncWebhookAdapter(session))
        await webhook.send(content, embed=embed, username=me.display_name, avatar_url=me.avatar_url_as())

async def check_ip():
    """
    This will check if the IP has changed.
    If it did, then it'll send a message out
    """
    global ip
    new_ip = await grab_ip()

    if ip is not None:
        if ip != new_ip:
            embed = discord.Embed(title='New IP', description=f'IP has changed. Please use || {new_ip} ||',
                                  color=grab_color())
            await send_webhook(embed=embed)

            ip = new_ip
    else:
        # if the global ip is None, that means the bot just started
        embed = discord.Embed(title='Bot started',
                              description='The bot has restarted / started. Just in case, here is the ip. '
                                          f'Please use || {new_ip} ||', color=grab_color())
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
@bot.check
async def only_trusted(ctx):
    """
    This will run before all the commands (global check)
    Basically, only users with trusted role and if its in a guild can run any command.

    Or if its a user in DEBUG_IDs, then we'll give them all the powers.
    Most likely its the developer / manager of the bot
    """
    if ctx.author.id in DEBUG_ID:
        return True

    if ctx.guild is not None:
        role = ctx.guild.get_role(TRUSTED_ROLE)
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
        loop_task = loop.create_task(check_loop(CHECK_EVERY))

    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_command_error(ctx, error):
    """
    This occurs when a command has an exception raised
    It will go through this event with the error variable
    """
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
        for user_id in DEBUG_ID:
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
async def grab_the_ip(ctx):
    """Gets the IP"""
    embed = discord.Embed(title='IP', description=f'|| {await grab_ip()} ||', color=grab_color())
    await ctx.send(embed=embed)

@bot.command()
async def status(ctx):
    """System's status. Note this will take 2 seconds or longer to run"""
    # grabbing the CPU / Memory status
    psutil.cpu_percent()
    # psutil documentation says to do a second call on cpu_percent
    # I can have the interval=1, but that would be a blocking call
    # so it'll be easier to have asyncio.sleep for 2 seconds, then call it again
    await asyncio.sleep(2)
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()

    # Converting memory from bytes -> GB
    mem_total = round(memory.total / 1024 / 1024 / 1024, 2)
    mem_available = round(memory.available / 1024 / 1024 / 1024, 2)

    embed = discord.Embed(title='System Status', color=grab_color())
    embed.add_field(name="CPU Usage Percent", value=f'{cpu_percent}%', inline=False)
    embed.add_field(name="Memory Usage", value=f'Available: {mem_available} GB, Total: {mem_total} GB',
                    inline=False)
    await ctx.send(embed=embed)

bot.run(TOKEN)
