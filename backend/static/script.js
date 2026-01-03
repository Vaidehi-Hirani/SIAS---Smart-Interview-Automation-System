const API_URL = "http://localhost:8000/api";
let mediaRecorder;
let audioChunks = [];
let recordingInterval;
let currentSessionId = null;
let statusCheckInterval;
let isSleepMode = true;
let dashboardPollInterval = null;
let lastPresenceTime = 0;

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    checkStatus();
    statusCheckInterval = setInterval(checkStatus, 5000); // Poll status every 5s
    setupSensors();
    
    document.getElementById('simulate-presence-btn').addEventListener('click', () => {
        triggerPresence("Motion Simulation");
    });
});

// --- View Management ---
function showView(viewId) {
    document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));
    document.getElementById(viewId).classList.add('active');
    
    // Stop dashboard polling if we leave dashboard
    if (viewId !== 'view-dashboard' && dashboardPollInterval) {
        clearInterval(dashboardPollInterval);
        dashboardPollInterval = null;
    }
}

// --- API Calls ---
async function checkStatus() {
    try {
        const res = await fetch(`${API_URL}/status`);
        const data = await res.json();
        
        if (data.status === "SLEEP") {
            if (!isSleepMode) {
                isSleepMode = true;
                showView('view-sleep');
                stopRecording(); // Safety
            }
        } else if (data.status === "IDLE") {
            isSleepMode = false;
            // Only switch to selection if we are currently in sleep
            if (document.getElementById('view-sleep').classList.contains('active')) {
                showView('view-selection');
            }
        } else if (data.status === "RECORDING") {
            isSleepMode = false;
            if (!document.getElementById('view-interview').classList.contains('active')) {
                showView('view-interview');
                currentSessionId = data.current_session_id;
                startRecordingUI(); // Resume UI if page reloaded
            }
        }
    } catch (e) {
        console.error("Status check failed", e);
    }
}

async function triggerPresence(source, skipCheck = false) {
    const formData = new FormData();
    formData.append('source', source);
    // Use sendBeacon or fetch without awaiting if just heartbeat, but fetch is fine.
    // We don't await the result to keep UI responsive if it's just a heartbeat
    fetch(`${API_URL}/detect-presence`, { method: 'POST', body: formData }).catch(e => console.error(e));
    
    if (!skipCheck) {
        checkStatus(); // Immediate check only if requested (e.g. initial wake up)
    }
}

async function updateCameraConfig() {
    const id = document.getElementById('camera-id-input').value;
    const formData = new FormData();
    formData.append('camera_id', id);
    const res = await fetch(`${API_URL}/config-camera`, { method: 'POST', body: formData });
    const data = await res.json();
    alert(data.message || data.error);
}

async function selectCandidate(type) {
    const formData = new FormData();
    formData.append('candidate_type', type);
    
    const res = await fetch(`${API_URL}/start-session`, { method: 'POST', body: formData });
    const data = await res.json();
    
    if (data.action === "SLEEP") {
        alert(data.message);
        showView('view-sleep');
    } else if (data.action === "START_INTERVIEW") {
        currentSessionId = data.session_id;
        showView('view-interview');
        startRecording();
    }
}

async function endInterview() {
    if (!currentSessionId) return;
    
    // Stop recording first. 
    // The actual API call to /end-session will happen in the mediaRecorder.onstop event
    // after the full audio file is uploaded.
    stopRecording();
}

