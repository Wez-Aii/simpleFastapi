import asyncio
import copy
import json
import os
import random
import time, logging
from fastapi.security import OAuth2PasswordBearer, HTTPBearer

from aiohttp import web

from datetime import datetime, timedelta
from typing import Annotated, List, Dict, Union
from fastapi import Depends, FastAPI, HTTPException, status, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from enum import Enum
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import cv2
import numpy
from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling
from aiortc.rtcrtpsender import RTCRtpSender
from av import VideoFrame


ROOT = os.path.dirname(__file__)

app = FastAPI()
# app.include_router(auth.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Bangkok")

LOGGING_LEVEL_DICT = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}

pcs = set()
web_offer_session_desc = None
remote_answer_session_desc = None

html = """
<!DOCTYPE html>
<html>

<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>WebRTC webcam</title>
    <style>
        button {
            padding: 8px 16px;
        }

        video {
            width: 100%;
        }

        .option {
            margin-bottom: 8px;
        }

        #media {
            max-width: 1280px;
        }
    </style>
</head>

<body>

    <div class="option">
        <input id="use-stun" type="checkbox" />
        <label for="use-stun">Use STUN server</label>
    </div>
    <button id="start" onclick="start()">Start</button>
    <button id="stop" style="display: none" onclick="stop()">Stop</button>

    <div id="media">
        <h2>Media</h2>

        <audio id="audio" autoplay="true"></audio>
        <video id="video" autoplay="true" playsinline="true"></video>
    </div>

    <script>
        var pc = null;

        function negotiate() {
            pc.addTransceiver('video', { direction: 'recvonly' });
            pc.addTransceiver('audio', { direction: 'recvonly' });
            return pc.createOffer().then((offer) => {
                return pc.setLocalDescription(offer);
            }).then(() => {
                // wait for ICE gathering to complete
                return new Promise((resolve) => {
                    if (pc.iceGatheringState === 'complete') {
                        resolve();
                    } else {
                        const checkState = () => {
                            if (pc.iceGatheringState === 'complete') {
                                pc.removeEventListener('icegatheringstatechange', checkState);
                                resolve();
                            }
                        };
                        pc.addEventListener('icegatheringstatechange', checkState);
                    }
                });
            }).then(() => {
                var offer = pc.localDescription;
                return fetch('/offer?cam_id=12345', {
                    body: JSON.stringify({
                        sdp: offer.sdp,
                        type: offer.type,
                    }),
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    method: 'POST'
                });
            }).then((response) => {
                console.log("response -", response)
                return response.json();
            }).then((answer) => {
                console.log("answer -", answer)
                return pc.setRemoteDescription(answer);
            }).catch((e) => {
                alert(e);
            });
        }

        function start() {
            var config = {
                sdpSemantics: 'unified-plan'
            };

            if (document.getElementById('use-stun').checked) {
                config.iceServers = [{ urls: ['stun:stun.l.google.com:19302'] }];
            }

            pc = new RTCPeerConnection(config);

            console.log("pre pc -", pc);

            // connect audio / video
            pc.addEventListener('track', (evt) => {
                console.log("get evt -",evt);
                if (evt.track.kind == 'video') {
                    document.getElementById('video').srcObject = evt.streams[0];
                } else {
                    document.getElementById('audio').srcObject = evt.streams[0];
                }
            });

            document.getElementById('start').style.display = 'none';
            negotiate();
            console.log("negotiation done");
            console.log("pc -", pc);
            // pc.addEventListener('track', (evt) => {
            //     console.log("pc -", pc);
            //     console.log("get evt -",evt);
            //     if (evt.track.kind == 'video') {
            //         document.getElementById('video').srcObject = evt.streams[0];
            //     } else {
            //         document.getElementById('audio').srcObject = evt.streams[0];
            //     }
            // });
            document.getElementById('stop').style.display = 'inline-block';
        }

        function stop() {
            document.getElementById('stop').style.display = 'none';

            // close peer connection
            setTimeout(() => {
                pc.close();
            }, 500);
        }
    </script>
</body>

</html>
"""

