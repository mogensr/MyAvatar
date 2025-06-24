// static/js/myavatar-dashboard.js

window.MyAvatarDashboard = function MyAvatarDashboard({ initialUser }) {
    const [isRecording, setIsRecording] = React.useState(false);
    const [mediaRecorder, setMediaRecorder] = React.useState(null);
    const [videoStatus, setVideoStatus] = React.useState(null);
    const [videoUrl, setVideoUrl] = React.useState(null);

    const chunks = React.useRef([]);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const recorder = new MediaRecorder(stream);
            recorder.ondataavailable = e => chunks.current.push(e.data);
            recorder.onstop = () => {
                const blob = new Blob(chunks.current, { type: 'audio/webm' });
                chunks.current = [];
                uploadAudio(blob);
            };
            recorder.start();
            setMediaRecorder(recorder);
            setIsRecording(true);
            showToast("Optager lyd...", "info");
        } catch (err) {
            console.error("Error starting recording:", err);
            showToast("Kunne ikke starte optagelse", "error");
        }
    };

    const stopRecording = () => {
        if (mediaRecorder) {
            mediaRecorder.stop();
            setIsRecording(false);
        }
    };

    const uploadAudio = async (blob) => {
        showToast("Uploader lyd...", "info");

        const formData = new FormData();
        formData.append("file", blob, "recording.webm");

        try {
            const response = await fetch("/api/video/generate", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const error = await response.text();
                throw new Error(error);
            }

            const data = await response.json();
            showToast("Video genereres...", "success");
            pollVideoStatus(data.id || data.video_id);
        } catch (err) {
            console.error(err);
            showToast("Upload fejlede", "error");
        }
    };

    const pollVideoStatus = async (videoId) => {
        let tries = 0;
        const maxTries = 30; // Increased from 15 to 30 (2 minutes total polling time)
        const poll = async () => {
            try {
                const res = await fetch(`/api/video/status/${videoId}`);
                if (!res.ok) {
                    console.error('Error fetching video status:', await res.text());
                    setTimeout(poll, 5000); // Try again after 5 seconds on error
                    return;
                }
                
                const data = await res.json();
                console.log('Video status update:', data);
                
                if (data.status === "completed" && data.video_url) {
                    setVideoStatus("klar");
                    setVideoUrl(data.video_url);
                    showToast("Video klar!", "success");
                    
                    // Force refresh video list if available
                    if (typeof refreshVideoList === 'function') {
                        refreshVideoList();
                    }
                } else if (data.status === "failed" || data.status === "error") {
                    showToast("Video processing failed", "error");
                } else if (tries < maxTries) {
                    tries++;
                    // Adaptive polling: Start with 4s intervals, increase to 6s after 10 tries
                    const interval = tries > 10 ? 6000 : 4000;
                    setTimeout(poll, interval);
                } else {
                    // Even after timeout, set up a background refresh
                    showToast("Video processing taking longer than expected. The page will refresh automatically when ready.", "warning");
                    // Set up a background poll every 10 seconds
                    setTimeout(() => {
                        window.location.reload();
                    }, 30000); // Refresh page after 30 seconds as last resort
                }
            } catch (err) {
                console.error('Polling error:', err);
                if (tries < maxTries) {
                    tries++;
                    setTimeout(poll, 5000); // Try again after 5 seconds
                }
            }
        };
        poll();
    };

    return (
        React.createElement("div", { className: "text-center" },
            React.createElement("h2", null, "Hej ", initialUser.username),
            React.createElement("p", null, "Tryk på knappen for at optage din stemme og generere din avatar-video."),
            isRecording
                ? React.createElement("button", { className: "btn btn-danger", onClick: stopRecording }, "🛑 Stop & Send")
                : React.createElement("button", { className: "btn btn-primary", onClick: startRecording }, "🎙️ Start optagelse"),

            videoUrl && (
                React.createElement("div", { className: "mt-4" },
                    React.createElement("h5", null, "Din video:"),
                    React.createElement("video", {
                        src: videoUrl,
                        controls: true,
                        style: { maxWidth: "100%", borderRadius: "10px" },
                        onError: () => setVideoError("Kunne ikke indlæse video. Tjek linket eller prøv at åbne det direkte.")
                    }),
                    videoError && (
                        React.createElement("div", { className: "alert alert-danger mt-2" },
                            videoError,
                            React.createElement("br", null),
                            React.createElement("a", { href: videoUrl, target: "_blank", rel: "noopener noreferrer" }, "Åbn video i nyt vindue")
                        )
                    ),
                    React.createElement("a", {
                        href: videoUrl,
                        download: "myavatar-video.mp4",
                        className: "btn btn-success mt-2"
                    }, "⬇️ Download video"),
                    React.createElement("div", { className: "mt-2" },
                        React.createElement("input", {
                            type: "text",
                            value: videoUrl,
                            readOnly: true,
                            style: { width: "80%", fontSize: "small" }
                        }),
                        React.createElement("button", {
                            className: "btn btn-outline-secondary btn-sm ms-2",
                            onClick: () => {
                                navigator.clipboard.writeText(videoUrl);
                                showToast("Video URL kopieret!", "success");
                            }
                        }, "Kopiér video URL")
                    )
                )
            )
        )
    );
};
