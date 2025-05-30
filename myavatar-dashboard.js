console.log("MyAvatar dashboard JS loaded! [FORCE REDEPLOY 2025-05-30-11:00]");

console.log("MyAvatar dashboard JS loaded! [FORCE REDEPLOY 2025-05-30-11:00]");
// static/js/myavatar-dashboard.js
// React-dashboard til MyAvatar Portal
// Med faner: Avatar, Video, Optag

const { useState, useEffect, useRef } = React;
const API            = window.APIService;
const cfg            = window.AppConfig;
const AudioRecorder  = window.AudioRecorder;

// Avatar-kort
const AvatarCard = ({ avatar, selected, onSelect }) => (
  <div
    className={`card mb-2 ${selected ? 'border-primary' : ''}`}
    style={{ cursor: 'pointer' }}
    onClick={() => onSelect(avatar)}
  >
    <div className="card-body py-2 d-flex align-items-center">
      <img
        src={avatar.thumbnail_url || cfg.ui.logo}
        width="48"
        height="48"
        className="me-2 rounded"
      />
      <span>{avatar.name}</span>
    </div>
  </div>
);

// Video-kort
const VideoCard = ({ video }) => {
  const videoUrl = video.video_url?.startsWith('http') ? video.video_url : `${window.AppConfig.api.baseUrl}${video.video_url}`;
  
  return (
    <div className="col-md-4 mb-3">
      <div className="card h-100">
        <video 
          src={videoUrl} 
          controls 
          className="card-img-top" 
          onError={(e) => {
            console.error('Video playback error:', e);
            e.target.style.display = 'none';
          }}
        />
        <div className="card-body py-2 d-flex justify-content-between">
          <small className="text-muted">
            {new Date(video.created_at).toLocaleString()}
          </small>
          <div className="btn-group">
            <a
              href={videoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-sm btn-outline-primary me-1"
            >
              Play in new tab
            </a>
            <a
              href={videoUrl}
              download
              className="btn btn-sm btn-outline-success"
            >
              Download
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};

// Hovedkomponent
function Dashboard({ initialUser, initialOrg }) {
  console.log("Dashboard component mounted", { initialUser, initialOrg }); // <-- This goes first!

  const [user, setUser]           = useState(initialUser || null);
  const [avatars, setAvatars]     = useState([]);
  const [videos, setVideos]       = useState([]);
  const [view, setView]           = useState('avatars');
  const [selAvatar, setSelAvatar] = useState(null);
  const [recording, setRecording] = useState(false);
  const [secLeft, setSecLeft]     = useState(0);
  const [progress, setProgress]   = useState(null);
  const [microphoneTestResult, setMicrophoneTestResult] = useState(null);
  const recRef = useRef(null);

  // Hent initial data
  useEffect(() => {
    (async () => {
      try {
        const [a, v] = await Promise.all([
          API.getAvatars(),
          API.getVideos()
        ]);
        setAvatars(a.avatars || []);
        setVideos(v || []);
      } catch (err) {
        console.error('Fejl ved hentning:', err);
      }
    })();
  }, []);

  // Test mikrofon
  const testMicrophone = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      source.connect(analyser);
      
      // Test lyd niveau
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(dataArray);
      
      // Luk stream efter test
      stream.getTracks().forEach(track => track.stop());
      
      setMicrophoneTestResult({
        success: true,
        message: 'Mikrofon fungerer! Lyd blev registreret.'
      });
    } catch (err) {
      console.error('Fejl ved mikrofon test:', err);
      setMicrophoneTestResult({
        success: false,
        message: 'Kunne ikke teste mikrofon. Fejl: ' + err.message
      });
    }
  };

 // Start optagelse
const startRec = async () => {
  console.log('startRec triggered');
  try {
    // Få mikrofon adgang
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    // Initialiser og start optagelse
    recRef.current = new AudioRecorder({
      maxSeconds: cfg.ui.maxRecordingTime,
      onTick: secs => setSecLeft(secs)
    });
    
    // ADD THIS LINE - Makes recorder accessible to API service
    window.recorder = recRef.current;
    
    await recRef.current.start();
    setRecording(true);
    setProgress(null);
  } catch (err) {
    console.error('Fejl ved mikrofon adgang:', err);
    alert('Kunne ikke få adgang til mikrofonen. Venligst giv tilladelse i browseren.');
    setRecording(false);
  }
};

  // Stop optagelse og generer video
  const stopRec = async () => {
    console.log('stopRec triggered, stopping recorder');
    const blob = await recRef.current.getBlob();
    setRecording(false);
    generateVideo(blob);
  };

  // Generer video via HeyGen + poll status
  const generateVideo = async blob => {
    console.log('generateVideo', blob, selAvatar);
    if (!selAvatar) return alert(cfg.ui.text.selectAvatarFirst);
    try {
      setProgress(0);
      const { video_id } = await API.generateVideo(blob, selAvatar.id);
      const data = await API.pollVideoStatus(
        video_id,
        p => { console.log('poll progress', p); setProgress(p); }
      );
      setVideos(v => [data, ...v]);
      setProgress(null);
    } catch (err) {
      console.error('Video generation error:', err);
      setProgress('err');
    }
  };

  // Hvis user ikke tilgængelig
  if (!user) {
    return <div className="container py-5 text-center">Indlæser…</div>;
  }

  return (
    <div className="container-fluid">
      {/* Faner */}
      <div className="row mb-3">
        <div className="col">
          <button
            className={`btn me-2 ${view==='avatars'?'btn-primary':'btn-outline-primary'}`}
            onClick={() => setView('avatars')}
          >Mine Avatarer</button>
          <button
            className={`btn me-2 ${view==='videos'?'btn-primary':'btn-outline-primary'}`}
            onClick={() => setView('videos')}
          >Mine Videoer</button>
          <button
            className={`btn ${view==='record'?'btn-primary':'btn-outline-primary'}`}
            onClick={() => setView('record')}
          >Optag Video (HeyGen)</button>
        </div>
      </div>

      {/* Paneler */}
      {view === 'avatars' && (
        <div className="row">
          {avatars.map(av => (
            <div key={av.id} className="col-md-4">
              <AvatarCard
                avatar={av}
                selected={selAvatar?.id === av.id}
                onSelect={setSelAvatar}
              />
            </div>
          ))}
        </div>
      )}

      {view === 'videos' && (
        <div className="row">
          {videos.length === 0 ? (
            <p>{cfg.ui.text.noVideosMessage}</p>
          ) : (
            videos.map(v => <VideoCard key={v.video_id} video={v} />)
          )}
        </div>
      )}

      {view === 'record' && (
        <div className="card p-3">
          <h5>{cfg.ui.text.recordTitle}</h5>
          <div className="mb-3">
            <button className="btn btn-outline-info me-2" onClick={testMicrophone}>
              🔍 Test Mikrofon
            </button>
            {!recording ? (
              <button className="btn btn-danger" onClick={startRec}>
                🎤 Start Optagelse
              </button>
            ) : (
              <button className="btn btn-secondary" onClick={stopRec}>
                ⏹ Stop ({secLeft}s)
              </button>
            )}
          </div>
          
          {progress !== null && (
            typeof progress === 'number' ? (
              <div className="progress mt-3" style={{ height: 6 }}>
                <div className="progress-bar" style={{ width: `${progress}%` }} />
              </div>
            ) : (
              <p className="text-danger mt-3">{cfg.ui.text.generationFailed}</p>
            )
          )}
          
          {microphoneTestResult && (
            <div className={`alert alert-${microphoneTestResult.success ? 'success' : 'danger'} mt-3`}>
              {microphoneTestResult.message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

window.MyAvatarDashboard = Dashboard;
console.log("=== window.MyAvatarDashboard is now set ===");
// force-redeploy-2025-05-30 // version: 2025-05-30-10-48