html2 = """
<!DOCTYPE html>
<html>

<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>WebRTC webcam</title>
    <style>
        button {
            padding: 8px 16px;
        }

        video {
            width: 100%;
        }

        .option {
            margin-bottom: 8px;
        }

        #media {
            max-width: 1280px;
        }
    </style>
</head>

<body>

    <div class="option">
        <input id="use-stun" type="checkbox" />
        <label for="use-stun">Use STUN server</label>
    </div>
    <button id="start" onclick="start()">Start</button>
    <button id="stop" style="display: none" onclick="stop()">Stop</button>

    <div id="media">
        <h2>Media</h2>

        <audio id="audio" autoplay="true"></audio>
        <video id="video" autoplay="true" playsinline="true"></video>
    </div>

    <script>
        var pc = null;

        function negotiate() {
            pc.addTransceiver('video', { direction: 'recvonly' });
            pc.addTransceiver('audio', { direction: 'recvonly' });
            return pc.createOffer().then((offer) => {
                return pc.setLocalDescription(offer);
            }).then(() => {
                // wait for ICE gathering to complete
                return new Promise((resolve) => {
                    if (pc.iceGatheringState === 'complete') {
                        resolve();
                    } else {
                        const checkState = () => {
                            if (pc.iceGatheringState === 'complete') {
                                pc.removeEventListener('icegatheringstatechange', checkState);
                                resolve();
                            }
                        };
                        pc.addEventListener('icegatheringstatechange', checkState);
                    }
                });
            }).then(() => {
                var offer = pc.localDescription;
                return fetch('/offer?cam_id=6789', {
                    body: JSON.stringify({
                        sdp: offer.sdp,
                        type: offer.type,
                    }),
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    method: 'POST'
                });
            }).then((response) => {
                console.log("response -", response)
                return response.json();
            }).then((answer) => {
                console.log("answer -", answer)
                return pc.setRemoteDescription(answer);
            }).catch((e) => {
                alert(e);
            });
        }

        function start() {
            var config = {
                sdpSemantics: 'unified-plan'
            };

            if (document.getElementById('use-stun').checked) {
                config.iceServers = [{ urls: ['stun:stun.l.google.com:19302'] }];
            }

            pc = new RTCPeerConnection(config);

            console.log("pre pc -", pc);

            // connect audio / video
            pc.addEventListener('track', (evt) => {
                console.log("get evt -",evt);
                if (evt.track.kind == 'video') {
                    document.getElementById('video').srcObject = evt.streams[0];
                } else {
                    document.getElementById('audio').srcObject = evt.streams[0];
                }
            });

            document.getElementById('start').style.display = 'none';
            negotiate();
            console.log("negotiation done");
            console.log("pc -", pc);
            // pc.addEventListener('track', (evt) => {
            //     console.log("pc -", pc);
            //     console.log("get evt -",evt);
            //     if (evt.track.kind == 'video') {
            //         document.getElementById('video').srcObject = evt.streams[0];
            //     } else {
            //         document.getElementById('audio').srcObject = evt.streams[0];
            //     }
            // });
            document.getElementById('stop').style.display = 'inline-block';
        }

        function stop() {
            document.getElementById('stop').style.display = 'none';

            // close peer connection
            setTimeout(() => {
                pc.close();
            }, 500);
        }
    </script>
</body>

</html>
"""

relay = None
webcam = None

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

manager = ConnectionManager()

class PCDescription(BaseModel):
    sdp : str
    type: str

class FlagVideoStreamTrack(VideoStreamTrack):
    """
    A video track that returns an animated flag.
    """

    def __init__(self):
        super().__init__()  # don't forget this!
        self.counter = 0
        height, width = 480, 640
        video_path = "/dev/video0"
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)

    async def recv(self):
        # Read frames from the video file and convert them to RTCVideoFrames
        ret, img = self.cap.read()
        if ret:
            pts, time_base = await self.next_timestamp()
            frame = VideoFrame.from_ndarray(img, format="bgr24")
            frame.pts = pts
            frame.time_base = time_base
            await asyncio.sleep(1/30)
            # cv2.putText(frame, 'Write By CV2', (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,255),2, cv2.LINE_4)
            return frame
        else:
            # Video ended, close the connection
            self.cap.release()
            raise ConnectionError("Video stream ended")
        


