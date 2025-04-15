import os
import httpx
import ormsgpack
from pydantic import AfterValidator, BaseModel, conint
from pathlib import Path
from typing import Annotated, AsyncGenerator, Literal


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


# 确定基础目录
BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.name == 'api':
    BASE_DIR = BASE_DIR.parent  # 如果在api目录中，则父目录为项目根目录


class ServeReferenceAudio(BaseModel):
    audio: bytes
    text: str


class ServeTTSRequest(BaseModel):
    text: str
    chunk_length: Annotated[int, conint(ge=100, le=300, strict=True)] = 200
    # Audio format
    format: Literal["wav", "pcm", "mp3"] = "mp3"
    mp3_bitrate: Literal[64, 128, 192] = 128
    # References audios for in-context learning
    references: list[ServeReferenceAudio] = []
    # Reference id
    # For example, if you want use https://fish.audio/m/7f92f8afb8ec43bf81429cc1c9199cb1/
    # Just pass 7f92f8afb8ec43bf81429cc1c9199cb1
    reference_id: str | None = None
    # Normalize text for en & zh, this increase stability for numbers
    normalize: bool = True
    # Balance mode will reduce latency to 300ms, but may decrease stability
    latency: Literal["normal", "balanced"] = "normal"




if __name__ == "__main__":

    request = ServeTTSRequest(
        text="你好，旅行者，我是可莉。我要出去炸鱼，你不要告诉琴团长，不然等我出来了我他妈的炸死你这个王八蛋",
        reference_id=REFERENCE_ID,
    )
    with (
        httpx.Client() as client,
        open("hello.mp3", "wb") as f,
    ):
        with client.stream(
            "POST",
            "https://api.fish.audio/v1/tts",
            content=ormsgpack.packb(request, option=ormsgpack.OPT_SERIALIZE_PYDANTIC),
            headers={
                "authorization": "Bearer " + FISH_API_KEY,
                "content-type": "application/msgpack",
                "model": "speech-1.6",  # Specify which TTS model to use
            },
            timeout=None,
        ) as response:
            for chunk in response.iter_bytes():
                f.write(chunk)