// --- Recording Logic ---
async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = []; // Reset chunks
        
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = async () => {
            // Upload the full blob
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            const formData = new FormData();
            formData.append('file', audioBlob);
            formData.append('session_id', currentSessionId);
            
            try {
                // 1. Upload Full Audio
                console.log("Uploading full audio...");
                await fetch(`${API_URL}/upload-full-audio`, { method: 'POST', body: formData });
                
                // 2. End Session (Triggers AI)
                console.log("Ending session...");
                const endFormData = new FormData();
                endFormData.append('session_id', currentSessionId);
                const res = await fetch(`${API_URL}/end-session`, { method: 'POST', body: endFormData });
                const data = await res.json();
                
                alert(data.message);
                showView('view-selection');
                
            } catch (e) {
                console.error("Error finalizing session:", e);
                alert("Error saving interview recording.");
            }
            
            // Stop tracks only after processing
            stream.getTracks().forEach(track => track.stop());
        };
        
        mediaRecorder.start(); // No timeslice argument!
        visualizeAudio(stream);
    } catch (e) {
        console.error("Mic access failed", e);
        alert("Microphone access required for interview.");
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
        // Do NOT stop tracks here. Done in onstop.
    }
}

function startRecordingUI() {
    startRecording();
}

// --- Sensors (VAD) ---
async function setupSensors() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const audioContext = new AudioContext();
        const analyser = audioContext.createAnalyser();
        const microphone = audioContext.createMediaStreamSource(stream);
        const scriptProcessor = audioContext.createScriptProcessor(2048, 1, 1);

        analyser.smoothingTimeConstant = 0.8;
        analyser.fftSize = 1024;
        microphone.connect(analyser);
        analyser.connect(scriptProcessor);
        scriptProcessor.connect(audioContext.destination);
        
        scriptProcessor.onaudioprocess = function() {
            const array = new Uint8Array(analyser.frequencyBinCount);
            analyser.getByteFrequencyData(array);
            const arraySum = array.reduce((a, value) => a + value, 0);
            const average = arraySum / array.length;
            
            document.getElementById('voice-indicator').innerText = `Voice Level: ${Math.round(average)}`;
            
            // Threshold for VAD (Auto Wake Up & Keep Alive)
            if (average > 30) {
                const now = Date.now();
                if (isSleepMode) {
                    triggerPresence("Voice Detected", false); // Wake up immediately
                    lastPresenceTime = now;
                } else if (now - lastPresenceTime > 5000) {
                    // Heartbeat to keep session alive during silence/thinking
                    triggerPresence("Voice Heartbeat", true); 
                    lastPresenceTime = now;
                }
            }
        };
    } catch (e) {
        console.log("Sensor init failed (likely permission)", e);
    }
}

function visualizeAudio(stream) {
    const canvas = document.getElementById("visualizer");
    const canvasCtx = canvas.getContext("2d");
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(stream);
    const analyser = audioCtx.createAnalyser();
    
    source.connect(analyser);
    analyser.fftSize = 2048;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    function draw() {
        requestAnimationFrame(draw);
        analyser.getByteTimeDomainData(dataArray);
        canvasCtx.fillStyle = 'rgb(255, 255, 255)';
        canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
        canvasCtx.lineWidth = 2;
        canvasCtx.strokeStyle = 'rgb(0, 123, 255)';
        canvasCtx.beginPath();
        const sliceWidth = canvas.width * 1.0 / bufferLength;
        let x = 0;
        for(let i = 0; i < bufferLength; i++) {
            const v = dataArray[i] / 128.0;
            const y = v * canvas.height/2;
            if(i === 0) canvasCtx.moveTo(x, y);
            else canvasCtx.lineTo(x, y);
            x += sliceWidth;
        }
        canvasCtx.lineTo(canvas.width, canvas.height/2);
        canvasCtx.stroke();
    }
    draw();
}

// --- Dashboard ---
async function showDashboard() {
    showView('view-dashboard');
    refreshDashboard();
    
    // Auto refresh while on dashboard
    if (dashboardPollInterval) clearInterval(dashboardPollInterval);
    dashboardPollInterval = setInterval(refreshDashboard, 5000);
}

