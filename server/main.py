import asyncio
from plugins.mediacontroller_plugin import MediaController

# quick demo
async def demo():
    mc = MediaController()
    ml = await mc.get_media_list()
    for item in ml:
        print(item["id"], item["title"], item["source"], item["volume"])
    if ml:
        # optimistic demo: pause first session
        # await mc.try_pause(ml[0]["session"])
        # set volume (best-effort)
        mc.try_set_volume(ml[0]["session"], 0)

if __name__ == "__main__":
    asyncio.run(demo())