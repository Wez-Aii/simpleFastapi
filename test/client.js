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
        return response.json();
    }).then((answer) => {
        return pc.setRemoteDescription(answer);
    }).catch((e) => {
        alert(e);
    });
}

function start() {
    // var config = {
    //     sdpSemantics: 'unified-plan'
    // };

    // if (document.getElementById('use-stun').checked) {
    //     config.iceServers = [{ urls: ['stun:stun.l.google.com:19302'] }];
    // }

    // Function to set up the RTCPeerConnection using information from the server response
    async function setupPeerConnection(pcInfo) {
        // Create an RTCPeerConnection object
        const pc = new RTCPeerConnection();

        // Set ICE connection state received from the server response
        pc.iceConnectionState = pcInfo.ice_connection_state;

        console.log(pcInfo)

        pc.setRemoteDescription({
            type: pcInfo.remote_session.type,
            sdp: pcInfo.remote_session.sdp
        });
        // const localDescription = {
        //     type: pcInfo.local_description.type,
        //     sdp: pcInfo.local_description.sdp
        // };
        // await pc.setLocalDescription(localDescription);
        // Set local description received from the server response
        if (pcInfo.local_description) {
            const localDescription = {
                type: pcInfo.local_description.type,
                sdp: pcInfo.local_description.sdp
            };
            await pc.setLocalDescription(localDescription).then(() => {
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
            });
        }

        // Add event handlers or perform any additional configuration as needed

        return pc;
    }

    fetch('/offer')
    .then(response => response.json())
    .then(pcInfo => {
        // Set up RTCPeerConnection using information from the server response
        return setupPeerConnection(pcInfo);
    })
    .then(pc => {
        // Use the configured RTCPeerConnection (pc) for further communication
        console.log('RTCPeerConnection is set up:', pc);
        // connect audio / video
        pc.addEventListener('track', (evt) => {
            if (evt.track.kind == 'video') {
                document.getElementById('video').srcObject = evt.streams[0];
            } else {
                document.getElementById('audio').srcObject = evt.streams[0];
            }
        });

        document.getElementById('start').style.display = 'none';
        // negotiate();
        document.getElementById('stop').style.display = 'inline-block';
        })
    .catch(error => {
        console.error('Error setting up RTCPeerConnection:', error);
    });

}

function stop() {
    document.getElementById('stop').style.display = 'none';

    // close peer connection
    setTimeout(() => {
        pc.close();
    }, 500);
}