async function refreshDashboard() {
    const res = await fetch(`${API_URL}/sessions`);
    const sessions = await res.json();
    const tbody = document.getElementById('dashboard-body');
    tbody.innerHTML = '';
    
    sessions.forEach(s => {
        const isProcessing = s.status === 'processing' || s.status === 'active';
        const summaryText = s.summary || (isProcessing ? 'Processing...' : 'No Summary');
        const shortSummary = summaryText.length > 50 ? summaryText.substring(0, 50) + '...' : summaryText;
        
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${s.id}</td>
            <td>${s.candidate_type}</td>
            <td>${new Date(s.start_time).toLocaleString()}</td>
            <td>
                ${shortSummary} 
                <br>
                <button class="small-btn" onclick="openSummary(${s.id})">View Full</button>
            </td>
            <td>${s.skills || '-'}</td>
            <td>${s.availability || '-'}</td>
            <td>${s.experience || '-'}</td>
            <td>
                ${s.audio_path ? `
                    <button class="small-btn" onclick="playAudio(${s.id})">Play</button>
                    <button class="small-btn danger" onclick="deleteAudio(${s.id})">Delete</button>
                ` : 'Deleted / None'}
            </td>
        `;
        tbody.appendChild(tr);
        
        // Store full summary for modal
        tr.dataset.summary = s.summary || "No Content";
    });
}

async function resetSystem() {
    const formData = new FormData();
    formData.append('candidate_type', 'Visitor'); // Trigger sleep logic
    await fetch(`${API_URL}/start-session`, { method: 'POST', body: formData });
    showView('view-sleep');
}

// --- Modal & Audio ---
function openSummary(id) {
    fetch(`${API_URL}/sessions`)
        .then(res => res.json())
        .then(sessions => {
            const s = sessions.find(x => x.id == id);
            if (s) {
                const modalBody = document.getElementById('modal-body');
                
                // If we have structured JSON data
                if (s.json_data) {
                    const d = s.json_data;
                    
                    // Helper to list items
                    const listItems = (arr) => arr && arr.length ? `<ul>${arr.map(x => `<li>${x}</li>`).join('')}</ul>` : 'None';
                    
                    // Helper for projects
                    const renderProjects = (projs) => {
                        if (!projs || !projs.length) return 'None';
                        return projs.map(p => `
                            <div class="project-card">
                                <strong>${p.title}</strong><br>
                                ${p.description}<br>
                                <em>Tech: ${p.technologies.join(', ') || 'N/A'}</em>
                            </div>
                        `).join('');
                    };

                    modalBody.innerHTML = `
                        <h3>${d.name || 'Candidate'}</h3>
                        <p><strong>Summary:</strong> ${d.summary}</p>
                        <hr>
                        <div class="details-grid">
                            <div><strong>Experience:</strong> ${d.experience}</div>
                            <div><strong>Availability:</strong> ${d.availability}</div>
                            <div><strong>Education:</strong> ${d.education}</div>
                            <div><strong>College:</strong> ${d.college}</div>
                        </div>
                        <hr>
                        <h4>Skills</h4>
                        <p>${d.skills.join(', ') || 'None'}</p>
                        
                        <h4>Projects</h4>
                        ${renderProjects(d.projects)}
                        
                        <h4>Achievements</h4>
                        ${listItems(d.achievements)}
                        
                        <h4>Hobbies</h4>
                        ${listItems(d.hobbies)}
                    `;
                } else {
                    // Fallback to plain summary text
                    modalBody.innerText = s.summary;
                }
                
                document.getElementById('summary-modal').style.display = "block";
            }
        });
}

function closeModal() {
    document.getElementById('summary-modal').style.display = "none";
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('summary-modal');
    if (event.target == modal) {
        modal.style.display = "none";
    }
}

function playAudio(sessionId) {
    const audio = new Audio(`${API_URL}/audio/${sessionId}`);
    audio.play();
}

async function deleteAudio(sessionId) {
    if (!confirm("Are you sure you want to delete this audio?")) return;
    
    const res = await fetch(`${API_URL}/delete-audio/${sessionId}`, { method: 'POST' });
    const data = await res.json();
    alert(data.message || data.error);
    refreshDashboard();
}
