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
    // }).then(() => {
    //     // wait for ICE gathering to complete
    //     return new Promise((resolve) => {
    //         if (pc.iceConnectionState === 'connected') {
    //             resolve();
    //         } else {
    //             const checkState = () => {
    //                 if (pc.iceConnectionState === 'connected') {
    //                     pc.removeEventListener('iceConnectionState', checkState);
    //                     resolve();
    //                 }
    //             };
    //             pc.addEventListener('iceConnectionState', checkState);
    //         }
    //     });
    }).then(() => {
        var offer = pc.localDescription;
        return fetch('/offer', {
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