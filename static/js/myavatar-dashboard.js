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
        const poll = async () => {
            const res = await fetch(`/api/video/status/${videoId}`);
            const data = await res.json();
            if (data.status === "completed" && data.video_url) {
                setVideoStatus("klar");
                setVideoUrl(data.video_url);
                showToast("Video klar!", "success");
            } else if (tries < 15) {
                tries++;
                setTimeout(poll, 4000);
            } else {
                showToast("Timeout på video", "error");
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
