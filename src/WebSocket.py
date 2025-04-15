import asyncio
import websockets
import ormsgpack
import subprocess
import shutil
from openai import AsyncOpenAI
import os

from dotenv import load_dotenv
# 加载环境变量
load_dotenv()

# 获取API密钥
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AMAP_API_KEY = os.getenv("AMAP_API_KEY")
AMAP_JS_API_KEY = os.getenv("AMAP_JS_API_KEY", AMAP_API_KEY)  # 如果没有特定的JS API KEY，使用常规的KEY
AMAP_JS_API_PWD = os.getenv("AMAP_JS_API_PWD")
FISH_API_KEY = os.getenv("FISH_API_KEY")
REFERENCE_ID = os.getenv("REFERENCE_ID")  # 默认值为可莉的ID


aclient = AsyncOpenAI()


def is_installed(lib_name):
    """Check if a system command is available"""
    return shutil.which(lib_name) is not None


async def stream_audio(audio_stream):
    """
    Stream audio data using mpv player
    Args:
        audio_stream: Async iterator yielding audio chunks
    """
    mpv_path = os.path.join(os.getcwd(), 'mpv-x86_64-20250415-git-4697f7c', 'mpv.exe')
    if not os.path.exists(mpv_path):
        raise ValueError(
            f"mpv executable not found at {mpv_path}. "
            "Please ensure mpv is properly installed in the correct location."
        )
    # Initialize mpv process for real-time audio playback
    mpv_process = subprocess.Popen(
        [mpv_path, "--no-cache", "--no-terminal", "--", "fd://0"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    async for chunk in audio_stream:
        if chunk:
            mpv_process.stdin.write(chunk)
            mpv_process.stdin.flush()

    if mpv_process.stdin:
        mpv_process.stdin.close()
    mpv_process.wait()


async def text_to_speech_stream(text_iterator):
    """
    Stream text to speech using WebSocket API
    Args:
        text_iterator: Async iterator yielding text chunks
    """
    uri = "wss://api.fish.audio/v1/tts/live"  # Updated URI

    async with websockets.connect(
        uri, additional_headers={"Authorization": "Bearer " + FISH_API_KEY}
    ) as websocket:
        # Send initial configuration
        await websocket.send(
            ormsgpack.packb(
                {
                    "event": "start",
                    "request": {
                        "text": "",
                        "latency": "normal",
                        "format": "opus",
                        "reference_id": REFERENCE_ID,
                    },
                    "debug": True,  # Added debug flag
                }
            )
        )

        # Handle incoming audio data
        async def listen():
            while True:
                try:
                    message = await websocket.recv()
                    data = ormsgpack.unpackb(message)
                    if data["event"] == "audio":
                        yield data["audio"]
                except websockets.exceptions.ConnectionClosed:
                    break

        # Start audio streaming task
        listen_task = asyncio.create_task(stream_audio(listen()))

        # Stream text chunks
        async for text in text_iterator:
            if text:
                await websocket.send(ormsgpack.packb({"event": "text", "text": text}))

        # Send stop signal
        await websocket.send(ormsgpack.packb({"event": "stop"}))
        await listen_task


async def chat_completion(query):
    """Retrieve text from OpenAI and pass it to the text-to-speech function."""
    response = await aclient.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": query}],
        max_completion_tokens=512,
        temperature=1,
        stream=True,
    )

    async def text_iterator():
        async for chunk in response:
            delta = chunk.choices[0].delta
            yield delta.content

    await text_to_speech_stream(text_iterator())  # Updated function name


# Main execution
if __name__ == "__main__":
    user_query = '请重复以下内容，不要加任何别的字：' +\
                "你好，旅行者，我是可莉。我要出去炸鱼，你不要告诉琴团长，不然等我出来了我他妈的炸死你这个王八蛋."
    asyncio.run(chat_completion(user_query))