def create_local_tracks(play_from, decode):
    global relay, webcam

    if play_from:
        player = MediaPlayer(play_from, decode=decode)
        return player.audio, player.video
    else:
        options = {"framerate": "30", "video_size": "640x480"}
        if relay is None:
            # if platform.system() == "Darwin":
            #     webcam = MediaPlayer(
            #         "default:none", format="avfoundation", options=options
            #     )
            # elif platform.system() == "Windows":
            #     webcam = MediaPlayer(
            #         "video=Integrated Camera", format="dshow", options=options
            #     )
            # else:
            #     webcam = MediaPlayer("/dev/video0", format="v4l2", options=options)
            relay = MediaRelay()
        # return None, relay.subscribe(webcam)
        return None, relay.subscribe(FlagVideoStreamTrack())
        # return None, FlagVideoStreamTrack()


def force_codec(pc, sender, forced_codec):
    kind = forced_codec.split("/")[0]
    codecs = RTCRtpSender.getCapabilities(kind).codecs
    transceiver = next(t for t in pc.getTransceivers() if t.sender == sender)
    transceiver.setCodecPreferences(
        [codec for codec in codecs if codec.mimeType == forced_codec]
    )


@app.get("/")
async def get():
    # content = open(os.path.join(ROOT, "index.html"), "r").read()
    # print(content)
    # return HTMLResponse(content=content)
    return HTMLResponse(html)
    # return web.Response(content_type="text/html", text=content)

@app.get("/789")
async def get():
    # content = open(os.path.join(ROOT, "index.html"), "r").read()
    # print(content)
    # return HTMLResponse(content=content)
    return HTMLResponse(html2)
    # return web.Response(content_type="text/html", text=content)


@app.get("/client.js")
async def javascript():
    # javascript_file_path = "path/to/your/javascript/file.js"
    # print("javascript file path", javascript_file_path)
    # return FileResponse(javascript_file_path, media_type='application/javascript')
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    # return content
    print(content)
    return web.Response(content_type="application/javascript", text=content)

@app.post("/offer")
async def offer(cam_id, body: PCDescription):
    global web_offer_session_desc, remote_answer_session_desc
    print("cam_id -", cam_id)
    # params = await body.json()
    web_offer_session_desc = {
        "sdp": body.sdp,
        "type": body.type
    }
    while remote_answer_session_desc is None:
        await asyncio.sleep(1)

    print("set_offer")
    content = remote_answer_session_desc.copy()
    remote_answer_session_desc = None
    web_offer_session_desc = None
    return JSONResponse(content=content)
    # return web.Response(
    #     content_type="application/json",
    #     text=json.dumps(
    #         remote_answer_session_desc
    #     ),
    # )  


@app.get("/offer")
async def get_offer():
    global web_offer_session_desc
    if web_offer_session_desc is not None:
        print("get_offer")
        return JSONResponse(content=web_offer_session_desc)
        # return web.Response(
        #     content_type="application/json",
        #     text=json.dumps(
        #         web_offer_session_desc
        #     ),
        # )
    else:
        return Response(status_code=404, content="Not Found")
        # return web.Response(status=404, text="Not Found")


@app.post("/stream")
async def set_stream(body: PCDescription):
    global web_offer_session_desc, remote_answer_session_desc
    # params = await request.json()
    remote_answer_session_desc = {
        "sdp": body.sdp,
        "type": body.type
    }

    if web_offer_session_desc is not None:
        print("get_anser")
        content = web_offer_session_desc.copy()
        web_offer_session_desc = None
        return JSONResponse(content=content)
        # return web.Response(
        #     content_type="application/json",
        #     text=json.dumps(
        #         web_offer_session_desc
        #     ),
        # )
    else:
        return Response(status_code=404, content="Not Found")
        # return web.Response(status=404, text="Not Found")


@app.get("/machinetime")
async def get_machine_time():
    _current_time = time.time()
    print(f"current machine time {_current_time}")
    return _current_time


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    global manager, remote_answer_session_desc
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            remote_answer_session_desc = json.load(data)
    except WebSocketDisconnect:
        manager.disconnect(client_id)