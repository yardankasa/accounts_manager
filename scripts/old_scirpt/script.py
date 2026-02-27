import logging as l
from telethon import TelegramClient as T
import schedule as s
import time as t
from dotenv import load_dotenv as ld
import os as o

ld()

l.basicConfig(filename='x.txt', level=l.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
n = l.getLogger()

a = o.getenv('API_ID')
b = o.getenv('API_HASH')
c = o.getenv('PHONE_NUMBER')
d = o.getenv('BOT_USERNAME')

e = T('ss', a, b)

f = 0
g = None

async def h():
    global f, g
    try:
        await e.start(c)
        print("Logged in!")
        i = await e.get_entity(d)

        async for j in e.iter_messages(i, limit=1):
            print(f"Received: {j.text}")
            if j.buttons:
                print("Buttons found.")
                for k in j.buttons:
                    for l in k:
                        print(f"Button: {l.text}")
                        if l.text and '✨ Фармить звезды' in l.text:
                            await l.click()
                            f += 1
                            print(f"Clicked: {l.text}")
                            n.info(f'Clicked: {l.text}')

                            if g is None:
                                await e.send_message(c, f"Stats: {f} clicks")
                                g = (await e.get_messages(c, limit=1))[0].id
                                print("First click - Stats sent.")
                            else:
                                await e.edit_message(c, g, f"Stats: {f} clicks")
                                print("Stats updated.")
                            break
            else:
                print("No buttons.")
    except Exception as x:
        n.error(f"Error: {x}")
        print(f"Error: {x}")

def y():
    print("Scheduled job...")
    e.loop.run_until_complete(h())

s.every(2).minutes.do(y)

while True:
    s.run_pending()
    t.sleep(1)